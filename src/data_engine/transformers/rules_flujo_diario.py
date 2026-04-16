# src/data_engine/transformers/rules_flujo_diario.py
import sqlite3
from collections import defaultdict

def procesar_datos_flujo_diario(banco_seleccionado: str):
    """
    Motor contable: Extrae datos de SQLite, calcula el Saldo Inicial base 
    y arrastra el flujo día a día (Running Balance).
    """
    with sqlite3.connect("local_cache/maestros.db") as conn:
        cursor = conn.cursor()
        if banco_seleccionado == "TODOS":
            cursor.execute("SELECT fecha, banco, saldo_inicial, ingresos, egresos FROM flujos_diarios")
        else:
            cursor.execute("SELECT fecha, banco, saldo_inicial, ingresos, egresos FROM flujos_diarios WHERE banco = ?", (banco_seleccionado,))
        raw_data = cursor.fetchall()

    if not raw_data:
        return [], [], [], []

    # 1. Obtenemos el Saldo Inicial "Base" (El más alto registrado por banco)
    saldos_base = {}
    for row in raw_data:
        banco = row[1]
        saldo = float(row[2]) if row[2] else 0.0
        if banco not in saldos_base or saldo > saldos_base[banco]:
            saldos_base[banco] = saldo
    
    total_saldo_base = sum(saldos_base.values())

    # 2. Agrupamos las transacciones (Ingresos/Egresos) por Día
    transacciones_dia = defaultdict(lambda: {"ing": 0.0, "egr": 0.0})
    for row in raw_data:
        fecha = row[0]
        transacciones_dia[fecha]["ing"] += float(row[3]) if row[3] else 0.0
        transacciones_dia[fecha]["egr"] += float(row[4]) if row[4] else 0.0

    # 3. Calculamos el Flujo en el Tiempo (Running Balance)
    fechas_ordenadas = sorted(transacciones_dia.keys())
    fechas, saldo_inicial_arr, ingresos_arr, egresos_arr = [], [], [], []
    
    running_saldo = total_saldo_base
    
    for fecha in fechas_ordenadas:
        fechas.append(fecha)
        saldo_inicial_arr.append(running_saldo)
        
        ing = transacciones_dia[fecha]["ing"]
        egr = transacciones_dia[fecha]["egr"]
        
        ingresos_arr.append(ing)
        egresos_arr.append(egr)
        
        # Contabilidad pura: El saldo final de hoy es el inicial de mañana
        running_saldo += (ing - egr)

    return fechas, saldo_inicial_arr, ingresos_arr, egresos_arr