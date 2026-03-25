# src/data_engine/reports/constructor_resumen.py
import polars as pl
import pandas as pd
import os
import sqlite3
from src.core.mapeos import MAPEO_CAJAS

AJUSTE_INGRESOS_CAJA = 16649756

# =========================================================================
# --- MOTOR DE CARGA DE BD SQLITE (PROVEEDORES Y CUENTAS 2335) ---
# =========================================================================
PROVEEDORES_LISTA = []
DICT_CUENTAS_2335 = {}
db_path = "local_cache/maestros.db"

if os.path.exists(db_path):
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 1. Extraemos los Proveedores
            cursor.execute("SELECT nombre FROM proveedores")
            PROVEEDORES_LISTA = [row[0].strip().upper() for row in cursor.fetchall()]
            
            # 2. Extraemos el catálogo de Cuentas 2335
            cursor.execute("SELECT codigo, nombre FROM cuentas_2335")
            for row in cursor.fetchall():
                codigo_cta = str(row[0]).strip()
                nombre_cta = str(row[1]).strip().title()
                DICT_CUENTAS_2335[codigo_cta] = nombre_cta
                
    except Exception as e:
        print(f"Advertencia: No se pudo cargar datos desde BD - {e}")

def armar_resumen_gerencial(df_global: pl.DataFrame, df_detallado: pl.DataFrame, ajustes: dict = None) -> pd.DataFrame:
    if ajustes is None:
        ajustes = {}

    # =========================================================================
    # --- MOTOR DE CARGA DE GASTOS OFICIALES (2335 DEL MES) ---
    # =========================================================================
    DICT_GASTOS_OFICIAL = {}
    ruta_gastos = "local_cache/gastos_2335.xlsx"

    if os.path.exists(ruta_gastos):
        try:
            df_gastos = pd.read_excel(ruta_gastos)
            df_gastos.columns = df_gastos.columns.str.strip().str.upper()
            
            if 'MCNCUENTA' in df_gastos.columns and 'MCNVALDEBI' in df_gastos.columns:
                df_gastos['MCNVALDEBI'] = pd.to_numeric(df_gastos['MCNVALDEBI'], errors='coerce').fillna(0)
                
                # Filtramos solo pagos (Débitos > 0)
                df_pagos = df_gastos[df_gastos['MCNVALDEBI'] > 0].copy()
                
                def mapear_cuenta(codigo, detalle):
                    cod_str = str(codigo).strip()
                    if cod_str.endswith(".0"):
                        cod_str = cod_str[:-2]
                        
                    if cod_str in DICT_CUENTAS_2335:
                        return DICT_CUENTAS_2335[cod_str]
                        
                    if len(cod_str) >= 6:
                        raiz = cod_str[:6]
                        for c_bd, n_bd in DICT_CUENTAS_2335.items():
                            if str(c_bd).startswith(raiz):
                                return n_bd
                                
                    texto = str(detalle).upper()
                    if any(x in texto for x in ["NOMIN", "LIBRANZA", "QUINCENA", "SUELDO"]): return "Nomina Administrativa y Ventas"
                    if any(x in texto for x in ["EPS", "SANITAS", "ARL", "PENSION", "APORTES"]): return "Seguridad Social"
                    if any(x in texto for x in ["ARRIENDO", "ARRENDAMIENTO", "RENTING"]): return "Arrendamientos (Incluye Renting)"
                    if any(x in texto for x in ["ENERGIA", "ACUEDUCTO", "GASES", "CLARO", "AGUA", "TELECOM"]): return "Servicios"
                    if any(x in texto for x in ["SEGURO", "POLIZA"]): return "Seguros"
                    if any(x in texto for x in ["HONORARIO", "ASESORIA"]): return "Honorarios"
                    if any(x in texto for x in ["COMISION", "GMF", "4X1000", "INTERES"]): return "Comisiones y Gastos Bancarios"
                    if any(x in texto for x in ["CREDITO", "OBLIGACION"]): return "Obligaciones financieras"
                    
                    return "Otros Proveedores / Gastos"

                col_detalle = 'CTANOMBRE' if 'CTANOMBRE' in df_pagos.columns else ('MCNDETALLE' if 'MCNDETALLE' in df_pagos.columns else None)
                
                df_pagos['Categoria_Gasto'] = df_pagos.apply(
                    lambda x: mapear_cuenta(x['MCNCUENTA'], x[col_detalle] if col_detalle else ""), 
                    axis=1
                )
                
                agrupado = df_pagos.groupby('Categoria_Gasto')['MCNVALDEBI'].sum()
                for cat, valor in agrupado.items():
                    if valor > 0:
                        DICT_GASTOS_OFICIAL[cat] = float(valor)
        except Exception as e:
            print(f"Advertencia: No se pudo procesar gastos_2335.xlsx - {e}")

    # --- NUEVO: MOTOR DE EXTRACCIÓN CRÉDITOS SUPPLY (2205) ---
    total_supply = 0.0
    ruta_aux_prov = "local_cache/aux_prov_2205.xlsx"
    
    if os.path.exists(ruta_aux_prov):
        try:
            df_aux = pd.read_excel(ruta_aux_prov)
            df_aux.columns = df_aux.columns.str.strip().str.upper()
            if 'MCNDETALLE' in df_aux.columns and 'MCNVALDEBI' in df_aux.columns:
                df_aux['MCNVALDEBI'] = pd.to_numeric(df_aux['MCNVALDEBI'], errors='coerce').fillna(0)
                # Filtramos donde MCNDETALLE contenga 'SUPPLY'
                mask = df_aux['MCNDETALLE'].astype(str).str.upper().str.contains('SUPPLY')
                total_supply = float(df_aux.loc[mask, 'MCNVALDEBI'].sum())
        except Exception as e:
            print(f"Advertencia: No se procesó aux_prov_2205.xlsx - {e}")

    # --- ENSAMBLAJE DEL REPORTE ---
    if "NOMBRE_CCO" in df_global.columns:
        df_global = df_global.with_columns(
            pl.col("NOMBRE_CCO")
            .cast(pl.Utf8)
            .str.extract(r"(\d{5})") 
            .replace_strict(MAPEO_CAJAS, default=pl.col("NOMBRE_CCO"))
            .alias("NOMBRE_CCO")
        )

    df_bancos = df_detallado.filter(~pl.col("Origen").is_in(["CAJA", "TOTAL BANCOS", "BANCO + CAJA"]))
    
    total_bancos_ingresos = df_bancos["Ingresos_Operativos"].sum() 
    total_bancos_salidas_traslados = df_bancos["Salidas_por_Traslados"].sum()
    salida_traslado_alianza = df_bancos.filter(pl.col("Origen") == "ALIANZA")["Salidas_por_Traslados"].sum()
    
    ingresos_bancos = total_bancos_ingresos - total_bancos_salidas_traslados + salida_traslado_alianza
    ingresos_caja_neto = df_detallado.filter(pl.col("Origen") == "CAJA")["Ingresos_Operativos"].sum()
    ingresos_caja_bruto = ingresos_caja_neto + AJUSTE_INGRESOS_CAJA 
    
    total_ingresos_mes = ingresos_bancos + ingresos_caja_bruto
    saldo_inicial_total = df_detallado.filter(pl.col("Origen") == "BANCO + CAJA")["Saldo_Inicial"].sum()
    total_disponible = total_ingresos_mes + saldo_inicial_total

    salidas_bancos = df_bancos["Salidas_Operativas"].sum()
    salidas_caja = df_detallado.filter(pl.col("Origen") == "CAJA")["Salidas_Operativas"].sum()
    
    if PROVEEDORES_LISTA:
        condicion_proveedores = pl.col("Tercero").fill_null("").str.to_uppercase().str.strip_chars().is_in(PROVEEDORES_LISTA)
    else:
        condicion_proveedores = (
            (
                (pl.col("Origen") == "CAJA") & 
                (pl.col("Documento_Referencia").fill_null("").str.starts_with("EB"))
            ) | 
            (pl.col("Origen") == "CAJA_BANCOS")
        ) & (~pl.col("Tercero").fill_null("").str.to_uppercase().str.contains("FINANSUENOS SAS"))

    # LÓGICA DE GASTOS DE RESPALDO (Por si no suben el Excel 2335)
    df_egresos = df_global.filter(
        (pl.col("Egreso") > 0) & 
        (pl.col("Categoria_Flujo") == "Operacion_Normal") &
        ~condicion_proveedores
    )
    
    df_categorizado = df_egresos.with_columns(
        pl.when(pl.col("Concepto").str.contains(r"(?i)NOMIN|LIBRANZA|QUINCENA|SUELDO")).then(pl.lit("Nomina Administrativa y Ventas"))
        .when(pl.col("Concepto").str.contains(r"(?i)EPS|SANITAS|ARL|PENSION|APORTES EN LINEA|COMPENSACION")).then(pl.lit("Seguridad Social"))
        .when(pl.col("Concepto").str.contains(r"(?i)ARRIENDO|ARRENDAMIENTO|RENTING|INMOBILIARIA")).then(pl.lit("Arrendamientos (Incluye Renting)"))
        .when(pl.col("Concepto").str.contains(r"(?i)ENERGIA|ACUEDUCTO|GASES|CLARO|MOVISTAR|AGUA|TELECOMUNICACIONES")).then(pl.lit("Servicios"))
        .when(pl.col("Concepto").str.contains(r"(?i)SEGURO|POLIZA|SURAMERICANA")).then(pl.lit("Seguros"))
        .when(pl.col("Concepto").str.contains(r"(?i)HONORARIO|ASESORIA|CONSULTORIA")).then(pl.lit("Honorarios"))
        .when(pl.col("Concepto").str.contains(r"(?i)COMISION|GMF|4X1000|INTERES|FINANCIACI|RECAUDO|CUOTA MANEJO")).then(pl.lit("Comisiones y Gastos Bancarios"))
        .when(pl.col("Concepto").str.contains(r"(?i)CUOTA CREDITO|CREDITO|OBLIGACION")).then(pl.lit("Obligaciones financieras"))
        .otherwise(pl.lit("Otros Proveedores / Gastos"))
        .alias("Categoria_Resumen")
    )
    
    gastos_agrupados = df_categorizado.group_by("Categoria_Resumen").agg(pl.col("Egreso").sum().alias("Valor"))
    dict_gastos_respaldo = dict(zip(gastos_agrupados["Categoria_Resumen"], gastos_agrupados["Valor"]))
    
    # --- CONSTRUCCIÓN DE DESGLOSES ---
    desglose_bancos_ingresos = []
    for row in df_bancos.iter_rows(named=True):
        nombre_banco = row["Origen"].capitalize()
        if row["Origen"] == "ALIANZA":
            valor_neto = ajustes.get("ALIANZA", {}).get("ingresos", 0.0)
        else:
            valor_neto = row["Ingresos_Operativos"]
            
        desglose_bancos_ingresos.append({"Concepto": f"Ingresos {nombre_banco}", "Valor": valor_neto})

    desglose_bancos_salidas = []
    for row in df_bancos.iter_rows(named=True):
        nombre_banco = row["Origen"].capitalize()
        valor_salida = row["Salidas_Operativas"]
        desglose_bancos_salidas.append({"Concepto": f"Salidas {nombre_banco}", "Valor": valor_salida})

    df_caja_ingresos_ccosto = df_global.filter(
        (pl.col("Origen") == "CAJA") & (pl.col("Ingreso") > 0) & (pl.col("Categoria_Flujo") != "Traslado_Salida")
    ).group_by("NOMBRE_CCO").agg(pl.col("Ingreso").sum().alias("Valor")).sort("Valor", descending=True)
    
    desglose_caja_ingresos = [{"Concepto": f"   > C.C: {row['NOMBRE_CCO'].title()}", "Valor": row["Valor"]} for row in df_caja_ingresos_ccosto.iter_rows(named=True)]
    suma_ingresos_desglose = sum(item["Valor"] for item in desglose_caja_ingresos)
    dif_ingresos = ingresos_caja_bruto - suma_ingresos_desglose
    if abs(dif_ingresos) > 0.01:
        desglose_caja_ingresos.append({"Concepto": "   > Ajustes / Otros Ingresos", "Valor": dif_ingresos})

    df_caja_salidas_ccosto = df_global.filter(
        (pl.col("Origen") == "CAJA") & (pl.col("Egreso") > 0) & (pl.col("Categoria_Flujo") == "Operacion_Normal")
    ).group_by("NOMBRE_CCO").agg(pl.col("Egreso").sum().alias("Valor")).sort("Valor", descending=True)
    
    desglose_caja_salidas = [{"Concepto": f"   > C.C: {row['NOMBRE_CCO'].title()}", "Valor": row["Valor"]} for row in df_caja_salidas_ccosto.iter_rows(named=True)]
    suma_salidas_desglose = sum(item["Valor"] for item in desglose_caja_salidas)
    dif_salidas = salidas_caja - suma_salidas_desglose
    if abs(dif_salidas) > 0.01:
        desglose_caja_salidas.append({"Concepto": "   > Ajuste Cruce Contable (Ej: Don Diego)", "Valor": dif_salidas})

    df_prov_pagos_caja = df_global.filter((pl.col("Origen") == "CAJA") & (pl.col("Egreso") > 0) & condicion_proveedores)
    total_pagos_caja = df_prov_pagos_caja["Egreso"].sum()
    df_prov_caja_agrupado = df_prov_pagos_caja.group_by("Tercero").agg(pl.col("Egreso").sum().alias("Valor")).sort("Valor", descending=True)
    desglose_proveedores_caja = [{"Concepto": f"   > Prov Caja: {row['Tercero'].title()}", "Valor": row["Valor"]} for row in df_prov_caja_agrupado.iter_rows(named=True)]

    df_prov_pagos_bancos = df_global.filter((pl.col("Origen") != "CAJA") & (pl.col("Egreso") > 0) & condicion_proveedores)
    total_pagos_bancos = df_prov_pagos_bancos["Egreso"].sum()
    df_prov_bancos_agrupado = df_prov_pagos_bancos.group_by("Tercero").agg(pl.col("Egreso").sum().alias("Valor")).sort("Valor", descending=True)
    desglose_proveedores_bancos = [{"Concepto": f"   > Prov Banco: {row['Tercero'].title()}", "Valor": row["Valor"]} for row in df_prov_bancos_agrupado.iter_rows(named=True)]

    total_abonos = total_pagos_caja + total_pagos_bancos + total_supply

    # ENSAMBLAJE FINAL
    estructura_resumen = [{"Concepto": "DETALLE DE INGRESOS BANCARIOS", "Valor": None}]
    estructura_resumen.extend(desglose_bancos_ingresos)
    estructura_resumen.extend([{"Concepto": "Total Ingresos x Bancos", "Valor": ingresos_bancos}, {"Concepto": "DETALLE DE INGRESOS POR CAJA", "Valor": None}])
    estructura_resumen.extend(desglose_caja_ingresos)
    estructura_resumen.extend([
        {"Concepto": "Total Ingresos x Caja", "Valor": ingresos_caja_bruto},
        {"Concepto": "Total Ingresos del mes", "Valor": total_ingresos_mes},
        {"Concepto": "", "Valor": None}, 
        {"Concepto": "Saldo inicial del mes anterior", "Valor": saldo_inicial_total},
        {"Concepto": "Total Disponible", "Valor": total_disponible},
        {"Concepto": "", "Valor": None}, 
        {"Concepto": "DETALLE DE SALIDAS BANCARIAS", "Valor": None}
    ])
    estructura_resumen.extend(desglose_bancos_salidas)
    estructura_resumen.extend([{"Concepto": "Total Salidas x Bancos", "Valor": salidas_bancos}, {"Concepto": "DETALLE DE SALIDAS POR CAJA", "Valor": None}])
    estructura_resumen.extend(desglose_caja_salidas)
    estructura_resumen.extend([
        {"Concepto": "Total Salidas x Caja", "Valor": salidas_caja},
        {"Concepto": "Total salidas del mes", "Valor": salidas_bancos + salidas_caja},
        {"Concepto": "", "Valor": None},
        {"Concepto": "PROVEEDORES", "Valor": None},
        {"Concepto": "Pagos por Caja", "Valor": total_pagos_caja},
        {"Concepto": "Pagos por Bancos", "Valor": total_pagos_bancos},
        {"Concepto": "Créditos Supply", "Valor": total_supply},
        {"Concepto": "Total Abonos", "Valor": total_abonos},
        
        # ---> LÍNEA DE CRÉDITOS SUPPLY (2205) AÑADIDA AQUÍ <---
        
        {"Concepto": "DESGLOSE DE PROVEEDORES (CAJA)", "Valor": None}
    ])
    estructura_resumen.extend(desglose_proveedores_caja)
    estructura_resumen.extend([{"Concepto": "DESGLOSE DE PROVEEDORES (BANCOS)", "Valor": None}])
    estructura_resumen.extend(desglose_proveedores_bancos)

    # --- INCORPORACIÓN DINÁMICA DE GASTOS OPERACIONALES ---
    estructura_resumen.extend([
        {"Concepto": "", "Valor": None},
        {"Concepto": "SALIDAS POR GASTOS OPERACIONALES", "Valor": None},
    ])

    if DICT_GASTOS_OFICIAL:
        for concepto, valor in sorted(DICT_GASTOS_OFICIAL.items(), key=lambda x: x[1], reverse=True):
            estructura_resumen.append({"Concepto": concepto, "Valor": valor})
    else:
        estructura_resumen.extend([
            {"Concepto": "Nomina Administrativa y Ventas", "Valor": dict_gastos_respaldo.get("Nomina Administrativa y Ventas", 0)},
            {"Concepto": "Seguridad Social", "Valor": dict_gastos_respaldo.get("Seguridad Social", 0)},
            {"Concepto": "Obligaciones financieras", "Valor": dict_gastos_respaldo.get("Obligaciones financieras", 0)},
            {"Concepto": "Comisiones y Gastos Bancarios", "Valor": dict_gastos_respaldo.get("Comisiones y Gastos Bancarios", 0)},
            {"Concepto": "Arrendamientos (Incluye Renting)", "Valor": dict_gastos_respaldo.get("Arrendamientos (Incluye Renting)", 0)},
            {"Concepto": "Servicios", "Valor": dict_gastos_respaldo.get("Servicios", 0)},
            {"Concepto": "Seguros", "Valor": dict_gastos_respaldo.get("Seguros", 0)},
            {"Concepto": "Honorarios", "Valor": dict_gastos_respaldo.get("Honorarios", 0)},
            {"Concepto": "Otros Proveedores / Gastos", "Valor": dict_gastos_respaldo.get("Otros Proveedores / Gastos", 0)}
        ])
    
    return pd.DataFrame(estructura_resumen)