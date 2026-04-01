# src/utils/data_loader.py
import polars as pl
import pandas as pd
import sqlite3
import os
import json

class DataLoader:
    """Cargador de datos para el dashboard y reportes."""
    
    CACHE_DIR = "local_cache"
    DB_PATH = f"{CACHE_DIR}/maestros.db"
    
    @staticmethod
    def load_parquet(nombre: str) -> pl.DataFrame:
        ruta = os.path.join(DataLoader.CACHE_DIR, f"{nombre}.parquet")
        if os.path.exists(ruta):
            return pl.read_parquet(ruta)
        return pl.DataFrame()
    
    @staticmethod
    def load_dataframes() -> tuple:
        df_global = DataLoader.load_parquet("base_global")
        df_detallado = DataLoader.load_parquet("base_detallada")
        df_resumen = DataLoader.load_parquet("base_resumen")
        return df_global, df_detallado, df_resumen
    
    @staticmethod
    def has_data() -> bool:
        return os.path.exists(f"{DataLoader.CACHE_DIR}/base_detallada.parquet") and \
               os.path.exists(f"{DataLoader.CACHE_DIR}/base_resumen.parquet")
    
    @staticmethod
    def get_resumen_values(df_resumen: pd.DataFrame) -> dict:
        def obtener_valor(concepto_str):
            try:
                vals = df_resumen.loc[df_resumen['Concepto'] == concepto_str, 'Valor'].dropna().values
                return float(vals[0]) if len(vals) > 0 else 0.0
            except:
                return 0.0
        
        return {
            "ingresos_mes": obtener_valor("Total Ingresos del mes"),
            "saldo_inicial": obtener_valor("Saldo inicial del mes anterior"),
            "total_disponible": obtener_valor("Total Disponible"),
            "total_salidas": obtener_valor("Total salidas del mes"),
        }
    
    @staticmethod
    def load_excel(ruta: str) -> pd.DataFrame:
        if os.path.exists(ruta):
            return pd.read_excel(ruta)
        return pd.DataFrame()
    
    @staticmethod
    def load_categorias_2335() -> dict:
        df = DataLoader.load_excel(f"{DataLoader.CACHE_DIR}/gastos_2335.xlsx")
        if df.empty:
            return {}
        
        df.columns = df.columns.str.strip().str.upper()
        if 'MCNCUENTA' in df.columns and 'MCNVALDEBI' in df.columns:
            df['MCNVALDEBI'] = pd.to_numeric(df['MCNVALDEBI'], errors='coerce').fillna(0)
            df_filtrado = df[df['MCNVALDEBI'] > 0]
            return dict(df_filtrado.groupby('MCNCUENTA')['MCNVALDEBI'].sum())
        return {}
    
    @staticmethod
    def load_proveedores() -> list:
        if os.path.exists(DataLoader.DB_PATH):
            try:
                with sqlite3.connect(DataLoader.DB_PATH) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT nombre FROM proveedores")
                    return [row[0].strip().upper() for row in cursor.fetchall()]
            except:
                pass
        return []
    
    @staticmethod
    def load_cajas_mapeo() -> dict:
        if os.path.exists(DataLoader.DB_PATH):
            try:
                with sqlite3.connect(DataLoader.DB_PATH) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT codigo, recauda FROM centros_costos")
                    mapeo = {}
                    for row in cursor.fetchall():
                        recauda = str(row[1]).strip().upper()
                        if recauda and recauda not in ["", "NONE", "NAN"]:
                            mapeo[str(row[0]).strip()] = recauda
                    return mapeo
            except:
                pass
        return {}