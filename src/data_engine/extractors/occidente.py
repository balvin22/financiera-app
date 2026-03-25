# src.data_engine/extractors/occidente.py
import polars as pl
import pandas as pd
from .base import BaseExtractor

class OccidenteExtractor(BaseExtractor):
    def process(self) -> pl.DataFrame:
        try:
            # 1. El Puente: Usamos pandas y le decimos explícitamente que lea "Hoja1"
            # Esto evita que el código se rompa si alguien cambia el orden de las pestañas
            pdf = pd.read_excel(self.filepath, sheet_name="Hoja1", skiprows=26)
            
            # Forzamos a que las columnas conflictivas sean estrictamente texto (strings)
            # para que PyArrow no colapse al encontrar números mezclados con letras.
            if "Nro. Documento" in pdf.columns:
                pdf["Nro. Documento"] = pdf["Nro. Documento"].astype(str)
            if "Transacción" in pdf.columns:
                pdf["Transacción"] = pdf["Transacción"].astype(str)
            
            # 2. Pasamos la tabla a Polars para la limpieza de alto rendimiento
            df = pl.from_pandas(pdf)

            # 3. Limpieza y Estandarización
            df_clean = (
                df
                .select([
                    # Pasamos a texto y le damos la máscara de formato "%Y/%m/%d"
                    pl.col("Fecha").cast(pl.Utf8).str.to_date("%Y/%m/%d", strict=False).alias("Fecha"),
                    
                    pl.col("Transacción").cast(pl.Utf8).alias("Concepto"),
                    pl.col("Nro. Documento").cast(pl.Utf8).alias("Documento_Referencia"),
                    
                    # Manejo de números, rellenando vacíos con 0
                    pl.col("Créditos").cast(pl.Float64, strict=False).fill_null(0.0).alias("Ingreso"),
                    pl.col("Débitos").cast(pl.Float64, strict=False).fill_null(0.0).alias("Egreso")
                ])
                .with_columns(pl.lit("OCCIDENTE").alias("Origen"))
                
                # Filtramos filas vacías o de totales (las que no tienen una fecha válida)
                .filter(pl.col("Fecha").is_not_null() & pl.col("Concepto").is_not_null())
                
                # 4. REGLAS DE NEGOCIO (El secreto descubierto en la hoja 'Din')
                # Etiquetamos automáticamente si la plata salió para un traslado o si es gasto real
                .with_columns(
                    pl.when(pl.col("Concepto") == "TRASLADO FONDOS SC")
                    .then(pl.lit("Traslado_Salida"))
                    .otherwise(pl.lit("Operacion_Normal"))
                    .alias("Categoria_Flujo")
                )
            )

            return df_clean
            
        except Exception as e:
            print(f"Error procesando Occidente ({self.filepath}): {e}")
            # Añadimos la nueva columna Categoria_Flujo al DataFrame de error para mantener la estructura
            return pl.DataFrame({"Fecha": [], "Concepto": [], "Documento_Referencia": [], "Ingreso": [], "Egreso": [], "Origen": [], "Categoria_Flujo": []})


# Zona de Pruebas
if __name__ == "__main__":
    ruta_prueba = "c:/Users/usuario/Desktop/Financiera/3. Movimiento Occidente Nov ARP.xlsx"
    
    extractor = OccidenteExtractor(ruta_prueba)
    resultado = extractor.process()
    
    if not resultado.is_empty():
        print("--- Muestra de Datos Limpios (Banco de Occidente) ---")
        print(resultado.head(10))
        
        print("\n--- Total de Movimientos ---")
        print(f"Total Ingresos: {resultado['Ingreso'].sum():,.2f}")
        print(f"Total Egresos (Crudos): {resultado['Egreso'].sum():,.2f}")
        
        # Validación de la Regla de Negocio
        salidas_reales = resultado.filter(pl.col("Categoria_Flujo") == "Operacion_Normal")["Egreso"].sum()
        traslados = resultado.filter(pl.col("Categoria_Flujo") == "Traslado_Salida")["Egreso"].sum()
        
        print(f"\n--- Desglose de Egresos (Según Hoja 'Din') ---")
        print(f"Egresos Operativos Reales: {salidas_reales:,.2f}")
        print(f"Traslados (No afectan gasto): {traslados:,.2f}")
    else:
        print("El DataFrame regresó vacío. Revisa la ruta o el archivo.")