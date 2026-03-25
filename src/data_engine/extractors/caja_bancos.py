# src.data_engine/extractors/caja_bancos.py
import polars as pl
import pandas as pd
import os
from .base import BaseExtractor

def cargar_proveedores():
    """Carga la lista de proveedores desde el Excel en local_cache."""
    lista = []
    ruta = "local_cache/proveedores.xlsx"
    if os.path.exists(ruta):
        try:
            df = pd.read_excel(ruta, header=None)
            for _, row in df.iterrows():
                if len(row) >= 2:
                    codigo = str(row[0]).strip()
                    nombre = str(row[1]).strip().upper().replace('"', '')
                    if codigo.isdigit() and len(codigo) > 4 and len(nombre) > 3:
                        lista.append(nombre)
        except Exception as e:
            print(f"Advertencia: No se pudo cargar proveedores - {e}")
    return lista

class CajaBancosExtractor(BaseExtractor):
    def process(self) -> pl.DataFrame:
        try:
            if self.filepath.lower().endswith('.csv'):
                pdf = pd.read_csv(self.filepath, sep=None, engine='python', encoding='latin1')
            else:
                pdf = pd.read_excel(self.filepath, sheet_name="Mov")
            
            pdf.columns = pdf.columns.str.strip().str.upper()
            df = pl.from_pandas(pdf)

            proveedores_permitidos = cargar_proveedores()

            df_clean = (
                df
                .filter(
                    (pl.col("MCNTIPODOC").cast(pl.Utf8).str.strip_chars().str.to_uppercase() == "EB09") &
                    (pl.col("VINNOMBRE").cast(pl.Utf8).str.strip_chars().str.to_uppercase().is_in(proveedores_permitidos))
                )
                .select([
                    pl.col("VINNOMBRE").cast(pl.Utf8).alias("Tercero"),
                    pl.col("MCNVALCRED").cast(pl.Float64, strict=False).fill_null(0.0).alias("Egreso")
                ])
                .with_columns(
                    pl.lit("CAJA_BANCOS").alias("Origen"),
                    pl.lit("Pagos_Por_Bancos").alias("Categoria_Flujo")
                )
            )

            return df_clean
            
        except Exception as e:
            print(f"Error procesando Caja Bancos ({self.filepath}): {e}")
            return pl.DataFrame({"Tercero": [], "Egreso": [], "Origen": [], "Categoria_Flujo": []})