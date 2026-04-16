# src/data_engine/reports/constructor_resumen.py
import polars as pl
import pandas as pd
from src.utils.data_loader import DataLoader

AJUSTE_INGRESOS_CAJA = 0

def _mapear_cuenta_gasto(codigo, detalle, dict_cuentas_2335):
    """Reglas de negocio para categorizar un gasto según su cuenta o detalle."""
    cod_str = str(codigo).strip()
    if cod_str.endswith(".0"): 
        cod_str = cod_str[:-2]
    
    # Excepción explícita
    if cod_str == "23359526":
        return "Finansuenos Sas"
        
    if cod_str in dict_cuentas_2335: 
        return dict_cuentas_2335[cod_str]
        
    if len(cod_str) >= 6:
        raiz = cod_str[:6]
        for c_bd, n_bd in dict_cuentas_2335.items():
            if str(c_bd).startswith(raiz): 
                return n_bd
                
    # Mapeo por palabras clave en el detalle
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

def _procesar_gastos_oficiales(mapeo_docs_caja, dict_cuentas_2335):
    """Extrae y categoriza los gastos oficiales desde el Excel de cuentas 2335."""
    dict_gastos = {}
    df_gastos = DataLoader.load_excel(f"{DataLoader.CACHE_DIR}/gastos_2335.xlsx")
    
    if not df_gastos.empty:
        df_gastos.columns = df_gastos.columns.str.strip().str.upper()
        if 'MCNCUENTA' in df_gastos.columns and 'MCNVALDEBI' in df_gastos.columns:
            df_gastos['MCNVALDEBI'] = pd.to_numeric(df_gastos['MCNVALDEBI'], errors='coerce').fillna(0)
            df_pagos = df_gastos[df_gastos['MCNVALDEBI'] > 0].copy()
            
            col_doc = 'MCNTIPODOC' if 'MCNTIPODOC' in df_pagos.columns else None
            df_pagos['Origen_Caja'] = df_pagos[col_doc].apply(lambda x: mapeo_docs_caja.get(str(x).strip().upper(), "OTRAS CAJAS")) if col_doc else "OTRAS CAJAS"
            
            col_detalle = 'CTANOMBRE' if 'CTANOMBRE' in df_pagos.columns else ('MCNDETALLE' if 'MCNDETALLE' in df_pagos.columns else None)
            df_pagos['Categoria_Gasto'] = df_pagos.apply(lambda x: _mapear_cuenta_gasto(x['MCNCUENTA'], x[col_detalle] if col_detalle else "", dict_cuentas_2335), axis=1)
            
            agrupado = df_pagos.groupby('Categoria_Gasto')['MCNVALDEBI'].sum()
            for cat, valor in agrupado.items():
                if valor > 0:
                    dict_gastos[cat] = float(valor)
    return dict_gastos

def armar_resumen_gerencial(df_global: pl.DataFrame, df_detallado: pl.DataFrame, ajustes: dict = None) -> pd.DataFrame:
    if ajustes is None:
        ajustes = {}

    # 1. Cargar todas las dependencias estáticas y auxiliares
    proveedores_lista = DataLoader.load_proveedores()
    dict_cuentas_2335 = DataLoader.load_cuentas_2335()
    mapeo_cajas_bd, mapeo_docs_caja = DataLoader.load_mapeos_caja()
    
    total_supply = DataLoader.get_total_supply()
    total_nomina = DataLoader.get_total_nomina_cajas()
    dict_gastos_oficial = _procesar_gastos_oficiales(mapeo_docs_caja, dict_cuentas_2335)

    # 2. Reemplazo de Cajas en el DataFrame Global
    if "NOMBRE_CCO" in df_global.columns:
        df_global = df_global.with_columns(
            pl.col("NOMBRE_CCO").cast(pl.Utf8).str.extract(r"(\d{5})").replace_strict(mapeo_cajas_bd, default=pl.col("NOMBRE_CCO")).alias("NOMBRE_CCO")
        )

    # 3. Atrapando flujos específicos (Finansuenos, Libranzas, Aportes)
    finansuenos_caja = df_global.filter(
        (pl.col("Origen") == "CAJA") & 
        (pl.col("Tercero").str.to_uppercase().str.contains("FINANSUENOS")) &
        (~pl.col("Documento_Referencia").str.to_uppercase().str.starts_with("ES"))
    )["Egreso"].sum()
    if finansuenos_caja > 0:
        dict_gastos_oficial["Finansuenos Sas"] = dict_gastos_oficial.get("Finansuenos Sas", 0) + finansuenos_caja

    libranzas_bancos = df_global.filter((pl.col("Origen") == "CAJA_BANCOS") & (pl.col("Categoria_Flujo") == "Libranzas"))["Egreso"].sum()
    if libranzas_bancos > 0:
        dict_gastos_oficial["Libranzas"] = dict_gastos_oficial.get("Libranzas", 0) + libranzas_bancos

    aportes_bancos = df_global.filter((pl.col("Origen") == "CAJA_BANCOS") & (pl.col("Categoria_Flujo") == "Seguridad Social"))["Egreso"].sum()
    if aportes_bancos > 0:
        dict_gastos_oficial["Seguridad Social"] = dict_gastos_oficial.get("Seguridad Social", 0) + aportes_bancos

    # 4. Cálculos de Disponibilidad e Ingresos
    try:
        ajuste_don_diego = df_global.filter((pl.col("Origen") == "CAJA") & (pl.col("Categoria_Flujo") == "Ajuste_Don_Diego"))["Ingreso"].sum()
    except:
        ajuste_don_diego = 0.0

    df_bancos = df_detallado.filter(~pl.col("Origen").is_in(["CAJA", "TOTAL BANCOS", "BANCO + CAJA"]))
    total_bancos_ingresos = df_bancos["Ingresos_Operativos"].sum() 
    total_bancos_salidas_traslados = df_bancos["Salidas_por_Traslados"].sum()
    salida_traslado_alianza = df_bancos.filter(pl.col("Origen") == "ALIANZA")["Salidas_por_Traslados"].sum()
    
    ingresos_bancos = total_bancos_ingresos - total_bancos_salidas_traslados + salida_traslado_alianza
    ingresos_caja_bruto = df_global.filter((pl.col("Origen") == "CAJA") & (pl.col("Ingreso") != 0) & (pl.col("Categoria_Flujo") != "Traslado_Salida"))["Ingreso"].sum()
    
    total_ingresos_mes = ingresos_bancos + ingresos_caja_bruto
    saldo_inicial_total = df_detallado.filter(pl.col("Origen") == "BANCO + CAJA")["Saldo_Inicial"].sum()
    total_disponible = total_ingresos_mes + saldo_inicial_total

    # 5. Cálculos de Salidas
    salidas_bancos = df_bancos["Salidas_Operativas"].sum()
    salidas_caja = df_detallado.filter(pl.col("Origen") == "CAJA")["Salidas_Operativas"].sum()
    
    if proveedores_lista:
        condicion_proveedores = (
            pl.col("Tercero").fill_null("").str.to_uppercase().str.strip_chars().is_in(proveedores_lista) &
            (pl.col("Categoria_Flujo") != "Libranzas") &
            (pl.col("Categoria_Flujo") != "Seguridad Social")
        )
    else:
        condicion_proveedores = (
            ((pl.col("Origen") == "CAJA") & (pl.col("Documento_Referencia").fill_null("").str.starts_with("EB"))) | 
            (pl.col("Origen") == "CAJA_BANCOS")
        ) & (~pl.col("Tercero").fill_null("").str.to_uppercase().str.contains("FINANSUENOS SAS")) & (pl.col("Categoria_Flujo") != "Libranzas") & (pl.col("Categoria_Flujo") != "Seguridad Social")

    df_egresos = df_global.filter(
        (pl.col("Egreso") != 0) & 
        (pl.col("Categoria_Flujo") == "Operacion_Normal") & 
        ~condicion_proveedores & 
        (~pl.col("Tercero").str.to_uppercase().str.contains("FINANSUENOS"))
    )
    
    df_categorizado = df_egresos.with_columns(pl.when(pl.col("Concepto").str.contains(r"(?i)NOMIN|LIBRANZA|QUINCENA|SUELDO")).then(pl.lit("Nomina Administrativa y Ventas")).otherwise(pl.lit("Otros Proveedores / Gastos")).alias("Categoria_Resumen"))
    gastos_agrupados = df_categorizado.group_by("Categoria_Resumen").agg(pl.col("Egreso").sum().alias("Valor"))
    dict_gastos_respaldo = dict(zip(gastos_agrupados["Categoria_Resumen"], gastos_agrupados["Valor"]))
    
    # 6. Desgloses para el reporte
    desglose_bancos_ingresos = []
    for row in df_bancos.iter_rows(named=True):
        nombre_banco = row["Origen"].capitalize()
        valor_neto = ajustes.get("ALIANZA", {}).get("ingresos", 0.0) if row["Origen"] == "ALIANZA" else row["Ingresos_Operativos"]
        desglose_bancos_ingresos.append({"Concepto": f"Ingresos {nombre_banco}", "Valor": valor_neto})

    desglose_bancos_salidas = [{"Concepto": f"Salidas {r['Origen'].capitalize()}", "Valor": r["Salidas_Operativas"]} for r in df_bancos.iter_rows(named=True)]

    df_caja_ingresos_ccosto = df_global.filter((pl.col("Origen") == "CAJA") & (pl.col("Ingreso") != 0) & (pl.col("Categoria_Flujo") != "Traslado_Salida")).group_by("NOMBRE_CCO").agg(pl.col("Ingreso").sum().alias("Valor")).sort("Valor", descending=True)
    desglose_caja_ingresos = [{"Concepto": f"   > C.C: {row['NOMBRE_CCO'].title()}", "Valor": row["Valor"]} for row in df_caja_ingresos_ccosto.iter_rows(named=True)]
    
    dif_ingresos = ingresos_caja_bruto - sum(item["Valor"] for item in desglose_caja_ingresos)
    if abs(dif_ingresos) > 0.01: desglose_caja_ingresos.append({"Concepto": "   > Ajustes / Otros Ingresos", "Valor": dif_ingresos})

    df_caja_salidas_ccosto = df_global.filter((pl.col("Origen") == "CAJA") & (pl.col("Egreso") != 0) & (pl.col("Categoria_Flujo") == "Operacion_Normal")).group_by("NOMBRE_CCO").agg(pl.col("Egreso").sum().alias("Valor")).sort("Valor", descending=True)
    desglose_caja_salidas = []
    for row in df_caja_salidas_ccosto.iter_rows(named=True):
        nombre_caja = row['NOMBRE_CCO'].title()
        valor_caja = row["Valor"] - ajuste_don_diego if ("Popayan" in nombre_caja or "Popayán" in nombre_caja) and ajuste_don_diego > 0 else row["Valor"]
        desglose_caja_salidas.append({"Concepto": f"   > C.C: {nombre_caja}", "Valor": valor_caja})
        
    dif_salidas = salidas_caja - sum(item["Valor"] for item in desglose_caja_salidas)
    if abs(dif_salidas) > 0.01: 
        desglose_caja_salidas.append({"Concepto": "   > Ajuste Cruce Contable", "Valor": dif_salidas})

    df_prov_pagos_caja = df_global.filter((pl.col("Origen") == "CAJA") & (pl.col("Egreso") != 0) & condicion_proveedores)
    total_pagos_caja = df_prov_pagos_caja["Egreso"].sum()
    desglose_proveedores_caja = [{"Concepto": f"   > Prov Caja: {row['Tercero'].title()}", "Valor": row["Valor"]} for row in df_prov_pagos_caja.group_by("Tercero").agg(pl.col("Egreso").sum().alias("Valor")).sort("Valor", descending=True).iter_rows(named=True)]

    df_prov_pagos_bancos = df_global.filter((pl.col("Origen") != "CAJA") & (pl.col("Egreso") != 0) & condicion_proveedores)
    total_pagos_bancos = df_prov_pagos_bancos["Egreso"].sum()
    desglose_proveedores_bancos = [{"Concepto": f"   > Prov Banco: {row['Tercero'].title()}", "Valor": row["Valor"]} for row in df_prov_pagos_bancos.group_by("Tercero").agg(pl.col("Egreso").sum().alias("Valor")).sort("Valor", descending=True).iter_rows(named=True)]

    total_abonos = total_pagos_caja + total_pagos_bancos + total_supply

    # 7. ENSAMBLAJE FINAL
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
        {"Concepto": "DESGLOSE DE PROVEEDORES (CAJA)", "Valor": None}
    ])
    estructura_resumen.extend(desglose_proveedores_caja)
    estructura_resumen.extend([{"Concepto": "DESGLOSE DE PROVEEDORES (BANCOS)", "Valor": None}])
    estructura_resumen.extend(desglose_proveedores_bancos)

    estructura_resumen.extend([
        {"Concepto": "", "Valor": None},
        {"Concepto": "PAGO DE NÓMINA Y PRESTACIONES (AUX 25) - CAJAS", "Valor": total_nomina} if total_nomina > 0 else None,
        {"Concepto": "", "Valor": None},
        {"Concepto": "SALIDAS POR GASTOS OPERACIONALES", "Valor": None},
    ])
    
    estructura_resumen = [item for item in estructura_resumen if item is not None]

    if dict_gastos_oficial:
        for concepto, valor in sorted(dict_gastos_oficial.items(), key=lambda x: x[1], reverse=True):
            if "NOMINA" not in concepto.upper() and "SUELDO" not in concepto.upper():
                estructura_resumen.append({"Concepto": concepto, "Valor": valor})
    else:
        estructura_resumen.extend([
            {"Concepto": "Finansuenos Sas", "Valor": dict_gastos_respaldo.get("Finansuenos Sas", 0)},
            {"Concepto": "Libranzas", "Valor": dict_gastos_respaldo.get("Libranzas", 0)},
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