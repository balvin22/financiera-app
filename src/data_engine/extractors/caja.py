# src.data_engine/extractors/caja.py
import polars as pl
import pandas as pd
from .base import BaseExtractor

class CajaExtractor(BaseExtractor):
    def process(self) -> pl.DataFrame:
        try:
            # 1. El Puente: Leemos la hoja "Mov" con Pandas
            pdf = pd.read_excel(self.filepath, sheet_name="Mov")
            
            # Limpiamos los nombres de columnas y aseguramos el formato de las fechas
            pdf.columns = pdf.columns.str.strip().str.upper()
            if "FECHA" in pdf.columns:
                pdf["FECHA"] = pd.to_datetime(pdf["FECHA"], errors='coerce').dt.date
                
            # Aseguramos que la columna TIPO (nuestra llave principal) sea texto
            if "TIPO" in pdf.columns:
                pdf["TIPO"] = pdf["TIPO"].astype(str).str.strip().str.upper()
                
            # 2. Pasamos a Polars
            df = pl.from_pandas(pdf)

            # 3. LIMPIEZA DE DATOS (El "Basurero" Contable)
            df_clean = (
                df
                .filter(
                    # Eliminamos las filas que cumplan estas condiciones de basura:
                    ~(
                        (pl.col("TIPO").str.starts_with("C") & ~pl.col("TIPO").str.starts_with("CB")) |
                        pl.col("TIPO").str.starts_with("J") |
                        pl.col("TIPO").str.starts_with("RP") |
                        pl.col("TIPO").str.starts_with("PC")
                    )
                )
                .select([
                    pl.col("FECHA").cast(pl.Date, strict=False).alias("Fecha"),
                    pl.col("DETALLE").cast(pl.Utf8).alias("Concepto"),
                    pl.col("TIPO").cast(pl.Utf8).alias("Documento_Referencia"),
                    
                    pl.col("DEBITO").cast(pl.Float64, strict=False).fill_null(0.0).alias("Ingreso"),
                    pl.col("CREDITO").cast(pl.Float64, strict=False).fill_null(0.0).alias("Egreso"),
                    
                    # ATRAPAMOS EL TERCERO
                    pl.col("NOMBRE").cast(pl.Utf8, strict=False).fill_null("SIN TERCERO").alias("Tercero"),
                    
                    # === EL CAMBIO CLAVE ===
                    # Tomamos el número de CCOSTO, lo convertimos a texto y lo llamamos NOMBRE_CCO
                    # Así engañamos al sistema para que le pase los números al diccionario traductor
                    pl.col("CCOSTO").cast(pl.Utf8, strict=False).fill_null("N/A").alias("NOMBRE_CCO")
                ])
                .with_columns(pl.lit("CAJA").alias("Origen"))
                .filter(pl.col("Fecha").is_not_null())
            )

            # 4. REGLAS DE NEGOCIO (Clasificación de Traslados y Reglas Especiales)
            df_final = df_clean.with_columns(
                pl.when(pl.col("Documento_Referencia").str.starts_with("CB"))
                .then(pl.lit("Traslado_Salida"))
                .when(
                    pl.col("Documento_Referencia").str.starts_with("RD") & 
                    pl.col("Concepto").str.to_uppercase().str.contains("DIEGO")
                )
                .then(pl.lit("Ajuste_Don_Diego"))
                .otherwise(pl.lit("Operacion_Normal"))
                .alias("Categoria_Flujo")
            )

            return df_final
            
        except Exception as e:
            print(f"Error procesando Caja ({self.filepath}): {e}")
            return pl.DataFrame({"Fecha": [], "Concepto": [], "Documento_Referencia": [], "Ingreso": [], "Egreso": [], "Origen": [], "Categoria_Flujo": [], "Tercero": [], "NOMBRE_CCO": []})