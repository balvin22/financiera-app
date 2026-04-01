# src/core/db_manager.py
import sqlite3
import pandas as pd
import os
from src.core.logger import get_logger
from datetime import datetime

logger = get_logger("db_manager")

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
            
            cursor.execute('''CREATE TABLE IF NOT EXISTS centros_costos (
                                codigo TEXT PRIMARY KEY,
                                nombre TEXT,
                                recauda TEXT,
                                docs TEXT)''')
            
            cursor.execute('''CREATE TABLE IF NOT EXISTS flujos_diarios (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                fecha TEXT,
                                banco TEXT,
                                ingresos REAL,
                                egresos REAL,
                                created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
            cursor.execute('''CREATE INDEX IF NOT EXISTS idx_flujos_diarios_fecha ON flujos_diarios(fecha)''')
            cursor.execute('''CREATE INDEX IF NOT EXISTS idx_flujos_diarios_banco ON flujos_diarios(banco)''')
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
            logger.error(f"Error importando: {e}")
            return False

    def guardar_flujo_diario(self, fecha: str, banco: str, ingresos: float, egresos: float):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO flujos_diarios (fecha, banco, ingresos, egresos)
                VALUES (?, ?, ?, ?)
            ''', (fecha, banco, ingresos, egresos))
            conn.commit()

    def get_flujos_diarios(self, fecha_inicio: str = None, fecha_fin: str = None, banco: str = None):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            query = "SELECT fecha, banco, ingresos, egresos FROM flujos_diarios WHERE 1=1"
            params = []
            
            if fecha_inicio:
                query += " AND fecha >= ?"
                params.append(fecha_inicio)
            if fecha_fin:
                query += " AND fecha <= ?"
                params.append(fecha_fin)
            if banco:
                query += " AND banco = ?"
                params.append(banco)
            
            query += " ORDER BY fecha DESC, banco ASC"
            cursor.execute(query, params)
            return cursor.fetchall()

    def get_fechas_disponibles(self):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT fecha FROM flujos_diarios ORDER BY fecha DESC")
            return [row[0] for row in cursor.fetchall()]

    def get_bancos_disponibles(self):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT banco FROM flujos_diarios ORDER BY banco ASC")
            return [row[0] for row in cursor.fetchall()]

    def get_totales_por_fecha(self):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT fecha, SUM(ingresos) as total_ingresos, SUM(egresos) as total_egresos
                FROM flujos_diarios
                GROUP BY fecha
                ORDER BY fecha DESC
            ''')
            return cursor.fetchall()

    def eliminar_flujo_fecha(self, fecha: str):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM flujos_diarios WHERE fecha = ?", (fecha,))
            conn.commit()