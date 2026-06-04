# src/core/db_manager.py
import sqlite3
import pandas as pd
import os
from src.core.logger import get_logger
from datetime import datetime
from src.utils.data_loader import DataLoader

logger = get_logger("db_manager")

DB_PATH = "local_cache/maestros.db"

class DBManager:
    _instance = None
    _movimientos_cache = None
    _meses_cache = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        os.makedirs("local_cache", exist_ok=True)
        self.init_db()

    def init_db(self):
        """Crea las tablas si no existen."""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # --- TABLAS MAESTRAS ---
            cursor.execute('''CREATE TABLE IF NOT EXISTS cuentas_2335 (codigo TEXT PRIMARY KEY, nombre TEXT)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS proveedores (codigo TEXT PRIMARY KEY, nombre TEXT)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS bancos (codigo TEXT PRIMARY KEY, nombre TEXT)''')
            
            cursor.execute('''CREATE TABLE IF NOT EXISTS centros_costos (
                                codigo TEXT PRIMARY KEY,
                                nombre TEXT,
                                recauda TEXT,
                                docs TEXT)''')
            
            # --- NUEVA ESTRUCTURA TRANSACCIONAL ---
            # 1. Tabla de Movimientos Detallados (Para el cruce mensual)
            cursor.execute('''CREATE TABLE IF NOT EXISTS flujo_movimientos (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                fecha TEXT,
                                origen TEXT,
                                concepto TEXT,
                                documento_referencia TEXT,
                                numero_doc TEXT,
                                ingreso REAL DEFAULT 0,
                                egreso REAL DEFAULT 0,
                                categoria_flujo TEXT,
                                tercero TEXT,
                                 centro_costos TEXT,
                                 vinculado TEXT DEFAULT '',
                                 conciliado BOOLEAN DEFAULT 0,
                                created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
                                
            # 2. Tabla de Saldos (Para el arrastre matemático del día a día)
            cursor.execute('''CREATE TABLE IF NOT EXISTS saldos_diarios (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                fecha TEXT,
                                banco TEXT,
                                saldo_inicial REAL DEFAULT 0,
                                saldo_final REAL DEFAULT 0,
                                UNIQUE(fecha, banco))''')
            
            # Índices para consultas rápidas
            cursor.execute('''CREATE INDEX IF NOT EXISTS idx_mov_fecha ON flujo_movimientos(fecha)''')
            cursor.execute('''CREATE INDEX IF NOT EXISTS idx_mov_origen ON flujo_movimientos(origen)''')
            cursor.execute('''CREATE INDEX IF NOT EXISTS idx_saldos_fecha ON saldos_diarios(fecha)''')
            
            # --- TABLAS AUXILIARES (Gastos, Nómina, Proveedores) ---
            cursor.execute('''CREATE TABLE IF NOT EXISTS aux_gastos_2335 (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                mes TEXT NOT NULL,
                                tipo_doc TEXT,
                                num_doc TEXT,
                                cuenta TEXT,
                                categoria TEXT,
                                valor REAL DEFAULT 0,
                                detalle TEXT,
                                created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
            cursor.execute('''CREATE INDEX IF NOT EXISTS idx_aux_gastos_mes ON aux_gastos_2335(mes)''')
            
            cursor.execute('''CREATE TABLE IF NOT EXISTS aux_nomina_25 (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                mes TEXT NOT NULL,
                                tipo_doc TEXT,
                                num_doc TEXT,
                                caja_codigo TEXT,
                                caja_nombre TEXT,
                                empleado TEXT,
                                valor REAL DEFAULT 0,
                                detalle TEXT,
                                created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
            cursor.execute('''CREATE INDEX IF NOT EXISTS idx_aux_nomina_mes ON aux_nomina_25(mes)''')
            
            cursor.execute('''CREATE TABLE IF NOT EXISTS nomina_por_caja (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                mes TEXT NOT NULL,
                                caja TEXT NOT NULL,
                                empleado TEXT,
                                valor REAL DEFAULT 0,
                                created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
            cursor.execute('''CREATE INDEX IF NOT EXISTS idx_npc_mes ON nomina_por_caja(mes)''')
            
            cursor.execute('''CREATE TABLE IF NOT EXISTS aux_prov_2205 (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                mes TEXT NOT NULL,
                                tipo_doc TEXT,
                                num_doc TEXT,
                                detalle TEXT,
                                valor REAL DEFAULT 0,
                                es_supply BOOLEAN DEFAULT 0,
                                created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
            cursor.execute('''CREATE INDEX IF NOT EXISTS idx_aux_prov_mes ON aux_prov_2205(mes)''')
            
            conn.commit()

    # ==========================================
    # MÉTODOS DE MAESTROS (Sin cambios)
    # ==========================================
    def get_all(self, tabla: str):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            # Prevención básica de inyección SQL validando el nombre de la tabla
            tablas_validas = ["centros_costos", "cuentas_2335", "proveedores", "bancos"]
            if tabla not in tablas_validas:
                raise ValueError("Tabla no válida")

            if tabla == "centros_costos":
                cursor.execute("SELECT codigo, nombre, recauda, docs FROM centros_costos ORDER BY codigo ASC")
            else:
                cursor.execute(f"SELECT codigo, nombre FROM {tabla} ORDER BY nombre ASC")
            return cursor.fetchall()

    def _invalidar_caches_maestros(self):
        DataLoader._cache_mapeos_caja = None
        DataLoader._cache_cuentas_2335 = None
        DataLoader._cache_proveedores = None
        DataLoader._cache_codigos_proveedores = None

    def insert_or_update(self, tabla: str, codigo: str, nombre: str, recauda: str = "", docs: str = ""):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            if tabla == "centros_costos":
                cursor.execute("INSERT OR REPLACE INTO centros_costos (codigo, nombre, recauda, docs) VALUES (?, ?, ?, ?)", (codigo, nombre, recauda, docs))
            else:
                cursor.execute(f"INSERT OR REPLACE INTO {tabla} (codigo, nombre) VALUES (?, ?)", (codigo, nombre))
            conn.commit()
        self._invalidar_caches_maestros()

    def delete(self, tabla: str, codigo: str):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {tabla} WHERE codigo = ?", (codigo,))
            conn.commit()
        self._invalidar_caches_maestros()

    def importar_desde_excel(self, tabla: str, ruta_excel: str):
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                if tabla == "centros_costos":
                    df = pd.read_excel(ruta_excel)
                    registros = []
                    for _, row in df.iterrows():
                        codigo = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
                        if codigo.isdigit() or len(codigo) >= 3:
                            nombre = str(row.iloc[1]).strip().upper() if pd.notna(row.iloc[1]) else ""
                            recauda = str(row.iloc[2]).strip().upper() if pd.notna(row.iloc[2]) else ""
                            docs = str(row.iloc[3]).strip().upper() if pd.notna(row.iloc[3]) else ""
                            if recauda == "NAN": recauda = ""
                            if docs == "NAN": docs = ""
                            registros.append((codigo, nombre, recauda, docs))
                    if registros:
                        cursor.executemany(
                            "INSERT OR REPLACE INTO centros_costos (codigo, nombre, recauda, docs) VALUES (?, ?, ?, ?)",
                            registros
                        )
                else:
                    df = pd.read_excel(ruta_excel, header=None)
                    registros = []
                    for _, row in df.iterrows():
                        if len(row) >= 2:
                            codigo = str(row.iloc[0]).strip()
                            nombre = str(row.iloc[1]).strip().upper().replace('"', '')
                            if codigo.isdigit() and len(nombre) > 2:
                                registros.append((codigo, nombre))
                    if registros:
                        cursor.executemany(
                            f"INSERT OR REPLACE INTO {tabla} (codigo, nombre) VALUES (?, ?)",
                            registros
                        )
                conn.commit()
            self._invalidar_caches_maestros()
            return True
        except Exception as e:
            logger.error(f"Error importando: {e}")
            return False

    # ==========================================
    # MÉTODOS TRANSACCIONALES (Nueva Lógica)
    # ==========================================
    def _invalidar_caches(self):
        DBManager._movimientos_cache = None
        DBManager._meses_cache = None
        from src.data_engine.transformers.rules_flujo_diario import invalidar_cache_flujo
        invalidar_cache_flujo()

    def guardar_movimiento(self, fecha: str, origen: str, concepto: str, doc_ref: str, num_doc: str, 
                           ingreso: float, egreso: float, cat_flujo: str, tercero: str = "N/A", cco: str = "N/A", vinculado: str = ""):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO flujo_movimientos 
                (fecha, origen, concepto, documento_referencia, numero_doc, ingreso, egreso, categoria_flujo, tercero, centro_costos, vinculado)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (fecha, origen, concepto, doc_ref, num_doc, ingreso, egreso, cat_flujo, tercero, cco, vinculado))
            conn.commit()
            self._invalidar_caches()

    def guardar_movimientos_batch(self, registros: list):
        if not registros:
            return
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.executemany('''
                INSERT INTO flujo_movimientos 
                (fecha, origen, concepto, documento_referencia, numero_doc, ingreso, egreso, categoria_flujo, tercero, centro_costos, vinculado)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', registros)
            conn.commit()

    def guardar_saldo_diario(self, fecha: str, banco: str, saldo_inicial: float, saldo_final: float):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO saldos_diarios (fecha, banco, saldo_inicial, saldo_final)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(fecha, banco) DO UPDATE SET 
                    saldo_inicial=excluded.saldo_inicial,
                    saldo_final=excluded.saldo_final
            ''', (fecha, banco, saldo_inicial, saldo_final))
            conn.commit()
        self._invalidar_caches()

    def guardar_saldos_batch(self, saldos: list):
        if not saldos:
            return
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.executemany('''
                INSERT INTO saldos_diarios (fecha, banco, saldo_inicial, saldo_final)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(fecha, banco) DO UPDATE SET 
                    saldo_inicial=excluded.saldo_inicial,
                    saldo_final=excluded.saldo_final
            ''', saldos)
            conn.commit()

    def tiene_saldos_diarios(self) -> bool:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM saldos_diarios")
            return cursor.fetchone()[0] > 0

    def tiene_movimientos(self) -> bool:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM flujo_movimientos")
            return cursor.fetchone()[0] > 0

    def get_ultimo_saldo(self, banco: str) -> float:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT saldo_final FROM saldos_diarios 
                WHERE banco = ? 
                ORDER BY fecha DESC LIMIT 1
            ''', (banco,))
            row = cursor.fetchone()
            return row[0] if row else 0.0

    def get_movimientos(self, fecha_inicio: str = None, fecha_fin: str = None, origen: str = None, mes: str = None):
        """Retorna el detalle línea a línea para conciliación. Usa caché si no hay filtros."""
        cache_key = (fecha_inicio, fecha_fin, origen, mes)
        if cache_key == (None, None, None, None) and DBManager._movimientos_cache is not None:
            return DBManager._movimientos_cache
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            query = """SELECT fecha, origen, concepto, documento_referencia, numero_doc, 
                              ingreso, egreso, categoria_flujo, tercero, centro_costos, conciliado, vinculado 
                       FROM flujo_movimientos WHERE 1=1"""
            params = []
            
            if fecha_inicio:
                query += " AND fecha >= ?"
                params.append(fecha_inicio)
            if fecha_fin:
                query += " AND fecha <= ?"
                params.append(fecha_fin)
            if origen:
                query += " AND origen = ?"
                params.append(origen)
            if mes:
                query += " AND fecha LIKE ?"
                params.append(mes + '%')
            
            query += " ORDER BY fecha DESC, origen ASC"
            cursor.execute(query, params)
            
            columns = [desc[0] for desc in cursor.description]
            resultados = [dict(zip(columns, row)) for row in cursor.fetchall()]
            if cache_key == (None, None, None, None):
                DBManager._movimientos_cache = resultados
            return resultados

    def get_fechas_disponibles(self):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT fecha FROM saldos_diarios ORDER BY fecha DESC")
            return [row[0] for row in cursor.fetchall()]

    def get_meses_disponibles(self):
        if DBManager._meses_cache is not None:
            return DBManager._meses_cache
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT substr(fecha, 1, 7) FROM saldos_diarios ORDER BY fecha ASC")
            DBManager._meses_cache = [row[0] for row in cursor.fetchall()]
        return DBManager._meses_cache

    def get_dias_disponibles(self, mes: str, banco: str = "TODOS"):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            if banco and banco != "TODOS":
                cursor.execute("SELECT DISTINCT fecha FROM saldos_diarios WHERE fecha LIKE ? AND banco = ? ORDER BY fecha ASC", (mes + '%', banco))
            else:
                cursor.execute("SELECT DISTINCT fecha FROM saldos_diarios WHERE fecha LIKE ? ORDER BY fecha ASC", (mes + '%',))
            return [row[0] for row in cursor.fetchall()]

    def get_bancos_disponibles(self):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT banco FROM saldos_diarios ORDER BY banco ASC")
            return [row[0] for row in cursor.fetchall()]

    def get_totales_por_fecha(self):
        """Cruza saldos y movimientos para la vista resumen."""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT s.fecha, 
                       SUM(s.saldo_inicial) as total_saldo_inicial, 
                       SUM(m.ingreso) as total_ingresos, 
                       SUM(m.egreso) as total_egresos,
                       SUM(s.saldo_final) as total_saldo_final
                FROM saldos_diarios s
                LEFT JOIN flujo_movimientos m ON s.fecha = m.fecha AND s.banco = m.origen
                GROUP BY s.fecha
                ORDER BY s.fecha DESC
            ''')
            return cursor.fetchall()

    def eliminar_flujo_fecha(self, fecha: str):
        """Limpia todo el rastro de un día específico en ambas tablas."""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM flujo_movimientos WHERE fecha = ?", (fecha,))
            cursor.execute("DELETE FROM saldos_diarios WHERE fecha = ?", (fecha,))
            conn.commit()
        self._invalidar_caches()

    # ==========================================
    # MÉTODOS PARA TABLAS AUXILIARES
    # ==========================================
    def guardar_aux_gastos(self, mes: str, registros: list):
        if not registros:
            return
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM aux_gastos_2335 WHERE mes = ?", (mes,))
            cursor.executemany('''INSERT INTO aux_gastos_2335 (mes,tipo_doc,num_doc,cuenta,categoria,valor,detalle) VALUES (?,?,?,?,?,?,?)''',
                [(mes, r.get("tipo_doc",""), r.get("num_doc",""), r.get("cuenta",""), r.get("categoria",""), r.get("valor",0.0), r.get("detalle","")) for r in registros])
            conn.commit()

    def get_aux_gastos(self, mes: str) -> list:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT tipo_doc,num_doc,cuenta,categoria,valor,detalle FROM aux_gastos_2335 WHERE mes=?", (mes,))
            return [{"tipo_doc":r[0],"num_doc":r[1],"cuenta":r[2],"categoria":r[3],"valor":r[4],"detalle":r[5]} for r in cursor.fetchall()]

    def guardar_aux_nomina(self, mes: str, registros: list):
        if not registros:
            return
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM aux_nomina_25 WHERE mes = ?", (mes,))
            cursor.executemany('''INSERT INTO aux_nomina_25 (mes,tipo_doc,num_doc,caja_codigo,caja_nombre,empleado,valor,detalle) VALUES (?,?,?,?,?,?,?,?)''',
                [(mes, r.get("tipo_doc",""), r.get("num_doc",""), r.get("caja_codigo",""), r.get("caja_nombre",""), r.get("empleado",""), r.get("valor",0.0), r.get("detalle","")) for r in registros])
            conn.commit()

    def guardar_nomina_por_caja(self, mes: str, registros: list):
        if not registros:
            return
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM nomina_por_caja WHERE mes = ?", (mes,))
            cursor.executemany('''INSERT INTO nomina_por_caja (mes,caja,empleado,valor) VALUES (?,?,?,?)''',
                [(mes, r["caja"], r.get("empleado",""), r["valor"]) for r in registros])
            conn.commit()

    def get_nomina_por_caja(self, mes: str) -> list:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT caja, empleado, valor FROM nomina_por_caja WHERE mes=?", (mes,))
            return [{"caja":r[0],"empleado":r[1],"valor":r[2]} for r in cursor.fetchall()]
