# src/utils/data_loader.py
import polars as pl
import pandas as pd
import sqlite3
import os
import re

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
    def load_proveedores() -> list:
        if os.path.exists(DataLoader.DB_PATH):
            try:
                with sqlite3.connect(DataLoader.DB_PATH) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT nombre FROM proveedores")
                    return [row[0].strip().upper() for row in cursor.fetchall()]
            except Exception as e:
                print(f"Error cargando proveedores: {e}")
        return []

    @staticmethod
    def load_mapeos_caja() -> tuple:
        """Retorna (mapeo_cajas_bd, mapeo_docs_caja)"""
        mapeo_cajas = {}
        mapeo_docs = {}
        if os.path.exists(DataLoader.DB_PATH):
            try:
                with sqlite3.connect(DataLoader.DB_PATH) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT codigo, recauda, docs FROM centros_costos")
                    for row in cursor.fetchall():
                        cod_caja = str(row[0]).strip()
                        recauda = str(row[1]).strip().upper()
                        docs_texto = str(row[2]).strip().upper()
                        
                        if recauda and recauda not in ["", "NONE", "NAN"]: 
                            mapeo_cajas[cod_caja] = recauda
                        if docs_texto and docs_texto not in ["", "NONE", "NAN"]:
                            for p in re.findall(r'[A-Z]{2}\d{2}', docs_texto): 
                                mapeo_docs[p] = recauda
            except Exception as e:
                print(f"Error cargando mapeos de caja: {e}")
        return mapeo_cajas, mapeo_docs

    @staticmethod
    def load_cuentas_2335() -> dict:
        """Carga el diccionario de cuentas para gastos."""
        cuentas = {}
        if os.path.exists(DataLoader.DB_PATH):
            try:
                with sqlite3.connect(DataLoader.DB_PATH) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT codigo, nombre FROM cuentas_2335")
                    for row in cursor.fetchall():
                        cuentas[str(row[0]).strip()] = str(row[1]).strip().title()
            except Exception as e:
                print(f"Error cargando cuentas 2335: {e}")
        return cuentas

    @staticmethod
    def get_total_supply() -> float:
        """Extrae el total de créditos supply del auxiliar 2205."""
        df = DataLoader.load_excel(f"{DataLoader.CACHE_DIR}/aux_prov_2205.xlsx")
        if not df.empty:
            df.columns = df.columns.str.strip().str.upper()
            if 'MCNDETALLE' in df.columns and 'MCNVALDEBI' in df.columns:
                df['MCNVALDEBI'] = pd.to_numeric(df['MCNVALDEBI'], errors='coerce').fillna(0)
                mask = df['MCNDETALLE'].astype(str).str.upper().str.contains('SUPPLY')
                return float(df.loc[mask, 'MCNVALDEBI'].sum())
        return 0.0

    @staticmethod
    def get_total_nomina_cajas() -> float:
        """Extrae el total de nómina pagada por caja del auxiliar 25."""
        df = DataLoader.load_excel(f"{DataLoader.CACHE_DIR}/aux_nomina_25.xlsx")
        if not df.empty:
            df.columns = df.columns.str.strip().str.upper()
            if 'MCNVALDEBI' in df.columns:
                df['MCNVALDEBI'] = pd.to_numeric(df['MCNVALDEBI'], errors='coerce').fillna(0)
                col_doc = next((col for col in ['MCNTIPODOC', 'TIPO', 'TIPODOC'] if col in df.columns), None)
                if col_doc:
                    df_cajas = df[df[col_doc].astype(str).str.upper().str.startswith('ES')]
                    return float(df_cajas['MCNVALDEBI'].sum())
        return 0.0