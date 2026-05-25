# src.data_engine/extractors/davivienda.py
import polars as pl
import pandas as pd
from .base import BaseExtractor

class DaviviendaExtractor(BaseExtractor):
    def process(self) -> pl.DataFrame:
        try:
            # 1. El Puente: Leemos la hoja "Mov" saltando las 2 filas de título
            pdf = pd.read_excel(self.filepath, sheet_name=0, skiprows=2)
            
            # Limpiamos los nombres de columnas por si traen espacios
            pdf.columns = pdf.columns.str.strip()
            
            # ACTUALIZADO: Buscamos las nuevas columnas (Tran y Valor Total)
            cols_utiles = ["Fecha", "Tran", "Desc Mot.", "Doc.", "Valor Total"]
            cols_presentes = [col for col in cols_utiles if col in pdf.columns]
            pdf = pdf[cols_presentes].copy()
            
            # Esterilización en Pandas
            if "Valor Total" in pdf.columns:
                pdf["Valor Total"] = pd.to_numeric(pdf["Valor Total"], errors='coerce').fillna(0.0)
            else:
                pdf["Valor Total"] = 0.0

            for col in ["Fecha", "Tran", "Desc Mot.", "Doc."]:
                if col in pdf.columns:
                    pdf[col] = pdf[col].fillna("").astype(str)
                    
            # --- BLINDAJE DE ESQUEMA PARA POLARS ---
            esquema = {}
            if "Fecha" in pdf.columns: esquema["Fecha"] = pl.Utf8
            if "Tran" in pdf.columns: esquema["Tran"] = pl.Utf8
            if "Desc Mot." in pdf.columns: esquema["Desc Mot."] = pl.Utf8
            if "Doc." in pdf.columns: esquema["Doc."] = pl.Utf8
            if "Valor Total" in pdf.columns: esquema["Valor Total"] = pl.Float64

            # 2. Pasamos a Polars
            df = pl.from_pandas(pdf, schema_overrides=esquema)

            # Evitar errores si falta alguna columna en el archivo original
            if "Tran" not in df.columns: df = df.with_columns(pl.lit("").alias("Tran"))
            if "Valor Total" not in df.columns: df = df.with_columns(pl.lit(0.0).alias("Valor Total"))

            # 3. LIMPIEZA Y LÓGICA DE INGRESOS/EGRESOS
            df_clean = (
                df
                .with_columns([
                    # LÓGICA DE NOTAS:
                    # Si Tran contiene "Notas Credito" (o derivados), es Ingreso.
                    pl.when(pl.col("Tran").str.contains(r"(?i)Notas\s*Cr[eé]dito"))
                      .then(pl.col("Valor Total"))
                      .otherwise(0.0)
                      .alias("Ingreso"),
                      
                    # Si Tran contiene "Notas Debito" (o derivados), es Egreso.
                    pl.when(pl.col("Tran").str.contains(r"(?i)Notas\s*D[eé]bito"))
                      .then(pl.col("Valor Total").abs()) # Lo volvemos positivo
                      .otherwise(0.0)
                      .alias("Egreso")
                ])
                .select([
                    # Extraemos los primeros 10 caracteres (YYYY-MM-DD)
                    pl.col("Fecha").str.slice(0, 10).str.to_date("%Y-%m-%d", strict=False).alias("Fecha"),
                    
                    pl.col("Desc Mot.").str.strip_chars().alias("Concepto"),
                    pl.col("Doc.").alias("Documento_Referencia"),
                    
                    pl.col("Ingreso"),
                    pl.col("Egreso")
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
            return pl.DataFrame({"Fecha": [], "Concepto": [], "Documento_Referencia": [], "Ingreso": [], "Egreso": [], "Origen": [], "Categoria_Flujo": []})