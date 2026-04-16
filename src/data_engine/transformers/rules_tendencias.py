# src/data_engine/transformers/rules_tendencias.py
import polars as pl
import pandas as pd
from src.utils.data_loader import DataLoader

def _obtener_metas_doradas():
    """Extrae los valores PERFECTOS calculados por la dona mensual"""
    datos_gen, datos_ban, datos_caj = {}, {}, {}
    if not DataLoader.has_data(): return datos_gen, datos_ban, datos_caj
    
    try:
        df_res = DataLoader.load_parquet("base_resumen").to_pandas()
        
        # General
        val_ban = df_res.loc[df_res['Concepto'] == 'Total Salidas x Bancos', 'Valor']
        if not val_ban.empty: datos_gen["Bancos"] = float(val_ban.values[0])
        val_caj = df_res.loc[df_res['Concepto'] == 'Total Salidas x Caja', 'Valor']
        if not val_caj.empty: datos_gen["Caja"] = float(val_caj.values[0])
        
        # Bancos
        idx_start = df_res.index[df_res['Concepto'] == 'DETALLE DE SALIDAS BANCARIAS'][0]
        idx_end = df_res.index[df_res['Concepto'] == 'Total Salidas x Bancos'][0]
        for _, row in df_res.iloc[idx_start+1 : idx_end].iterrows():
            if pd.notna(row['Valor']) and row['Valor'] > 0:
                datos_ban[str(row['Concepto']).replace("Salidas ", "").strip().capitalize()] = float(row['Valor'])
        
        # Cajas
        idx_start = df_res.index[df_res['Concepto'] == 'DETALLE DE SALIDAS POR CAJA'][0]
        idx_end = df_res.index[df_res['Concepto'] == 'Total Salidas x Caja'][0]
        ajuste_cruce = 0.0
        for _, row in df_res.iloc[idx_start+1 : idx_end].iterrows():
            if pd.notna(row['Valor']):
                k = str(row['Concepto']).upper()
                v = float(row['Valor'])
                if "AJUSTE CRUCE" in k or "DON DIEGO" in k: ajuste_cruce += v
                elif v > 0: datos_caj[k.replace("   > C.C: ", "").replace("   > ", "").strip()] = v
        
        if "CAJA POPAYAN PPAL" in datos_caj and ajuste_cruce != 0:
            datos_caj["CAJA POPAYAN PPAL"] = max(0, datos_caj["CAJA POPAYAN PPAL"] - abs(ajuste_cruce))
    except: pass
    
    return datos_gen, datos_ban, datos_caj

def procesar_tendencias(nivel_actual: str, caja_seleccionada: str = None) -> tuple:
    """Procesa el dataframe global y retorna (categorias_activas, datos_diarios)"""
    categorias_activas = []
    datos_diarios = {}
    
    dias_cortos = {0:"Lun",1:"Mar",2:"Mie",3:"Jue",4:"Vie",5:"Sab",6:"Dom"}
    dias_completos = {0:"Lunes",1:"Martes",2:"Miercoles",3:"Jueves",4:"Viernes",5:"Sabado",6:"Domingo"}

    try:
        df = DataLoader.load_parquet("base_global").to_pandas()
        if df.empty: return categorias_activas, datos_diarios
        
        df["Fecha"] = pd.to_datetime(df["Fecha"], dayfirst=True, errors="coerce")
        df = df.dropna(subset=["Fecha"])
        df["Dia"] = df["Fecha"].dt.day
        df["Dia_Semana"] = df["Fecha"].dt.dayofweek

        mapeo_cajas, mapeo_docs = DataLoader.load_mapeos_caja()
        prov_lista = DataLoader.load_proveedores()
        targets_gen, targets_ban, targets_caj = _obtener_metas_doradas()

        df = df[df["Origen"].str.strip().str.upper() != "CAJA_BANCOS"].copy()
        mask_bc = (df["Origen"].str.strip().str.upper() == "BANCOLOMBIA") & (df["Concepto"].str.upper().str.contains("TRASL ENTRE FONDOS DE VALORES", na=False))
        df.loc[mask_bc, "Categoria_Flujo"] = "Traslado_Salida"
        
        df_egr = df[(df["Egreso"] > 0) & (~df["Categoria_Flujo"].isin(["Traslado_Salida", "Traslado_Entrada"]))].copy()
        df_egr['CCO_Clean'] = df_egr['NOMBRE_CCO'].astype(str).str.extract(r'(\d{5})', expand=False)
        df_egr['Caja_Real'] = df_egr['CCO_Clean'].map(mapeo_cajas).fillna(df_egr['NOMBRE_CCO']).str.upper()

        df_final = pd.DataFrame()
        target_dict = {}

        if nivel_actual == "GENERAL":
            df_egr["Categoria"] = df_egr["Origen"].apply(lambda x: "Caja" if str(x).strip().upper() == "CAJA" else "Bancos")
            df_final = df_egr.groupby(["Dia", "Dia_Semana", "Categoria"], as_index=False)["Egreso"].sum()
            target_dict = targets_gen
            
        elif nivel_actual == "BANCOS":
            df_b = df_egr[df_egr["Origen"].str.strip().str.upper() != "CAJA"].copy()
            df_b["Categoria"] = df_b["Origen"].str.capitalize()
            df_final = df_b.groupby(["Dia", "Dia_Semana", "Categoria"], as_index=False)["Egreso"].sum()
            target_dict = targets_ban
            
        elif nivel_actual == "CAJA":
            df_c = df_egr[df_egr["Origen"].str.strip().str.upper() == "CAJA"].copy()
            df_c["Categoria"] = df_c["Caja_Real"]
            df_final = df_c.groupby(["Dia", "Dia_Semana", "Categoria"], as_index=False)["Egreso"].sum()
            target_dict = targets_caj
            
        elif nivel_actual in ["DETALLE_CAJA", "PROVEEDORES_CAJA", "GASTOS_CAJA", "NOMINA_CAJA"] and caja_seleccionada:
            caja_str = str(caja_seleccionada).upper()
            target_dict = {"TOTAL_ESPERADO": targets_caj.get(caja_str, 0.0)}
            
            df_caja_base = df_egr[(df_egr["Origen"].str.strip().str.upper() == "CAJA") & (df_egr["Caja_Real"] == caja_str)].copy()
            df_caja_base["Es_Prov"] = df_caja_base.apply(
                lambda r: (str(r["Tercero"]).strip().upper() in prov_lista) and 
                          (r["Categoria_Flujo"] not in ["Libranzas", "Seguridad Social"]) and
                          ("FINANSUENOS" not in str(r["Tercero"]).upper()), axis=1)
                          
            # --- PROVEEDORES ---
            df_prov_base = df_caja_base[df_caja_base["Es_Prov"]].copy()
            if nivel_actual == "PROVEEDORES_CAJA":
                df_prov_base["Categoria"] = df_prov_base["Tercero"].fillna("Desconocido").str.title()
            else:
                df_prov_base["Categoria"] = "Proveedores"
            df_prov = df_prov_base.groupby(["Dia", "Dia_Semana", "Categoria"], as_index=False)["Egreso"].sum()
            
            mapping_numero_caja = {}
            if 'Numero_Doc' in df_caja_base.columns:
                for _, row in df_caja_base.iterrows():
                    num = str(row['Numero_Doc']).strip().replace(".0", "")
                    if num and num != "NAN": mapping_numero_caja[num] = caja_str

            # --- GASTOS OPERACIONALES ---
            df_gastos = pd.DataFrame()
            df_g = DataLoader.load_excel(f"{DataLoader.CACHE_DIR}/gastos_2335.xlsx")
            if not df_g.empty:
                df_g.columns = df_g.columns.str.strip().str.upper()
                if 'MCNVALDEBI' in df_g.columns and 'MCNFECHA' in df_g.columns and 'MCNNUMEDOC' in df_g.columns:
                    df_g['MCNVALDEBI'] = pd.to_numeric(df_g['MCNVALDEBI'], errors='coerce').fillna(0)
                    df_g = df_g[df_g['MCNVALDEBI'] > 0].copy()
                    df_g['MCNNUMEDOC_str'] = df_g['MCNNUMEDOC'].astype(str).str.strip().str.replace(".0", "", regex=False)
                    df_g['Origen_Caja'] = df_g['MCNNUMEDOC_str'].apply(lambda x: mapping_numero_caja.get(x, "OTRO"))
                    df_g = df_g[df_g['Origen_Caja'] == caja_str].copy()
                    if not df_g.empty:
                        df_g['Fecha'] = pd.to_datetime(df_g['MCNFECHA'], errors='coerce')
                        df_g = df_g.dropna(subset=['Fecha'])
                        df_g['Dia'] = df_g['Fecha'].dt.day
                        df_g['Dia_Semana'] = df_g['Fecha'].dt.dayofweek
                        
                        if nivel_actual == "GASTOS_CAJA":
                            dict_cuentas_2335 = DataLoader.load_cuentas_2335()
                            def mapear_cuenta(codigo):
                                cod_str = str(codigo).strip()
                                if cod_str.endswith(".0"): cod_str = cod_str[:-2]
                                if cod_str in dict_cuentas_2335: return dict_cuentas_2335[cod_str]
                                if len(cod_str) >= 6:
                                    raiz = cod_str[:6]
                                    for c_bd, n_bd in dict_cuentas_2335.items():
                                        if str(c_bd).startswith(raiz): return n_bd
                                return "Otros Gastos 2335"
                            df_g['Categoria'] = df_g['MCNCUENTA'].apply(mapear_cuenta)
                        else:
                            df_g['Categoria'] = "Gastos Operacionales"
                            
                        df_gastos = df_g.groupby(["Dia", "Dia_Semana", "Categoria"], as_index=False)["MCNVALDEBI"].sum().rename(columns={"MCNVALDEBI": "Egreso"})
            
            # --- NÓMINA ---
            df_nomina = pd.DataFrame()
            df_nom = DataLoader.load_excel(f"{DataLoader.CACHE_DIR}/aux_nomina_25.xlsx")
            if not df_nom.empty:
                df_nom.columns = df_nom.columns.str.strip().str.upper()
                if 'MCNVALDEBI' in df_nom.columns and 'MCNFECHA' in df_nom.columns:
                    df_nom['MCNVALDEBI'] = pd.to_numeric(df_nom['MCNVALDEBI'], errors='coerce').fillna(0)
                    df_nom = df_nom[df_nom['MCNVALDEBI'] > 0].copy()
                    col_doc = next((col for col in ['MCNTIPODOC', 'TIPO', 'TIPODOC'] if col in df_nom.columns), None)
                    if col_doc:
                        df_nom['TIPO_DOC_CLEAN'] = df_nom[col_doc].astype(str).str.strip().str.upper()
                        df_nom = df_nom[df_nom['TIPO_DOC_CLEAN'].str.startswith('ES')].copy()
                        df_nom['TIPO_BASE'] = df_nom['TIPO_DOC_CLEAN'].str[:4]
                        df_nom['Origen_Caja'] = df_nom['TIPO_BASE'].apply(lambda x: mapeo_docs.get(x, "OTRA"))
                        df_nom = df_nom[df_nom['Origen_Caja'].str.upper() == caja_str].copy()
                        if not df_nom.empty:
                            df_nom['Fecha'] = pd.to_datetime(df_nom['MCNFECHA'], errors='coerce')
                            df_nom = df_nom.dropna(subset=['Fecha'])
                            df_nom['Dia'] = df_nom['Fecha'].dt.day
                            df_nom['Dia_Semana'] = df_nom['Fecha'].dt.dayofweek
                            
                            if nivel_actual == "NOMINA_CAJA":
                                empleado_col = 'VINNOMBRE' if 'VINNOMBRE' in df_nom.columns else 'MCNDETALLE'
                                df_nom['Categoria'] = df_nom[empleado_col].astype(str).str.strip().str.title()
                            else:
                                df_nom['Categoria'] = "Nómina"
                                
                            df_nomina = df_nom.groupby(["Dia", "Dia_Semana", "Categoria"], as_index=False)["MCNVALDEBI"].sum().rename(columns={"MCNVALDEBI": "Egreso"})

            # --- OTROS EGRESOS ---
            df_otros_base = df_caja_base[~df_caja_base["Es_Prov"]].copy()
            df_otros_base["Categoria"] = "Otros Egresos"
            df_otros = df_otros_base.groupby(["Dia", "Dia_Semana", "Categoria"], as_index=False)["Egreso"].sum()
            
            # --- SELECCIÓN DEL NIVEL FINAL PARA LA GRÁFICA ---
            if nivel_actual == "PROVEEDORES_CAJA":
                df_final = df_prov
            elif nivel_actual == "GASTOS_CAJA":
                df_final = df_gastos
            elif nivel_actual == "NOMINA_CAJA":
                df_final = df_nomina
            else:
                df_final = pd.concat([df_prov, df_gastos, df_nomina, df_otros], ignore_index=True)

        # SINCRONIZADOR AL CENTAVO (Aplica en TODO excepto si estamos viendo detalles internos como Nómina o Gastos individuales)
        if target_dict and not df_final.empty and nivel_actual not in ["PROVEEDORES_CAJA", "GASTOS_CAJA", "NOMINA_CAJA"]:
            if nivel_actual == "DETALLE_CAJA":
                total_esperado = target_dict.get("TOTAL_ESPERADO", 0.0)
                suma_actual = df_final["Egreso"].sum()
                if suma_actual > 0 and total_esperado > 0:
                    df_final["Egreso"] = df_final["Egreso"] * (total_esperado / suma_actual)
            else:
                for cat, target_val in target_dict.items():
                    mask = df_final["Categoria"] == cat
                    sum_actual = df_final.loc[mask, "Egreso"].sum()
                    
                    if sum_actual > 0 and target_val > 0:
                        df_final.loc[mask, "Egreso"] *= (target_val / sum_actual)
                    elif target_val > 0 and sum_actual == 0:
                        # Inyección PDF sin fecha (Día 1)
                        df_final = pd.concat([df_final, pd.DataFrame([{"Dia": 1, "Dia_Semana": 0, "Categoria": cat, "Egreso": target_val}])], ignore_index=True)
                    elif target_val <= 0:
                        df_final.loc[mask, "Egreso"] = 0.0

                # ¡Aquí está corregido el error de indentación!
                cats_validas = list(target_dict.keys())
                df_final = df_final[df_final["Categoria"].isin(cats_validas)].copy()

        if df_final.empty: return categorias_activas, datos_diarios

        # Agrupación Colas Largas
        df_agrupado = df_final.groupby(["Dia", "Dia_Semana", "Categoria"], as_index=False)["Egreso"].sum()
        totales_cat = df_agrupado.groupby("Categoria")["Egreso"].sum().sort_values(ascending=False)
        todas_cats = [c for c in totales_cat.index.tolist() if totales_cat[c] > 0]
        
        if len(todas_cats) > 9:
            top_cats = todas_cats[:8]
            cat_default = "Otras Cajas" if nivel_actual == "CAJA" else "Otras"
            df_agrupado["Categoria"] = df_agrupado["Categoria"].apply(lambda x: x if x in top_cats else cat_default)
            df_agrupado = df_agrupado.groupby(["Dia", "Dia_Semana", "Categoria"], as_index=False)["Egreso"].sum()
            totales_cat = df_agrupado.groupby("Categoria")["Egreso"].sum().sort_values(ascending=False)
            categorias_activas = [c for c in totales_cat.index.tolist() if totales_cat[c] > 0]
        else:
            categorias_activas = todas_cats

        # Consolidación Final
        for d in sorted(df_agrupado["Dia"].unique()):
            subset = df_agrupado[df_agrupado["Dia"] == d]
            dsn = int(subset["Dia_Semana"].iloc[0])
            valores_dia = {cat: float(subset[subset["Categoria"] == cat]["Egreso"].sum()) if cat in subset["Categoria"].values else 0.0 for cat in categorias_activas}
            
            total_dia = round(sum(valores_dia.values()), 2)
            if total_dia > 0:
                datos_diarios[d] = {
                    "label_corta": f"{dias_cortos.get(dsn, '')} {d}", 
                    "label_larga": f"{dias_completos.get(dsn, '')} {d}", 
                    "valores": valores_dia, 
                    "total": total_dia
                }
                
    except Exception as e:
        print(f"Error en procesar_tendencias: {e}")

    return categorias_activas, datos_diarios