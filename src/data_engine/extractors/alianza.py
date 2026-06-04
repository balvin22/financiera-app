# src/data_engine/extractors/alianza.py
import polars as pl
import pandas as pd
import re
from .base import BaseExtractor

class AlianzaExtractor(BaseExtractor):
    def process(self) -> pl.DataFrame:
        try:
            try:
                pdf = pd.read_excel(self.filepath, sheet_name=0)
                if not {"Fecha Transacción", "Concepto", "Total", "Ingreso", "Egreso"}.intersection(pdf.columns):
                    raise ValueError("Formato no detectado, probando con skiprows")
            except (ValueError, Exception):
                pdf = pd.read_excel(self.filepath, sheet_name=0, skiprows=5)
            
            pdf.columns = pdf.columns.str.strip()
            cols_presentes = pdf.columns.tolist()

            def limpiar_valor(val):
                if pd.isna(val): return 0.0
                if isinstance(val, (int, float)): return float(val)
                v = str(val).strip()
                v = re.sub(r'[\$\s\xa0]', '', v)
                
                if '.' in v and ',' in v:
                    if v.rfind('.') > v.rfind(','):
                        v = v.replace(',', '')
                    else:
                        v = v.replace('.', '').replace(',', '.')
                elif ',' in v:
                    if len(v.split(',')[-1]) <= 2:
                        v = v.replace(',', '.')
                    else: 
                        v = v.replace(',', '')
                try:
                    return float(v)
                except ValueError:
                    return 0.0

            tiene_separados = "Ingreso" in cols_presentes and "Egreso" in cols_presentes
            tiene_valor = "Total" in cols_presentes

            if tiene_separados:
                pdf["Ingreso"] = pdf["Ingreso"].apply(limpiar_valor)
                pdf["Egreso"] = pdf["Egreso"].apply(limpiar_valor)
            elif tiene_valor:
                pdf["Total"] = pdf["Total"].apply(limpiar_valor)
            else:
                print("❌ Alianza: No se encontraron columnas.")
                return pl.DataFrame()

            # Asegurar textos
            if "Concepto" not in pdf.columns: pdf["Concepto"] = ""
            if "Beneficiario" not in pdf.columns: pdf["Beneficiario"] = ""
            
            pdf["Concepto"] = pdf["Concepto"].fillna("").astype(str)
            pdf["Beneficiario"] = pdf["Beneficiario"].fillna("").astype(str)
                
            df = pl.from_pandas(pdf)
            
            if tiene_separados:
                df_calc = df.with_columns([pl.col("Ingreso"), pl.col("Egreso")])
            else:
                df_calc = df.with_columns([
                    pl.when(pl.col("Total") > 0).then(pl.col("Total")).otherwise(0.0).alias("Ingreso"),
                    pl.when(pl.col("Total") < 0).then(pl.col("Total").abs()).otherwise(0.0).alias("Egreso")
                ])

            # =========================================================
            # REGLAS DE NEGOCIO BLINDADAS
            # =========================================================
            df_final = (
                df_calc
                .with_columns([
                    # VALIDACIÓN DIRECTA SOBRE AMBAS COLUMNAS
                    pl.when(
                        pl.col("Concepto").str.to_uppercase().str.contains("ANULA") | 
                        pl.col("Beneficiario").str.to_uppercase().str.contains("ANULA")
                    )
                    .then(pl.lit("Anulacion"))
                    .when(pl.col("Beneficiario").str.to_uppercase().str.contains("ARPESOD") & (pl.col("Egreso") > 0))
                    .then(pl.lit("Traslado_Salida"))
                    .otherwise(pl.lit("Operacion_Normal"))
                    .alias("Categoria_Flujo"),
                    
                    pl.concat_str([pl.col("Concepto"), pl.lit(" - "), pl.col("Beneficiario")]).alias("Texto_Completo")
                ])
                .select([
                    pl.col("Fecha Transacción").cast(pl.Utf8).str.slice(0, 10).str.to_date("%Y-%m-%d", strict=False).alias("Fecha"),
                    pl.col("Texto_Completo").alias("Concepto"),
                    pl.lit("N/A").alias("Documento_Referencia"),
                    pl.col("Ingreso"),
                    pl.col("Egreso"),
                    pl.col("Categoria_Flujo") 
                ])
                .with_columns(pl.lit("ALIANZA").alias("Origen"))
                .filter(pl.col("Fecha").is_not_null() & ((pl.col("Ingreso") != 0.0) | (pl.col("Egreso") != 0.0)))
            )

            return df_final
            
        except Exception as e:
            print(f"Error procesando Alianza ({self.filepath}): {e}")
            return pl.DataFrame({"Fecha": [], "Concepto": [], "Documento_Referencia": [], "Ingreso": [], "Egreso": [], "Origen": [], "Categoria_Flujo": []})