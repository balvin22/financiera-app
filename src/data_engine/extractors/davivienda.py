# src.data_engine/extractors/davivienda.py
import polars as pl
import pandas as pd
from .base import BaseExtractor

class DaviviendaExtractor(BaseExtractor):
    def process(self) -> pl.DataFrame:
        try:
            # 1. El Puente: Leemos la hoja "Mov" saltando las 2 filas de título
            pdf = pd.read_excel(self.filepath, sheet_name="Mov", skiprows=2)
            
            # Limpiamos los nombres de columnas por si traen espacios
            pdf.columns = pdf.columns.str.strip()
            
            # Nos quedamos estrictamente con las columnas que necesitamos
            cols_utiles = ["Fecha","Tran", "Desc Mot.", "Doc.", "Ingreso", "Egreso"]
            cols_presentes = [col for col in cols_utiles if col in pdf.columns]
            pdf = pdf[cols_presentes].copy()
            
            # Esterilización extrema en Pandas
            for col in cols_presentes:
                if col in ["Ingreso", "Egreso"]:
                    pdf[col] = pd.to_numeric(pdf[col], errors='coerce').fillna(0.0)
                else:
                    # Obligamos a que cualquier valor nulo sea un texto vacío y forzamos a string
                    pdf[col] = pdf[col].fillna("").astype(str)
                    
            # --- EL BLINDAJE FINAL ---
            # Le dictamos el esquema exacto a Polars para que no intente adivinar nada
            esquema = {}
            if "Fecha" in pdf.columns: esquema["Fecha"] = pl.Utf8
            if "Desc Mot." in pdf.columns: esquema["Desc Mot."] = pl.Utf8
            if "Doc." in pdf.columns: esquema["Doc."] = pl.Utf8
            if "Ingreso" in pdf.columns: esquema["Ingreso"] = pl.Float64
            if "Egreso" in pdf.columns: esquema["Egreso"] = pl.Float64

            # 2. Pasamos a Polars usando el schema_overrides
            df = pl.from_pandas(pdf, schema_overrides=esquema)

            # 3. LIMPIEZA Y ESTANDARIZACIÓN
            df_clean = (
                df
                .select([
                    # Extraemos los primeros 10 caracteres por si acaso (2025-11-30) y lo pasamos a Fecha
                    pl.col("Fecha").str.slice(0, 10).str.to_date("%Y-%m-%d", strict=False).alias("Fecha"),
                    
                    pl.col("Desc Mot.").str.strip_chars().alias("Concepto"),
                    pl.col("Doc.").alias("Documento_Referencia"),
                    
                    pl.col("Ingreso").alias("Ingreso"),
                    pl.col("Egreso").alias("Egreso")
                ])
                .with_columns(pl.lit("DAVIVIENDA").alias("Origen"))
                
                # Filtramos las filas basuras
                .filter(pl.col("Fecha").is_not_null() & ((pl.col("Ingreso") > 0) | (pl.col("Egreso") > 0)))
            )

            # 4. REGLA DE NEGOCIO (Separar los Traslados)
            df_final = df_clean.with_columns(
                pl.when(pl.col("Concepto").str.contains(r"(?i)Dcto por Transferencia de Fondos"))
                .then(pl.lit("Traslado_Salida"))
                .otherwise(pl.lit("Operacion_Normal"))
                .alias("Categoria_Flujo")
            )

            return df_final
            
        except Exception as e:
            print(f"Error procesando Davivienda ({self.filepath}): {e}")
            import traceback
            traceback.print_exc() # Esto nos mostrará el error completo si vuelve a fallar
            return pl.DataFrame({"Fecha": [], "Concepto": [], "Documento_Referencia": [], "Ingreso": [], "Egreso": [], "Origen": [], "Categoria_Flujo": []})

# ==========================================
# Zona de Pruebas
# ==========================================
if __name__ == "__main__":
    ruta_prueba = "c:/Users/usuario/Desktop/Financiera/2. Mov Davivienda Noviembre ARP.xls.xlsx"
    
    extractor = DaviviendaExtractor(ruta_prueba)
    resultado = extractor.process()
    
    if not resultado.is_empty():
        print("--- Muestra de Datos Limpios (Davivienda) ---")
        print(resultado.head())
        
        # Validaciones Matemáticas
        ingresos_totales = resultado["Ingreso"].sum()
        egresos_operativos = resultado.filter(pl.col("Categoria_Flujo") == "Operacion_Normal")["Egreso"].sum()
        traslados = resultado.filter(pl.col("Categoria_Flujo") == "Traslado_Salida")["Egreso"].sum()
        
        print("\n--- Validación de Cuadre ---")
        print(f"Ingresos Totales:      {ingresos_totales:,.2f} <-- (Debe ser 434,448,292)")
        print(f"Egresos Operativos:    {egresos_operativos:,.2f} <-- (Debe ser 110,186,141.60)")
        print(f"Salidas por Traslados: {traslados:,.2f} <-- (Debe ser 234,690,000)")
    else:
        print("El DataFrame regresó vacío.")