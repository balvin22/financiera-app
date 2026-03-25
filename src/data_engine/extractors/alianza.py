# src.data_engine/extractors/alianza.py
import polars as pl
import pandas as pd
from .base import BaseExtractor

class AlianzaExtractor(BaseExtractor):
    def process(self) -> pl.DataFrame:
        try:
            # 1. El Puente: Buscamos inteligentemente la hoja correcta en el Excel nativo
            try:
                # Si existe "Pag (2)", significa que el analista ya borró la basura de arriba. 
                # Leemos normal SIN skiprows.
                pdf = pd.read_excel(self.filepath, sheet_name="Pag (2)")
            except ValueError:
                # Si usan el extracto original ("Pag"), sí debemos saltar las 5 filas de basura
                pdf = pd.read_excel(self.filepath, sheet_name="Pag", skiprows=5)
            
            # Limpiamos los nombres de las columnas
            pdf.columns = pdf.columns.str.strip()
            
            # Nos quedamos con las columnas útiles para el flujo
            cols_utiles = ["Fecha Transacción", "Concepto", "Beneficiario", "Ingreso", "Egreso"]
            cols_presentes = [col for col in cols_utiles if col in pdf.columns]
            pdf = pdf[cols_presentes].copy()
            
            # 2. Esterilización extrema en Pandas
            for col in ["Ingreso", "Egreso"]:
                if col in cols_presentes:
                    pdf[col] = pd.to_numeric(pdf[col], errors='coerce').fillna(0.0)
                    
            if "Concepto" in pdf.columns: 
                pdf["Concepto"] = pdf["Concepto"].fillna("").astype(str)
            if "Beneficiario" in pdf.columns: 
                pdf["Beneficiario"] = pdf["Beneficiario"].fillna("").astype(str)
                
            # 3. Blindaje de Esquema para Polars
            esquema = {}
            if "Fecha Transacción" in pdf.columns: esquema["Fecha Transacción"] = pl.Utf8
            if "Concepto" in pdf.columns: esquema["Concepto"] = pl.Utf8
            if "Beneficiario" in pdf.columns: esquema["Beneficiario"] = pl.Utf8
            if "Ingreso" in pdf.columns: esquema["Ingreso"] = pl.Float64
            if "Egreso" in pdf.columns: esquema["Egreso"] = pl.Float64

            df = pl.from_pandas(pdf, schema_overrides=esquema)
            
            # Si el analista olvidó crear las columnas de Ingreso/Egreso, las creamos en 0 para que no explote
            for col in ["Ingreso", "Egreso"]:
                if col not in df.columns:
                    df = df.with_columns(pl.lit(0.0).alias(col))

            # 4. LIMPIEZA Y ESTANDARIZACIÓN
            df_clean = (
                df
                .select([
                    # Extraemos los 10 primeros caracteres (YYYY-MM-DD)
                    pl.col("Fecha Transacción").str.slice(0, 10).str.to_date("%Y-%m-%d", strict=False).alias("Fecha"),
                    
                    # Unimos Concepto y Beneficiario para tener todo el contexto
                    pl.concat_str([pl.col("Concepto"), pl.lit(" - "), pl.col("Beneficiario")]).alias("Concepto"),
                    
                    pl.lit("N/A").alias("Documento_Referencia"),
                    
                    pl.col("Ingreso").alias("Ingreso"),
                    pl.col("Egreso").alias("Egreso")
                ])
                .with_columns(pl.lit("ALIANZA").alias("Origen"))
                
                # Filtramos basura (totales o vacíos)
                .filter(pl.col("Fecha").is_not_null() & ((pl.col("Ingreso") != 0.0) | (pl.col("Egreso") != 0.0)))
            )

            # 5. REGLA DE NEGOCIO: La regla de Arpesod (Traslados de Alianza a otro banco)
            # Como vimos en "Din", debemos separar las salidas a ARPESOD de la operación normal.
            # En noviembre son 2 transacciones que suman exactamente los 41.000.000.
            df_final = df_clean.with_columns(
                pl.when(
                    pl.col("Concepto").str.contains(r"(?i)ARPESOD") & (pl.col("Egreso") > 0)
                )
                .then(pl.lit("Traslado_Salida"))
                .otherwise(pl.lit("Operacion_Normal"))
                .alias("Categoria_Flujo")
            )

            return df_final
            
        except Exception as e:
            print(f"Error procesando Alianza ({self.filepath}): {e}")
            return pl.DataFrame({"Fecha": [], "Concepto": [], "Documento_Referencia": [], "Ingreso": [], "Egreso": [], "Origen": [], "Categoria_Flujo": []})

# ==========================================
# Zona de Pruebas
# ==========================================
if __name__ == "__main__":
    # RUTA APUNTANDO AL EXCEL ORIGINAL
    ruta_prueba = "c:/Users/usuario/Desktop/Financiera/5. Mov Alianza ARP 1155 Noviembre  2025.xlsx"
    
    # Asumimos que tienes el archivo disponible
    extractor = AlianzaExtractor(ruta_prueba)
    resultado = extractor.process()
    
    if not resultado.is_empty():
        print("--- Muestra de Datos Limpios (Alianza Fiduciaria) ---")
        print(resultado.head())
        
        # Validaciones Matemáticas
        ingresos_totales = resultado["Ingreso"].sum()
        egresos_operativos = resultado.filter(pl.col("Categoria_Flujo") == "Operacion_Normal")["Egreso"].sum()
        traslados = resultado.filter(pl.col("Categoria_Flujo") == "Traslado_Salida")["Egreso"].sum()
        
        print("\n--- Validación de Cuadre ---")
        print(f"Ingresos Totales:      {ingresos_totales:,.2f} <-- (Debe ser ~1,453,661,286.45)")
        print(f"Egresos Operativos:    {egresos_operativos:,.2f} <-- (Debe ser ~1,404,775,699.53)")
        print(f"Salidas por Traslados: {traslados:,.2f} <-- (Debe ser 41,000,000.00)")
    else:
        print("El DataFrame regresó vacío. Revisa si la hoja en el Excel tiene el formato esperado.")