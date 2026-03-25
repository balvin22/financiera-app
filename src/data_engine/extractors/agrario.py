# src.data_engine/extractors/agrario.py
import polars as pl
import pandas as pd
from src.data_engine.extractors.base import BaseExtractor

class AgrarioExtractor(BaseExtractor):
    def process(self) -> pl.DataFrame:
        try:
            # 1. El Puente: Leemos la primera hoja ("Pag"), saltando 10 filas de encabezados inútiles
            try:
                pdf = pd.read_excel(self.filepath, sheet_name="Pag", skiprows=10)
            except ValueError:
                # Si por algún motivo le cambian el nombre a la hoja, leemos la primera por defecto
                pdf = pd.read_excel(self.filepath, sheet_name=0, skiprows=10)
            
            # Limpiamos los nombres de columnas
            pdf.columns = pdf.columns.str.strip()
            
            # Seleccionamos estrictamente lo que necesitamos
            cols_utiles = ["Fecha", "Transacción", "Débito", "Crédito", "Impuesto GMF"]
            cols_presentes = [col for col in cols_utiles if col in pdf.columns]
            pdf = pdf[cols_presentes].copy()
            
            # 2. Esterilización extrema (Pandas)
            for col in ["Débito", "Crédito", "Impuesto GMF"]:
                if col in cols_presentes:
                    pdf[col] = pd.to_numeric(pdf[col], errors='coerce').fillna(0.0)
                    
            if "Transacción" in pdf.columns:
                pdf["Transacción"] = pdf["Transacción"].fillna("").astype(str)
                
            # 3. Blindaje de Esquema para Polars
            esquema = {}
            if "Fecha" in pdf.columns: esquema["Fecha"] = pl.Utf8
            if "Transacción" in pdf.columns: esquema["Transacción"] = pl.Utf8
            if "Débito" in pdf.columns: esquema["Débito"] = pl.Float64
            if "Crédito" in pdf.columns: esquema["Crédito"] = pl.Float64
            if "Impuesto GMF" in pdf.columns: esquema["Impuesto GMF"] = pl.Float64

            df = pl.from_pandas(pdf, schema_overrides=esquema)
            
            # Garantizamos que las columnas matemáticas existan, incluso si el banco no las exportó un mes
            for col in ["Débito", "Crédito", "Impuesto GMF"]:
                if col not in df.columns:
                    df = df.with_columns(pl.lit(0.0).alias(col))

            # 4. LIMPIEZA Y ESTANDARIZACIÓN
            df_clean = (
                df
                .select([
                    # Agrario usa formato DD/MM/YYYY
                    pl.col("Fecha").str.slice(0, 10).str.to_date("%d/%m/%Y", strict=False).alias("Fecha"),
                    
                    pl.col("Transacción").str.strip_chars().alias("Concepto"),
                    pl.lit("N/A").alias("Documento_Referencia"),
                    
                    # Crédito es entrada, Débito + GMF es salida
                    pl.col("Crédito").alias("Ingreso"),
                    (pl.col("Débito") + pl.col("Impuesto GMF")).alias("Egreso")
                ])
                .with_columns(pl.lit("AGRARIO").alias("Origen"))
                
                # Filtramos la basura
                .filter(pl.col("Fecha").is_not_null() & ((pl.col("Ingreso") > 0) | (pl.col("Egreso") > 0)))
            )

            # 5. REGLA DE NEGOCIO (Separar los Traslados de $37.3M)
            df_final = df_clean.with_columns(
                pl.when(pl.col("Concepto").str.contains(r"(?i)INTERNET TRANSFERENCIAS ENTRE TERCEROS"))
                .then(pl.lit("Traslado_Salida"))
                .otherwise(pl.lit("Operacion_Normal"))
                .alias("Categoria_Flujo")
            )

            return df_final
            
        except Exception as e:
            print(f"Error procesando Agrario ({self.filepath}): {e}")
            import traceback
            traceback.print_exc()
            return pl.DataFrame({"Fecha": [], "Concepto": [], "Documento_Referencia": [], "Ingreso": [], "Egreso": [], "Origen": [], "Categoria_Flujo": []})

# ==========================================
# Zona de Pruebas
# ==========================================
if __name__ == "__main__":
    ruta_prueba = "c:/Users/usuario/Desktop/Financiera/4. Mov Agrario mes Noviembre ARP.xlsx"
    
    extractor = AgrarioExtractor(ruta_prueba)
    resultado = extractor.process()
    
    if not resultado.is_empty():
        print("--- Muestra de Datos Limpios (Agrario) ---")
        print(resultado.head())
        
        # Validaciones Matemáticas
        ingresos_totales = resultado["Ingreso"].sum()
        egresos_operativos = resultado.filter(pl.col("Categoria_Flujo") == "Operacion_Normal")["Egreso"].sum()
        traslados = resultado.filter(pl.col("Categoria_Flujo") == "Traslado_Salida")["Egreso"].sum()
        
        print("\n--- Validación de Cuadre ---")
        print(f"Ingresos Totales:      {ingresos_totales:,.2f} <-- (Debe ser 35,558,845)")
        print(f"Egresos Operativos:    {egresos_operativos:,.2f} <-- (Debe ser 135,896)")
        print(f"Salidas por Traslados: {traslados:,.2f} <-- (Debe ser 37,380,000)")
    else:
        print("El DataFrame regresó vacío.")