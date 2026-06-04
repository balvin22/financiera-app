# src/data_engine/reports/flujo_efectivo.py
import polars as pl
import pandas as pd
import xlsxwriter
import os
import sqlite3
from src.core.db_manager import DBManager
from src.data_engine.extractors.bancolombia import BancolombiaExtractor
from src.data_engine.extractors.occidente import OccidenteExtractor
from src.data_engine.extractors.davivienda import DaviviendaExtractor
from src.data_engine.extractors.agrario import AgrarioExtractor
from src.data_engine.extractors.caja import CajaExtractor
from src.data_engine.extractors.alianza import AlianzaExtractor
from src.data_engine.extractors.caja_bancos import CajaBancosExtractor
from src.core.mapeos import ORDEN_BANCOS, MAPEO_CAJAS

from .calculadora_saldos import calcular_detallado
from .constructor_resumen import armar_resumen_gerencial

class GeneradorFlujoEfectivo:
    def __init__(self, rutas_archivos: dict, ajustes_manuales: dict = None, saldos_iniciales: dict = None):
        self.rutas = rutas_archivos.copy()
        self.ajustes = ajustes_manuales or {}
        self.saldos_iniciales = saldos_iniciales or {}
        self.db = DBManager()
        
        if self.rutas.get("caja_bancos") is None and os.path.exists("local_cache/caja_bancos.xlsx"):
            self.rutas["caja_bancos"] = "local_cache/caja_bancos.xlsx"
        
    def generar_base_consolidada(self) -> pl.DataFrame:
        print("Iniciando extracción y consolidación de datos...\n")
        dataframes = []
        
        extractores = {
            "BANCOLOMBIA": BancolombiaExtractor(self.rutas.get("bancolombia")),
            "OCCIDENTE": OccidenteExtractor(self.rutas.get("occidente")),
            "DAVIVIENDA": DaviviendaExtractor(self.rutas.get("davivienda")),
            "AGRARIO": AgrarioExtractor(self.rutas.get("agrario")),
            "ALIANZA": AlianzaExtractor(self.rutas.get("alianza")),
            "CAJA": CajaExtractor(self.rutas.get("caja")),
            "CAJA_BANCOS": CajaBancosExtractor(self.rutas.get("caja_bancos"))
        }
        
        for banco, extractor in extractores.items():
            if extractor.filepath is not None: 
                try:
                    df = extractor.process()
                    if not df.is_empty():
                        dataframes.append(df)
                except Exception as e:
                    print(f"❌ Error crítico en {banco}: {e}")
        
        if not dataframes:
            return pl.DataFrame()
            
        df_global = pl.concat(dataframes, how="diagonal")

        if "Centro_Costos" in df_global.columns:
            df_global = df_global.with_columns(
                pl.col("Centro_Costos").cast(pl.Utf8).str.extract(r"(\d{5})").replace_strict(MAPEO_CAJAS, default=pl.col("Centro_Costos")).alias("Centro_Costos")
            )
            
        return df_global
    
    def generar_mensual_desde_bd(self, mes_filtro: str = None):
        print("Consultando la Base de Datos para armar el reporte mensual...")
        movimientos_db = self.db.get_movimientos()
        
        if not movimientos_db:
            raise ValueError("No hay datos en la Base de Datos.")
        
        if mes_filtro:
            movimientos_db = [m for m in movimientos_db if m.get("fecha", "").startswith(mes_filtro)]
            if not movimientos_db:
                raise ValueError(f"No hay movimientos para el mes {mes_filtro}")
            mes_prefix = mes_filtro
        else:
            fechas_validas = [m["fecha"] for m in movimientos_db if m.get("fecha")]
            mes_prefix = min(fechas_validas)[:7] if fechas_validas else ""

        saldos_iniciales_mes = self.saldos_iniciales.copy()

        with sqlite3.connect("local_cache/maestros.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT banco, saldo_inicial FROM saldos_diarios WHERE fecha LIKE ? ORDER BY fecha ASC", (f"{mes_prefix}%",))
            
            bancos_cargados_db = set()
            for row in cursor.fetchall():
                banco = row[0]
                saldo = row[1]
                if banco not in bancos_cargados_db:
                    saldos_iniciales_mes[banco] = saldo 
                    bancos_cargados_db.add(banco)

        df_global = pl.DataFrame(movimientos_db).rename({
            "origen": "Origen", "concepto": "Concepto", "documento_referencia": "Documento_Referencia",
            "numero_doc": "Numero_Doc", "ingreso": "Ingreso", "egreso": "Egreso", 
            "categoria_flujo": "Categoria_Flujo", "tercero": "Tercero", "centro_costos": "Centro_Costos",
            "vinculado": "Vinculado"
        }).with_columns(pl.col("fecha").cast(pl.Utf8).str.to_date("%Y-%m-%d", strict=False).alias("Fecha"))

        if self.rutas.get("caja_bancos") and os.path.exists(self.rutas["caja_bancos"]):
            extractor_cb = CajaBancosExtractor(self.rutas.get("caja_bancos"))
            df_cb = extractor_cb.process()
            if not df_cb.is_empty():
                df_global = pl.concat([df_global, df_cb], how="diagonal")

        if "Centro_Costos" in df_global.columns:
            df_global = df_global.with_columns(
                pl.col("Centro_Costos").cast(pl.Utf8).str.extract(r"(\d{5})").replace_strict(MAPEO_CAJAS, default=pl.col("Centro_Costos")).alias("Centro_Costos")
            )

        # -------------------------------------------------------------
        # CORRECCIÓN APLICADA: ENVIAMOS df_global, NO movimientos_db
        # -------------------------------------------------------------
        df_detallado = calcular_detallado(df_global, saldos_iniciales_mes, self.ajustes)
        df_resumen = armar_resumen_gerencial(df_global, df_detallado, self.ajustes)

        return df_global, df_detallado, df_resumen

    def generar_y_guardar_flujo_diario(self) -> int:
        df_global = self.generar_base_consolidada()
        
        registros = []
        if not df_global.is_empty():
            df_base = df_global.filter(
                pl.col("Origen").str.to_uppercase() != "CAJA_BANCOS"
            ).with_columns(
                pl.when(
                    (pl.col("Origen").str.to_uppercase() == "BANCOLOMBIA") &
                    (pl.col("Concepto").fill_null("").str.to_uppercase().str.contains("TRASL ENTRE FONDOS DE VALORES"))
                ).then(pl.lit("Traslado_Salida"))
                .otherwise(pl.col("Categoria_Flujo"))
                .alias("Categoria_Flujo")
            ).with_columns(pl.col("Fecha").cast(pl.Date).cast(pl.Utf8).alias("Fecha_Str"))
            
            registros = df_base.to_dicts()

        fechas_procesadas = set()

        if self.ajustes and "ALIANZA" in self.ajustes:
            ing_extra = self.ajustes["ALIANZA"].get("ingresos", 0.0)
            egr_extra = self.ajustes["ALIANZA"].get("egresos", 0.0)
            
            if ing_extra > 0 or egr_extra > 0:
                if registros:
                    fecha_pdf = min(r["Fecha_Str"] for r in registros if r.get("Fecha_Str") and str(r.get("Fecha_Str")) != "null")
                else:
                    import datetime
                    fechas_bd = self.db.get_fechas_disponibles()
                    if fechas_bd:
                        fecha_pdf = max(fechas_bd)
                    else:
                        fecha_pdf = datetime.date.today().strftime("%Y-%m-%d")

                registros.append({
                    "Fecha_Str": fecha_pdf, "Origen": "ALIANZA", 
                    "Concepto": "AJUSTE MANUAL / ESCANER PDF", "Documento_Referencia": "N/A",
                    "Numero_Doc": "N/A", "Ingreso": ing_extra, "Egreso": egr_extra, 
                    "Categoria_Flujo": "Operacion_Normal", "Tercero": "N/A", "Centro_Costos": "N/A"
                })

        if not registros:
            return 0

        saldos_actuales = {}
        for banco in self.rutas.keys():
            if banco != "caja_bancos":
                saldos_actuales[banco.upper()] = self.db.get_ultimo_saldo(banco.upper())
                if saldos_actuales[banco.upper()] == 0.0:
                    saldos_actuales[banco.upper()] = self.saldos_iniciales.get(banco.upper(), 0.0)

        acumulador_diario = {}
        movimientos_batch = []

        for row in registros:
            fecha_str = row.get("Fecha_Str")
            if not fecha_str or str(fecha_str) == "null":
                continue
                
            fechas_procesadas.add(fecha_str)
            origen = str(row.get("Origen", "")).upper()
            concepto = str(row.get("Concepto", ""))
            doc_ref = str(row.get("Documento_Referencia", ""))
            num_doc = str(row.get("Numero_Doc", "N/A")) 
            ing = float(row.get("Ingreso") or 0.0)
            egr = float(row.get("Egreso") or 0.0)
            cat_flujo = str(row.get("Categoria_Flujo", "Operacion_Normal"))
            tercero = str(row.get("Tercero", "N/A"))
            cco = str(row.get("Centro_Costos") or row.get("NOMBRE_CCO") or "N/A")
            vinculado = str(row.get("Vinculado", ""))

            movimientos_batch.append((fecha_str, origen, concepto, doc_ref, num_doc, ing, egr, cat_flujo, tercero, cco, vinculado))
            
            llave_dia = (fecha_str, origen)
            if llave_dia not in acumulador_diario:
                acumulador_diario[llave_dia] = {"ing": 0.0, "egr": 0.0}
            acumulador_diario[llave_dia]["ing"] += ing
            acumulador_diario[llave_dia]["egr"] += egr

        # Batch insert todos los movimientos en UNA sola transacción
        self.db.guardar_movimientos_batch(movimientos_batch)

        llaves_ordenadas = sorted(acumulador_diario.keys(), key=lambda x: (x[0], x[1]))
        saldos_batch = []
        
        for fecha_str, origen in llaves_ordenadas:
            ing_total = acumulador_diario[(fecha_str, origen)]["ing"]
            egr_total = acumulador_diario[(fecha_str, origen)]["egr"]
            
            saldo_inicial = saldos_actuales.get(origen, 0.0)
            saldo_final = saldo_inicial + ing_total - egr_total
            
            saldos_batch.append((fecha_str, origen, saldo_inicial, saldo_final))
            saldos_actuales[origen] = saldo_final

        # Batch insert todos los saldos en UNA sola transacción
        self.db.guardar_saldos_batch(saldos_batch)

        # Invalidar caches UNA sola vez al final
        self.db._invalidar_caches()

        return len(fechas_procesadas)

    def generar_reporte_detallado(self, df_global: pl.DataFrame) -> pl.DataFrame:
        return calcular_detallado(df_global, self.saldos_iniciales, self.ajustes)

    def generar_resumen_gerencial(self, df_global: pl.DataFrame, df_detallado: pl.DataFrame) -> pd.DataFrame:
        return armar_resumen_gerencial(df_global, df_detallado, self.ajustes)

    def exportar_a_excel(self, df_detallado_pl: pl.DataFrame, df_resumen: pd.DataFrame, ruta_salida: str):
        print(f"Aplicando estilos y exportando reporte a {ruta_salida}...")
        
        pd_detallado = df_detallado_pl.to_pandas()
        
        pd_detallado.columns = ["Banco / Caja", "Saldo Inicial", "Ingresos", "Anulada", "Ingresos de Traslados", "Salidas", "Salidas por Traslados", "Saldo Final"]
        
        with pd.ExcelWriter(ruta_salida, engine='xlsxwriter') as writer:
            pd_detallado.to_excel(writer, sheet_name='Detallado', index=False)
            df_resumen.to_excel(writer, sheet_name='Resumen', index=False)
            
            workbook  = writer.book
            fmt_moneda_base = workbook.add_format({'num_format': '$#,##0'})
            fmt_negrita = workbook.add_format({'bold': True})
            fmt_headers = workbook.add_format({'bold': True, 'bg_color': '#203764', 'font_color': 'white', 'border': 1})
            fmt_totales_detallado = workbook.add_format({'num_format': '$#,##0', 'bold': True, 'bg_color': '#E8E8E8'})
            
            fmt_macro_c = workbook.add_format({'bold': True, 'bg_color': '#1F4E78', 'font_color': 'white'})
            fmt_macro_v = workbook.add_format({'bold': True, 'bg_color': '#1F4E78', 'font_color': 'white', 'num_format': '$#,##0'})
            fmt_in_c = workbook.add_format({'bold': True, 'bg_color': '#E2EFDA', 'font_color': '#375623'})
            fmt_in_v = workbook.add_format({'bold': True, 'bg_color': '#E2EFDA', 'font_color': '#375623', 'num_format': '$#,##0'})
            fmt_out_c = workbook.add_format({'bold': True, 'bg_color': '#FCE4D6', 'font_color': '#C65911'})
            fmt_out_v = workbook.add_format({'bold': True, 'bg_color': '#FCE4D6', 'font_color': '#C65911', 'num_format': '$#,##0'})
            fmt_prov_c = workbook.add_format({'bold': True, 'bg_color': '#DDEBF7', 'font_color': '#2F5597'})
            fmt_prov_v = workbook.add_format({'bold': True, 'bg_color': '#DDEBF7', 'font_color': '#2F5597', 'num_format': '$#,##0'})

            ws_detallado = writer.sheets['Detallado']
            ws_detallado.set_column('A:A', 20, fmt_negrita)
            
            ws_detallado.set_column('B:H', 22, fmt_moneda_base)
            for col_num, value in enumerate(pd_detallado.columns.values):
                ws_detallado.write(0, col_num, value, fmt_headers)
                
            try:
                idx_tb = pd_detallado.index[pd_detallado['Banco / Caja'] == 'TOTAL BANCOS'].tolist()[0]
                idx_tg = pd_detallado.index[pd_detallado['Banco / Caja'] == 'BANCO + CAJA'].tolist()[0]
                ws_detallado.set_row(idx_tb + 1, None, fmt_totales_detallado)
                ws_detallado.set_row(idx_tg + 1, None, fmt_totales_detallado)
            except IndexError:
                pass
            
            ws_resumen = writer.sheets['Resumen']
            ws_resumen.set_column('A:A', 45)
            ws_resumen.set_column('B:B', 20, fmt_moneda_base)
            for col_num, value in enumerate(df_resumen.columns.values):
                ws_resumen.write(0, col_num, value, fmt_headers)
            
            claves_macros = ["Total Ingresos del mes", "Saldo inicial del mes anterior", "Total Disponible", "Total salidas del mes"]
            claves_ingresos = ["DETALLE DE INGRESOS BANCARIOS", "Total Ingresos x Bancos", "DETALLE DE INGRESOS POR CAJA", "Total Ingresos x Caja"]
            claves_salidas = ["DETALLE DE SALIDAS BANCARIAS", "Total Salidas x Bancos", "DETALLE DE SALIDAS POR CAJA", "Total Salidas x Caja", "SALIDAS POR GASTOS OPERACIONALES"]
            claves_proveedores = ["PROVEEDORES", "Pagos por Caja", "Pagos por Bancos", "Total Abonos", "DESGLOSE DE PROVEEDORES (CAJA)", "DESGLOSE DE PROVEEDORES (BANCOS)"]
            
            for row_idx, row_series in df_resumen.iterrows():
                concepto = str(row_series['Concepto']).strip()
                valor = row_series['Valor']
                excel_row = row_idx + 1
                fmt_c, fmt_v = None, None
                
                if concepto in claves_macros: fmt_c, fmt_v = fmt_macro_c, fmt_macro_v
                elif concepto in claves_ingresos: fmt_c, fmt_v = fmt_in_c, fmt_in_v
                elif concepto in claves_salidas: fmt_c, fmt_v = fmt_out_c, fmt_out_v
                elif concepto in claves_proveedores: fmt_c, fmt_v = fmt_prov_c, fmt_prov_v
                
                if fmt_c and fmt_v:
                    ws_resumen.write(excel_row, 0, concepto, fmt_c)
                    if pd.notna(valor): ws_resumen.write(excel_row, 1, valor, fmt_v)
                    else: ws_resumen.write(excel_row, 1, "", fmt_c)