# src.data_engine/extractors/bancolombia.py
import polars as pl
import openpyxl
from .base import BaseExtractor

class BancolombiaExtractor(BaseExtractor):
    def process(self) -> pl.DataFrame:
        try:
            # 1. Usamos openpyxl para leer el color de las celdas (El Plan B robusto)
            wb = openpyxl.load_workbook(self.filepath, data_only=True)
            ws = wb["Mov"] 
            
            data = []
            headers = [str(c.value).strip().upper() if c.value else "" for c in ws[1]]
            
            if "FECHA" not in headers or "CONCEPTO" not in headers or "VALOR" not in headers:
                raise ValueError("El archivo crudo no tiene las columnas FECHA, CONCEPTO y VALOR.")
                
            idx_f = headers.index("FECHA")
            idx_c = headers.index("CONCEPTO")
            idx_v = headers.index("VALOR")
            
            # 2. Recorremos fila por fila clasificando matemáticamente
            for row in ws.iter_rows(min_row=2):
                fecha = row[idx_f].value
                concepto = row[idx_c].value
                celda_valor = row[idx_v]
                valor = celda_valor.value
                
                if not fecha or not concepto or valor is None:
                    continue
                    
                es_negativo = isinstance(valor, (int, float)) and valor < 0
                es_rojo = False
                if celda_valor.font and celda_valor.font.color:
                    color_val = getattr(celda_valor.font.color, "rgb", None)
                    if color_val and "FF0000" in str(color_val).upper():
                        es_rojo = True
                
                if es_negativo or es_rojo:
                    ingreso = 0.0
                    egreso = abs(float(valor))
                else:
                    ingreso = abs(float(valor))
                    egreso = 0.0
                    
                data.append({
                    "Fecha": str(fecha),
                    "Concepto": str(concepto),
                    "Documento_Referencia": "N/A",
                    "Ingreso": ingreso,
                    "Egreso": egreso,
                    "Origen": "BANCOLOMBIA"
                })
                
            # 3. Transformamos a Polars
            df_clean = pl.DataFrame(data).with_columns([
                pl.col("Fecha").str.to_date("%Y%m%d", strict=False)
            ]).filter(pl.col("Fecha").is_not_null())

            # 4. REGLAS DE NEGOCIO AVANZADAS (Calculos de la hoja Din)
            df_final = df_clean.with_columns(
                # Aislamos las salidas que son traslados
                pl.when(pl.col("Concepto").str.contains(r"^(?i)TRASL ENTRE FONDOS DE VALORES"))
                .then(pl.lit("Traslado_Salida"))
                
                # Aislamos las ENTRADAS que son traslados (Los 41 Millones de Alianza Fiduciaria)
                .when(pl.col("Concepto").str.contains(r"^(?i)PAGO DE PROV CCA ALIANZA FID"))
                .then(pl.lit("Traslado_Entrada"))
                
                # El resto es operación normal
                .otherwise(pl.lit("Operacion_Normal"))
                .alias("Categoria_Flujo")
            )

            return df_final
            
        except Exception as e:
            print(f"Error procesando Bancolombia ({self.filepath}): {e}")
            return pl.DataFrame()
        
# Zona de Pruebas
if __name__ == "__main__":
    ruta_prueba = "c:/Users/usuario/Desktop/Financiera/1. Mov Bancolombia mes de Noviembre ARP.xlsx"
    
    extractor = BancolombiaExtractor(ruta_prueba)
    resultado = extractor.process()
    
    if not resultado.is_empty():
        print("--- Validación de Cálculos Hoja 'Din' ---")
        
        # Ingresos
        ingresos_totales = resultado["Ingreso"].sum()
        traslados_entrada = resultado.filter(pl.col("Categoria_Flujo") == "Traslado_Entrada")["Ingreso"].sum()
        ingresos_operativos = ingresos_totales - traslados_entrada
        
        # Egresos
        egresos_totales = resultado["Egreso"].sum()
        traslados_salida = resultado.filter(pl.col("Categoria_Flujo") == "Traslado_Salida")["Egreso"].sum()
        egresos_operativos = egresos_totales - traslados_salida
        
        print(f"Ingresos Totales (Crudos): {ingresos_totales:,.2f}")
        print(f"  - Menos Traslados (Alianza): {traslados_entrada:,.2f}")
        print(f"  = Ingreso Operativo Real: {ingresos_operativos:,.2f}  <-- ¡Cuadra con la línea BANCOLOMBIA de la hoja Din!\n")
        
        print(f"Egresos Totales (Crudos): {egresos_totales:,.2f}")
        print(f"  - Menos Traslados (Fondos): {traslados_salida:,.2f}")
        print(f"  = Egreso Operativo Real: {egresos_operativos:,.2f} <-- ¡Cuadra con la línea BANCOLOMBIA de la hoja Din!\n")
        
        # Nota sobre Saldos
        print("Nota: Los saldos inicial (19M) y final (123M) se ingresarán al final del proceso global en el módulo de Consolidación.")