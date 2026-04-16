# src/data_engine/transformers/rules_caja.py
import polars as pl
import pandas as pd
import sqlite3
import os
import re
from src.utils.data_loader import DataLoader

def procesar_datos_grafico_egresos():
    """
    Extrae, cruza y calcula todos los datos necesarios para el gráfico de egresos interactivo.
    Retorna un diccionario con las jerarquías de datos listas para la UI.
    """
    resultados = {
        "datos_gen_entidades": {},
        "datos_ban_entidades": {},
        "datos_caj_entidades": {},
        "datos_caj_categorias": {},
        "datos_caj_prov_detalle": {},
        "datos_caj_gas_detalle": {},
        "datos_caj_nom_detalle": {}
    }

    # 1. Cargar dependencias usando DataLoader (reutilizamos lo que ya limpiamos antes)
    mapeo_cajas, mapeo_docs = DataLoader.load_mapeos_caja()
    dict_cuentas_2335 = DataLoader.load_cuentas_2335()
    proveedores_lista = DataLoader.load_proveedores()

    # 2. Resumen General (Base Resumen Parquet)
    if DataLoader.has_data():
        try:
            df_res = DataLoader.load_parquet("base_resumen").to_pandas()
            try: 
                resultados["datos_gen_entidades"] = {
                    "Bancos": df_res.loc[df_res['Concepto'] == 'Total Salidas x Bancos', 'Valor'].values[0], 
                    "CAJA": df_res.loc[df_res['Concepto'] == 'Total Salidas x Caja', 'Valor'].values[0]
                }
            except: pass
            
            try:
                idx_start = df_res.index[df_res['Concepto'] == 'DETALLE DE SALIDAS BANCARIAS'][0]
                idx_end = df_res.index[df_res['Concepto'] == 'Total Salidas x Bancos'][0]
                for _, row in df_res.iloc[idx_start+1 : idx_end].iterrows():
                    if pd.notna(row['Valor']) and row['Valor'] > 0: 
                        resultados["datos_ban_entidades"][str(row['Concepto']).replace("Salidas ", "").upper()] = row['Valor']
            except: pass
            
            try:
                idx_start = df_res.index[df_res['Concepto'] == 'DETALLE DE SALIDAS POR CAJA'][0]
                idx_end = df_res.index[df_res['Concepto'] == 'Total Salidas x Caja'][0]
                ajuste_cruce = 0.0
                for _, row in df_res.iloc[idx_start+1 : idx_end].iterrows():
                    if pd.notna(row['Valor']):
                        key_raw = str(row['Concepto']).upper()
                        val = float(row['Valor'])
                        if "AJUSTE CRUCE" in key_raw or "DON DIEGO" in key_raw:
                            ajuste_cruce += val
                        elif val > 0:
                            key_clean = str(row['Concepto']).replace("   > C.C: ", "").replace("   > ", "").strip().upper()
                            resultados["datos_caj_entidades"][key_clean] = val
                
                if "CAJA POPAYAN PPAL" in resultados["datos_caj_entidades"] and ajuste_cruce != 0:
                    resultados["datos_caj_entidades"]["CAJA POPAYAN PPAL"] -= abs(ajuste_cruce)
                    if resultados["datos_caj_entidades"]["CAJA POPAYAN PPAL"] < 0: 
                        resultados["datos_caj_entidades"]["CAJA POPAYAN PPAL"] = 0.0
            except: pass
        except: pass

    # 3. Proveedores de Caja (Base Global)
    mapping_numero_caja = {}
    if os.path.exists("local_cache/base_global.parquet"):
        try:
            df_global = pl.read_parquet("local_cache/base_global.parquet").to_pandas()
            df_caja = df_global[
                (df_global['Origen'].str.upper() == 'CAJA') & 
                (df_global['Egreso'] > 0) &
                (df_global['Categoria_Flujo'] == 'Operacion_Normal')
            ].copy()
            df_caja['CCO_Clean'] = df_caja['NOMBRE_CCO'].astype(str).str.extract(r'(\d{5})', expand=False)
            df_caja['Caja_Real'] = df_caja['CCO_Clean'].map(mapeo_cajas).fillna(df_caja['NOMBRE_CCO']).str.upper()
            df_caja['EsProv'] = df_caja['Tercero'].apply(lambda x: str(x).strip().upper() in proveedores_lista if pd.notna(x) else False)
            
            if 'Numero_Doc' in df_caja.columns:
                for _, row in df_caja.iterrows():
                    num = str(row['Numero_Doc']).strip().replace(".0", "")
                    caja = str(row['Caja_Real']).upper()
                    if num and num != "NAN":
                        mapping_numero_caja[num] = caja
            
            provs_caja = df_caja[df_caja['EsProv']].copy()
            for _, row in provs_caja.iterrows():
                c = str(row['Caja_Real'])
                v = float(row['Egreso'])
                prov_name = str(row['Tercero']).strip().title()
                
                if c not in resultados["datos_caj_categorias"]: resultados["datos_caj_categorias"][c] = {"Proveedores": 0.0, "Gastos Operacionales": 0.0, "Nómina": 0.0}
                if c not in resultados["datos_caj_prov_detalle"]: resultados["datos_caj_prov_detalle"][c] = {}
                    
                resultados["datos_caj_categorias"][c]["Proveedores"] += v
                resultados["datos_caj_prov_detalle"][c][prov_name] = resultados["datos_caj_prov_detalle"][c].get(prov_name, 0.0) + v
        except: pass

    # 4. Gastos (Excel 2335)
    df_gastos = DataLoader.load_excel(f"{DataLoader.CACHE_DIR}/gastos_2335.xlsx")
    if not df_gastos.empty:
        try:
            df_gastos.columns = df_gastos.columns.str.strip().str.upper()
            if 'MCNVALDEBI' in df_gastos.columns and 'MCNNUMEDOC' in df_gastos.columns:
                df_gastos['MCNVALDEBI'] = pd.to_numeric(df_gastos['MCNVALDEBI'], errors='coerce').fillna(0)
                df_pagos = df_gastos[df_gastos['MCNVALDEBI'] > 0].copy()
                
                df_pagos['MCNNUMEDOC_str'] = df_pagos['MCNNUMEDOC'].astype(str).str.strip().str.replace(".0", "", regex=False)
                df_pagos['Origen_Caja'] = df_pagos['MCNNUMEDOC_str'].apply(lambda x: mapping_numero_caja.get(x, "OTRO"))
                
                def mapear_cuenta(codigo):
                    cod_str = str(codigo).strip()
                    if cod_str.endswith(".0"): cod_str = cod_str[:-2]
                    if cod_str in dict_cuentas_2335: return dict_cuentas_2335[cod_str]
                    if len(cod_str) >= 6:
                        raiz = cod_str[:6]
                        for c_bd, n_bd in dict_cuentas_2335.items():
                            if str(c_bd).startswith(raiz): return n_bd
                    return "Otros Gastos 2335"

                df_pagos['Categoria'] = df_pagos['MCNCUENTA'].apply(mapear_cuenta)
                
                df_pagos_caja = df_pagos[df_pagos['Origen_Caja'] != "OTRO"].copy()
                for _, row in df_pagos_caja.iterrows():
                    c = str(row['Origen_Caja'])
                    v = float(row['MCNVALDEBI'])
                    cat = str(row['Categoria'])
                    
                    if c not in resultados["datos_caj_categorias"]: resultados["datos_caj_categorias"][c] = {"Proveedores": 0.0, "Gastos Operacionales": 0.0, "Nómina": 0.0}
                    if c not in resultados["datos_caj_gas_detalle"]: resultados["datos_caj_gas_detalle"][c] = {}
                        
                    resultados["datos_caj_categorias"][c]["Gastos Operacionales"] += v
                    resultados["datos_caj_gas_detalle"][c][cat] = resultados["datos_caj_gas_detalle"][c].get(cat, 0.0) + v
        except: pass

    # 5. Nómina (Excel 25)
    df_nom = DataLoader.load_excel(f"{DataLoader.CACHE_DIR}/aux_nomina_25.xlsx")
    if not df_nom.empty:
        try:
            df_nom.columns = df_nom.columns.str.strip().str.upper()
            if 'MCNVALDEBI' in df_nom.columns:
                df_nom['MCNVALDEBI'] = pd.to_numeric(df_nom['MCNVALDEBI'], errors='coerce').fillna(0)
                df_pagos_nom = df_nom[df_nom['MCNVALDEBI'] > 0].copy()
                
                col_doc = next((col for col in ['MCNTIPODOC', 'TIPO', 'TIPODOC'] if col in df_pagos_nom.columns), None)
                    
                if col_doc:
                    df_pagos_nom['TIPO_DOC_CLEAN'] = df_pagos_nom[col_doc].astype(str).str.strip().str.upper()
                    df_caja_nom = df_pagos_nom[df_pagos_nom['TIPO_DOC_CLEAN'].str.startswith('ES')].copy()
                    
                    for _, row in df_caja_nom.iterrows():
                        tipo_doc = row['TIPO_DOC_CLEAN']
                        v = float(row['MCNVALDEBI'])
                        tipo_base = tipo_doc[:4] if len(tipo_doc) >= 4 else tipo_doc
                        caja_destino = mapeo_docs.get(tipo_base, "OTRA")
                        
                        if caja_destino != "OTRA":
                            c = str(caja_destino).upper()
                            empleado_col = 'VINNOMBRE' if 'VINNOMBRE' in df_caja_nom.columns else 'MCNDETALLE'
                            empleado = str(row.get(empleado_col, 'EMPLEADO')).strip().title()
                            
                            if c not in resultados["datos_caj_categorias"]:
                                resultados["datos_caj_categorias"][c] = {"Proveedores": 0.0, "Gastos Operacionales": 0.0, "Nómina": 0.0}
                            if "Nómina" not in resultados["datos_caj_categorias"][c]:
                                resultados["datos_caj_categorias"][c]["Nómina"] = 0.0
                            if c not in resultados["datos_caj_nom_detalle"]:
                                resultados["datos_caj_nom_detalle"][c] = {}
                                
                            resultados["datos_caj_categorias"][c]["Nómina"] += v
                            resultados["datos_caj_nom_detalle"][c][empleado] = resultados["datos_caj_nom_detalle"][c].get(empleado, 0.0) + v
        except: pass
        
    # 6. Regla de Equilibrio
    for c, v_total in resultados["datos_caj_entidades"].items():
        if c not in resultados["datos_caj_categorias"]:
            resultados["datos_caj_categorias"][c] = {"Proveedores": 0.0, "Gastos Operacionales": 0.0, "Nómina": 0.0, "Otros Egresos": v_total}
        else:
            sum_identificados = (
                resultados["datos_caj_categorias"][c].get("Proveedores", 0.0) + 
                resultados["datos_caj_categorias"][c].get("Gastos Operacionales", 0.0) +
                resultados["datos_caj_categorias"][c].get("Nómina", 0.0)
            )
            diff = v_total - sum_identificados
            
            if diff > 1000: 
                resultados["datos_caj_categorias"][c]["Otros Egresos"] = diff
            elif diff < -1000:
                exceso = abs(diff)
                if resultados["datos_caj_categorias"][c].get("Gastos Operacionales", 0.0) >= exceso:
                    resultados["datos_caj_categorias"][c]["Gastos Operacionales"] -= exceso
                elif resultados["datos_caj_categorias"][c].get("Proveedores", 0.0) >= exceso:
                    resultados["datos_caj_categorias"][c]["Proveedores"] -= exceso

    return resultados