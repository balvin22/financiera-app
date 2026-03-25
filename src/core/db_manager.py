# src/core/db_manager.py
import sqlite3
import pandas as pd
import os

DB_PATH = "local_cache/maestros.db"

class DBManager:
    def __init__(self):
        os.makedirs("local_cache", exist_ok=True)
        self.init_db()

    def init_db(self):
        """Crea las tablas si no existen."""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS cuentas_2335 (codigo TEXT PRIMARY KEY, nombre TEXT)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS proveedores (codigo TEXT PRIMARY KEY, nombre TEXT)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS bancos (codigo TEXT PRIMARY KEY, nombre TEXT)''')
            
            # ¡CORREGIDO! Ya no borramos la tabla, solo la creamos si no existe
            cursor.execute('''CREATE TABLE IF NOT EXISTS centros_costos (
                                codigo TEXT PRIMARY KEY,
                                nombre TEXT,
                                recauda TEXT,
                                docs TEXT)''')
            conn.commit()

    def get_all(self, tabla: str):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            if tabla == "centros_costos":
                cursor.execute("SELECT codigo, nombre, recauda, docs FROM centros_costos ORDER BY codigo ASC")
            else:
                cursor.execute(f"SELECT codigo, nombre FROM {tabla} ORDER BY nombre ASC")
            return cursor.fetchall()

    def insert_or_update(self, tabla: str, codigo: str, nombre: str, recauda: str = "", docs: str = ""):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            if tabla == "centros_costos":
                cursor.execute("INSERT OR REPLACE INTO centros_costos (codigo, nombre, recauda, docs) VALUES (?, ?, ?, ?)", (codigo, nombre, recauda, docs))
            else:
                cursor.execute(f"INSERT OR REPLACE INTO {tabla} (codigo, nombre) VALUES (?, ?)", (codigo, nombre))
            conn.commit()

    def delete(self, tabla: str, codigo: str):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {tabla} WHERE codigo = ?", (codigo,))
            conn.commit()

    def importar_desde_excel(self, tabla: str, ruta_excel: str):
        try:
            if tabla == "centros_costos":
                # Leemos tu Excel tal cual (asumiendo que tiene los encabezados de tu foto)
                df = pd.read_excel(ruta_excel)
                for index, row in df.iterrows():
                    codigo = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
                    if codigo.isdigit() or len(codigo) >= 3:
                        nombre = str(row.iloc[1]).strip().upper() if pd.notna(row.iloc[1]) else ""
                        recauda = str(row.iloc[2]).strip().upper() if pd.notna(row.iloc[2]) else ""
                        docs = str(row.iloc[3]).strip().upper() if pd.notna(row.iloc[3]) else ""
                        
                        # Limpiamos los "NAN" para que no queden feos en la BD
                        if recauda == "NAN": recauda = ""
                        if docs == "NAN": docs = ""
                        
                        self.insert_or_update(tabla, codigo, nombre, recauda, docs)
            else:
                df = pd.read_excel(ruta_excel, header=None)
                for index, row in df.iterrows():
                    if len(row) >= 2:
                        codigo = str(row.iloc[0]).strip()
                        nombre = str(row.iloc[1]).strip().upper().replace('"', '')
                        if codigo.isdigit() and len(nombre) > 2:
                            self.insert_or_update(tabla, codigo, nombre)
            return True
        except Exception as e:
            print(f"Error importando: {e}")
            return False