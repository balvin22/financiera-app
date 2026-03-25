# src.data_engine/reports/flujo_efectivo.py
import polars as pl
import pandas as pd
import xlsxwriter
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

    def generar_reporte_detallado(self, df_global: pl.DataFrame) -> pl.DataFrame:
        return calcular_detallado(df_global, self.saldos_iniciales, self.ajustes)

    def generar_resumen_gerencial(self, df_global: pl.DataFrame, df_detallado: pl.DataFrame) -> pd.DataFrame:
        # Le pasamos los ajustes para que el resumen sepa exactamente cuánto fue el ingreso puro de Alianza
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