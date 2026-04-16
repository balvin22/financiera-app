# src/data_engine/reports/flujo_efectivo.py
import polars as pl
import pandas as pd
import xlsxwriter
import sqlite3
import re
import os
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
        self.rutas = rutas_archivos
        self.ajustes = ajustes_manuales or {}
        self.saldos_iniciales = saldos_iniciales or {}
        
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

        # MAGIA DE AGRUPACIÓN (MAPEO AUTOMÁTICO)
        if "Centro_Costos" in df_global.columns:
            df_global = df_global.with_columns(
                pl.col("Centro_Costos")
                .cast(pl.Utf8)
                .str.extract(r"(\d{5})")
                .replace_strict(MAPEO_CAJAS, default=pl.col("Centro_Costos"))
                .alias("Centro_Costos")
            )
            
        return df_global

    def generar_y_guardar_flujo_diario(self) -> int:
        """
        Procesa el flujo diario con Acumuladores de Descuento para asegurar que 
        cuadre matemáticamente (al centavo) con los KPIs del Dashboard Mensual.
        """
        df_global = self.generar_base_consolidada()
        if df_global.is_empty():
            return 0

        # 1. Base limpia: Excluimos entidad CAJA_BANCOS y aplicamos reglas de Extractor
        df_base = df_global.filter(
            pl.col("Origen").str.to_uppercase() != "CAJA_BANCOS"
        ).with_columns(
            pl.when(
                (pl.col("Origen").str.to_uppercase() == "BANCOLOMBIA") &
                (pl.col("Concepto").str.to_uppercase().str.contains("TRASL ENTRE FONDOS DE VALORES"))
            ).then(pl.lit("Traslado_Salida"))
            .otherwise(pl.col("Categoria_Flujo"))
            .alias("Categoria_Flujo")
        ).with_columns(pl.col("Fecha").cast(pl.Date).cast(pl.Utf8).alias("Fecha_Str"))

        # 2. Ingresos Brutos (Excluyendo Entradas por Traslado, pero dejando Don Diego)
        df_ingresos = df_base.filter(
            pl.col("Categoria_Flujo") != "Traslado_Entrada"
        ).group_by(["Fecha_Str", "Origen"]).agg(
            pl.col("Ingreso").sum().alias("Ingreso_Bruto")
        ).to_pandas()

        # 3. Egresos Operativos Brutos (Excluyendo traslados y Don Diego)
        df_egresos = df_base.filter(
            ~pl.col("Categoria_Flujo").is_in(["Traslado_Salida", "Traslado_Entrada", "Ajuste_Don_Diego"])
        ).group_by(["Fecha_Str", "Origen"]).agg(
            pl.col("Egreso").sum().alias("Total_Egreso_Bruto")
        ).to_pandas()

        # Unimos Ingresos y Egresos
        df_diario = pd.merge(df_ingresos, df_egresos, on=["Fecha_Str", "Origen"], how="outer").fillna(0)

        # 4. Descuentos a aplicar para netear la contabilidad
        df_traslados = df_base.filter(
            pl.col("Categoria_Flujo") == "Traslado_Salida"
        ).group_by(["Fecha_Str"]).agg(
            pl.col("Egreso").sum().alias("Traslado_A_Descontar")
        ).to_pandas()

        df_ajuste_dd = df_base.filter(
            (pl.col("Origen").str.to_uppercase() == "CAJA") &
            (pl.col("Categoria_Flujo") == "Ajuste_Don_Diego")
        ).group_by(["Fecha_Str"]).agg(
            pl.col("Ingreso").sum().alias("Ajuste_DD_A_Descontar")
        ).to_pandas()

        df_diario = pd.merge(df_diario, df_traslados, on="Fecha_Str", how="left").fillna(0)
        df_diario = pd.merge(df_diario, df_ajuste_dd, on="Fecha_Str", how="left").fillna(0)
        df_diario = df_diario.sort_values(["Fecha_Str", "Ingreso_Bruto"], ascending=[True, False]).reset_index(drop=True)

        df_diario["Total_Ingreso"] = df_diario["Ingreso_Bruto"]
        df_diario["Total_Egreso"] = df_diario["Total_Egreso_Bruto"]

        # 5. APLICAR DESCUENTOS EN CASCADA (El secreto para que cuadre exacto)
        desc_ingreso_acumulado = 0.0
        desc_egreso_acumulado = 0.0
        
        for fecha in df_diario["Fecha_Str"].unique():
            indices = df_diario[df_diario["Fecha_Str"] == fecha].index
            if len(indices) == 0: continue
            
            # --- Descontar Traslados de los Ingresos ---
            desc_ingreso = df_diario.at[indices[0], "Traslado_A_Descontar"] + desc_ingreso_acumulado
            if desc_ingreso > 0:
                for idx in indices:
                    bruto = df_diario.at[idx, "Total_Ingreso"]
                    if bruto > 0 and desc_ingreso > 0:
                        quitar = min(bruto, desc_ingreso)
                        df_diario.at[idx, "Total_Ingreso"] = bruto - quitar
                        desc_ingreso -= quitar
            desc_ingreso_acumulado = desc_ingreso # Lo que no se pudo descontar, pasa a mañana
            
            # --- Descontar Ajuste_Don_Diego de los Egresos (solo CAJA) ---
            desc_egreso = df_diario.at[indices[0], "Ajuste_DD_A_Descontar"] + desc_egreso_acumulado
            if desc_egreso > 0:
                mask_caja = (df_diario["Fecha_Str"] == fecha) & (df_diario["Origen"].str.upper() == "CAJA")
                if mask_caja.any():
                    idx_caja = df_diario[mask_caja].index[0]
                    actual_egr = df_diario.at[idx_caja, "Total_Egreso"]
                    if actual_egr > 0:
                        quitar_egr = min(actual_egr, desc_egreso)
                        df_diario.at[idx_caja, "Total_Egreso"] = actual_egr - quitar_egr
                        desc_egreso -= quitar_egr
            desc_egreso_acumulado = desc_egreso

        # 6. Inyección de Ajustes Manuales (PDFs de Alianza y TextFields)
        if self.ajustes and "ALIANZA" in self.ajustes and not df_diario.empty:
            ing_extra = self.ajustes["ALIANZA"].get("ingresos", 0.0)
            egr_extra = self.ajustes["ALIANZA"].get("egresos", 0.0)
            
            if ing_extra > 0 or egr_extra > 0:
                primer_dia = df_diario["Fecha_Str"].min()
                mask_alianza = (df_diario["Fecha_Str"] == primer_dia) & (df_diario["Origen"].str.upper() == "ALIANZA")
                
                if mask_alianza.any():
                    idx_alianza = df_diario[mask_alianza].index[0]
                    df_diario.at[idx_alianza, "Total_Ingreso"] += ing_extra
                    df_diario.at[idx_alianza, "Total_Egreso"] += egr_extra
                else:
                    nueva_fila = pd.DataFrame([{
                        "Fecha_Str": primer_dia, "Origen": "ALIANZA",
                        "Total_Ingreso": ing_extra, "Total_Egreso": egr_extra
                    }])
                    df_diario = pd.concat([df_diario, nueva_fila], ignore_index=True)

        # 7. Guardado en SQLite
        fechas_procesadas = set()
        with sqlite3.connect("local_cache/maestros.db") as conn:
            conn.execute("DELETE FROM flujos_diarios")
            for _, row in df_diario.iterrows():
                fecha_str = row["Fecha_Str"]
                banco = str(row["Origen"]).upper()
                ing = float(row["Total_Ingreso"])
                egr = float(row["Total_Egreso"])
                saldo_inicial = self.saldos_iniciales.get(banco, 0.0)

                # Guardamos si hubo movimiento o si el banco tiene saldo inicial
                if pd.notna(fecha_str) and str(fecha_str) != "null" and (ing > 0 or egr > 0 or saldo_inicial > 0):
                    fechas_procesadas.add(fecha_str)
                    conn.execute('''
                        INSERT INTO flujos_diarios (fecha, banco, saldo_inicial, ingresos, egresos)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (fecha_str, banco, saldo_inicial, ing, egr))
            conn.commit()

        return len(fechas_procesadas)

    def generar_reporte_detallado(self, df_global: pl.DataFrame) -> pl.DataFrame:
        return calcular_detallado(df_global, self.saldos_iniciales, self.ajustes)

    def generar_resumen_gerencial(self, df_global: pl.DataFrame, df_detallado: pl.DataFrame) -> pd.DataFrame:
        return armar_resumen_gerencial(df_global, df_detallado, self.ajustes)

    def exportar_a_excel(self, df_detallado_pl: pl.DataFrame, df_resumen: pd.DataFrame, ruta_salida: str):
        print(f"Aplicando estilos y exportando reporte a {ruta_salida}...")
        
        pd_detallado = df_detallado_pl.to_pandas()
        pd_detallado.columns = ["Banco / Caja", "Saldo Inicial", "Ingresos", "Ingresos de Traslados", "Salidas", "Salidas por Traslados", "Saldo Final"]
        
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
            ws_detallado.set_column('B:G', 22, fmt_moneda_base)
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