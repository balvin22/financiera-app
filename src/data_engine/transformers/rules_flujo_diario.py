# src/data_engine/transformers/rules_flujo_diario.py
import sqlite3
from collections import defaultdict

def procesar_datos_flujo_diario(banco_seleccionado: str, mes_filtro: str = None, fecha_exacta: str = None):
    """
    Motor contable diario: Calcula la apertura real del mes y arrastra el saldo
    utilizando un Libro Mayor Continuo (Running Balance) para evitar la pérdida
    de saldos en días sin movimientos transaccionales.
    
    Args:
        banco_seleccionado: "TODOS" o nombre del banco.
        mes_filtro: Opcional, formato "YYYY-MM". Filtra solo las fechas de ese mes.
        fecha_exacta: Opcional, formato "YYYY-MM-DD". Filtra a una fecha exacta (prioriza sobre mes_filtro).
    """
    with sqlite3.connect("local_cache/maestros.db") as conn:
        cursor = conn.cursor()
        
        if fecha_exacta and not mes_filtro:
            mes_filtro = fecha_exacta[:7]

        # 1. CAPTURA DEL SALDO INICIAL REAL DE APERTURA DEL MES
        if fecha_exacta:
            if banco_seleccionado == "TODOS":
                cursor.execute("""
                    SELECT banco, saldo_inicial 
                    FROM saldos_diarios 
                    WHERE fecha = ?
                """, (fecha_exacta,))
                saldos_apertura = cursor.fetchall()
                total_saldo_inicial = sum(float(row[1] or 0.0) for row in saldos_apertura)
            else:
                cursor.execute("""
                    SELECT saldo_inicial 
                    FROM saldos_diarios 
                    WHERE banco = ? AND fecha = ?
                """, (banco_seleccionado, fecha_exacta))
                row = cursor.fetchone()
                total_saldo_inicial = float(row[0] or 0.0) if row else 0.0
        elif mes_filtro:
            if banco_seleccionado == "TODOS":
                cursor.execute("""
                    SELECT banco, saldo_inicial 
                    FROM saldos_diarios 
                    WHERE fecha LIKE ? AND (banco, fecha) IN (
                        SELECT banco, MIN(fecha) FROM saldos_diarios WHERE fecha LIKE ? GROUP BY banco
                    )
                """, (mes_filtro + '%', mes_filtro + '%'))
                saldos_apertura = cursor.fetchall()
                total_saldo_inicial = sum(float(row[1] or 0.0) for row in saldos_apertura)
            else:
                cursor.execute("""
                    SELECT saldo_inicial 
                    FROM saldos_diarios 
                    WHERE banco = ? AND fecha LIKE ?
                    ORDER BY fecha ASC LIMIT 1
                """, (banco_seleccionado, mes_filtro + '%'))
                row = cursor.fetchone()
                total_saldo_inicial = float(row[0] or 0.0) if row else 0.0
        else:
            if banco_seleccionado == "TODOS":
                cursor.execute("""
                    SELECT banco, saldo_inicial 
                    FROM saldos_diarios 
                    WHERE (banco, fecha) IN (
                        SELECT banco, MIN(fecha) FROM saldos_diarios GROUP BY banco
                    )
                """)
                saldos_apertura = cursor.fetchall()
                total_saldo_inicial = sum(float(row[1] or 0.0) for row in saldos_apertura)
            else:
                cursor.execute("""
                    SELECT saldo_inicial 
                    FROM saldos_diarios 
                    WHERE banco = ? 
                    ORDER BY fecha ASC LIMIT 1
                """, (banco_seleccionado,))
                row = cursor.fetchone()
                total_saldo_inicial = float(row[0] or 0.0) if row else 0.0

        # 2. EXTRACCIÓN DE MOVIMIENTOS DETALLADOS PARA INGRESOS Y EGRESOS
        cursor.execute("SELECT fecha, origen, concepto, ingreso, egreso, categoria_flujo FROM flujo_movimientos")
        mov_raw = cursor.fetchall()

    if not mov_raw:
        # Respaldo por si la tabla de movimientos está limpia pero hay saldos registrados
        with sqlite3.connect("local_cache/maestros.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT fecha FROM saldos_diarios ORDER BY fecha ASC")
            fechas_vacias = [r[0] for r in cursor.fetchall()]
        if fechas_vacias:
            zeros = [0.0] * len(fechas_vacias)
            s_ini_arr = [total_saldo_inicial] * len(fechas_vacias)
            return fechas_vacias, s_ini_arr, zeros, zeros, zeros, zeros, s_ini_arr
        return [], [], [], [], [], [], []

    # Estructura intermedia para clasificar la plata y aplicar puentes de traslados
    movs = defaultdict(lambda: defaultdict(lambda: {
        "ing_bruto": 0.0, "egr_bruto": 0.0, 
        "ing_tras": 0.0, "egr_tras": 0.0,
        "traslado_caja_cb": 0.0, "traslado_ali_occ": 0.0, "traslado_ali_ban": 0.0
    }))

    for fecha, origen, concepto, ingreso, egreso, cat in mov_raw:
        if origen == "CAJA_BANCOS": continue
        
        d = movs[fecha][origen]
        
        # Regla especial Bancolombia
        if origen == "BANCOLOMBIA" and "TRASL ENTRE FONDOS DE VALORES" in str(concepto).upper():
            cat = "Traslado_Salida"
            
        ing = float(ingreso or 0.0)
        egr = float(egreso or 0.0)
        
        d["ing_bruto"] += ing
        d["egr_bruto"] += egr
        
        if "Traslado_Entrada" in cat or "Ajuste_Don_Diego" in cat:
            d["ing_tras"] += ing
            
        if "Traslado_Salida" in cat:
            d["egr_tras"] += egr
            if origen == "CAJA":
                d["traslado_caja_cb"] += egr
            elif origen == "ALIANZA":
                if "OCCIDENTE" in str(concepto).upper():
                    d["traslado_ali_occ"] += egr
                else:
                    d["traslado_ali_ban"] += egr
        elif cat == "Ajuste_Don_Diego":
            d["egr_tras"] += ing

    # Inyección de puentes contables de traslados entre cuentas
    for fecha, bancos in movs.items():
        caja_cb = bancos.get("CAJA", {}).get("traslado_caja_cb", 0.0)
        ali_occ = bancos.get("ALIANZA", {}).get("traslado_ali_occ", 0.0)
        ali_ban = bancos.get("ALIANZA", {}).get("traslado_ali_ban", 0.0)
        
        if "BANCOLOMBIA" in bancos:
            bancos["BANCOLOMBIA"]["ing_tras"] = caja_cb + ali_ban
        if "OCCIDENTE" in bancos:
            bancos["OCCIDENTE"]["ing_tras"] += ali_occ

    # Construcción de la línea de tiempo unificada
    fechas_set = sorted(list(set(movs.keys())))
    if fecha_exacta:
        fechas_set = [f for f in fechas_set if f == fecha_exacta]
    elif mes_filtro:
        fechas_set = [f for f in fechas_set if f.startswith(mes_filtro)]
    fechas, saldos_ini, ing_op, ing_tr, egr_op, egr_tr, saldos_fin = [], [], [], [], [], [], []
    
    running_saldo = total_saldo_inicial
    
    for fecha in fechas_set:
        dia_ing_op, dia_ing_tr, dia_egr_op, dia_egr_tr = 0.0, 0.0, 0.0, 0.0
        tiene_datos_banco = False
        
        for b in movs[fecha].keys():
            if banco_seleccionado != "TODOS" and b != banco_seleccionado: continue
            
            tiene_datos_banco = True
            m = movs[fecha][b]
            i_b, e_b = m["ing_bruto"], m["egr_bruto"]
            i_t, e_t = m["ing_tras"], m["egr_tras"]
            
            dia_ing_op += (i_b - i_t)
            dia_ing_tr += i_t
            dia_egr_op += (e_b - e_t)
            dia_egr_tr += e_t

        # Si filtramos por un banco específico y ese día no registró actividad, saltamos la fecha
        if banco_seleccionado != "TODOS" and not tiene_datos_banco:
            continue

        # Almacenamos el estado del día usando el balance acumulado continuo
        fechas.append(fecha)
        saldos_ini.append(running_saldo)
        ing_op.append(dia_ing_op)
        ing_tr.append(dia_ing_tr)
        egr_op.append(dia_egr_op)
        egr_tr.append(dia_egr_tr)
        
        # Balance neto diario para calcular el cierre
        dia_neto = dia_ing_op + dia_ing_tr - dia_egr_op - dia_egr_tr
        running_saldo_final = running_saldo + dia_neto
        saldos_fin.append(running_saldo_final)
        
        # El saldo de cierre se convierte en la apertura del siguiente día de actividad
        running_saldo = running_saldo_final

    return fechas, saldos_ini, ing_op, ing_tr, egr_op, egr_tr, saldos_fin