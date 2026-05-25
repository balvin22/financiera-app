# src/data_engine/extractors/caja_bancos.py
import polars as pl
import pandas as pd
from .base import BaseExtractor

class CajaBancosExtractor(BaseExtractor):
    def process(self) -> pl.DataFrame:
        try:
            if self.filepath.lower().endswith('.csv'):
                pdf = pd.read_csv(self.filepath, sep=None, engine='python', encoding='latin1')
            else:
                pdf = pd.read_excel(self.filepath, sheet_name=0)
            
            pdf.columns = pdf.columns.str.strip().str.upper()
            
            # Aseguramos columnas base para evitar errores
            if "MCNFECHA" not in pdf.columns and "FECHA" not in pdf.columns:
                pdf["FECHA"] = None
            if "MCNDETALLE" not in pdf.columns and "DETALLE" not in pdf.columns:
                pdf["MCNDETALLE"] = ""
            if "MCNTIPODOC" not in pdf.columns and "TIPO" not in pdf.columns:
                pdf["MCNTIPODOC"] = ""
            if "VINNOMBRE" not in pdf.columns:
                pdf["VINNOMBRE"] = ""
            if "MCNVALCRED" not in pdf.columns:
                pdf["MCNVALCRED"] = 0.0
                
            df = pl.from_pandas(pdf)

            # --- MAGIA REGEX: ATRAPA DISLEXIA Y ERRORES COMUNES ---
            patron_libranza = r"(?i)LIBRAN[A-Z]*A|LIRBAN[A-Z]*A|LIBRAM[A-Z]*A|LIBRANZ|LIBRANS"
            patron_aportes = r"(?i)APORT[E-S]|APORTT|APORTE|APORTES"
            
            col_fecha = "MCNFECHA" if "MCNFECHA" in pdf.columns else "FECHA"
            col_detalle = "MCNDETALLE" if "MCNDETALLE" in pdf.columns else "DETALLE"
            col_doc = "MCNTIPODOC" if "MCNTIPODOC" in pdf.columns else "TIPO"

            df_clean = (
                df
                .filter(
                    (
                        (pl.col(col_doc).cast(pl.Utf8).str.strip_chars().str.to_uppercase().str.starts_with("EB"))
                    ) | (
                        pl.col(col_detalle).cast(pl.Utf8).str.contains(patron_libranza)
                    ) | (
                        pl.col("VINNOMBRE").cast(pl.Utf8).str.contains(patron_aportes)
                    )
                )
                .select([
                    pl.col(col_fecha).cast(pl.Date, strict=False).alias("Fecha"),
                    pl.col(col_detalle).cast(pl.Utf8).fill_null("").alias("Concepto"),
                    pl.col(col_doc).cast(pl.Utf8).fill_null("").alias("Documento_Referencia"),
                    pl.lit(0.0).alias("Ingreso"),
                    pl.col("MCNVALCRED").cast(pl.Float64, strict=False).fill_null(0.0).alias("Egreso"),
                    pl.col("VINNOMBRE").cast(pl.Utf8).fill_null("SIN TERCERO").alias("Tercero"),
                    pl.lit("N/A").alias("NOMBRE_CCO"),
                    pl.col("MCNVINCULA").cast(pl.Utf8).fill_null("").alias("Codigo_Proveedor")
                ])
                .with_columns(
                    pl.lit("CAJA_BANCOS").alias("Origen"),
                    pl.when(pl.col("Concepto").str.contains(patron_libranza))
                      .then(pl.lit("Libranzas"))
                      .when(pl.col("Tercero").str.contains(patron_aportes))
                      .then(pl.lit("Seguridad Social"))
                      .otherwise(pl.lit("Operacion_Normal"))
                      .alias("Categoria_Flujo")
                )
            )

            return df_clean
            
        except Exception as e:
            print(f"Error procesando Caja Bancos ({self.filepath}): {e}")
            return pl.DataFrame({"Fecha": [], "Concepto": [], "Documento_Referencia": [], "Ingreso": [], "Egreso": [], "Origen": [], "Categoria_Flujo": [], "Tercero": [], "NOMBRE_CCO": [], "Codigo_Proveedor": []})