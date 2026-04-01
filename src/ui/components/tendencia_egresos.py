# src/ui/components/tendencia_egresos.py
import flet as ft
import polars as pl
import pandas as pd
import sqlite3
import os
import json
import math
from src.core.mapeos import (
    COLORES_FT, COLORES_ENTIDADES, COLORES_BANCOS, COLORES_CAJAS, COLORES_PROVEEDORES,
    obtener_color, obtener_color_proveedor
)

class TendenciaEgresos(ft.Container):
    def __init__(self):
        super().__init__()
        self.expand = True
        self.height = 650 
        self.bgcolor = ft.colors.WHITE
        self.border_radius = 12
        self.padding = ft.padding.all(16)
        self.border = ft.border.all(1, ft.colors.GREY_200)

        self.modo_vista = "ENTIDADES"
        self.nivel_actual = "GENERAL"
        self.caja_seleccionada = None
        self.categorias_activas = []
        self.datos_diarios = {}
        self.proveedores_activos = []

        self.titulo = ft.Text("Tendencia de salidas diarias", weight=ft.FontWeight.W_600, size=15, color=ft.colors.RED_900)

        self.btn_entidades = ft.TextButton("Entidades", on_click=lambda e: self.set_modo("ENTIDADES"))
        self.btn_proveedores = ft.TextButton("Proveedores", on_click=lambda e: self.set_modo("PROVEEDORES"))
        self.btn_gastos = ft.TextButton("Gastos (2335)", on_click=lambda e: self.set_modo("GASTOS")) 

        self.contenedor_tabs = ft.Row([self.btn_entidades, self.btn_proveedores, self.btn_gastos], spacing=0)

        self.dropdown_dias = ft.Dropdown(
            label="Vista", width=200, options=[ft.dropdown.Option(key="ALL", text="Todo el mes")],
            on_change=self.mostrar_detalle_dia, text_size=13, height=50,    
            content_padding=ft.padding.only(left=15, right=10, top=10, bottom=10), value="ALL",
            border_radius=8, border_color=ft.colors.GREY_300, focused_border_color=ft.colors.RED_500,
            label_style=ft.TextStyle(size=12, color=ft.colors.RED_700)
        )

        self.card_total    = self._make_metric_card("Total Salidas", "–")
        self.card_promedio = self._make_metric_card("Promedio diario", "–")
        self.card_maximo   = self._make_metric_card("Salida maxima", "–")
        self.card_mayor    = self._make_metric_card("Mayor entidad", "–")

        self.fila_metricas = ft.Row([self.card_total, self.card_promedio, self.card_maximo, self.card_mayor], spacing=10)
        self.leyenda_row = ft.Row(wrap=True, spacing=8, scroll=ft.ScrollMode.AUTO)
        self.leyenda_container = ft.Container(content=self.leyenda_row, height=50, expand=True)

        self.txt_total_hover = ft.Text("Pasa el mouse sobre el grafico para ver detalles", size=12, color=ft.colors.RED_700, weight=ft.FontWeight.W_600)
        self.panel_hover = ft.Row(wrap=True, spacing=12) 
        self.hover_container = ft.Container(
            content=ft.Column([self.txt_total_hover, self.panel_hover], spacing=4, tight=True),
            padding=ft.padding.symmetric(horizontal=12, vertical=8), bgcolor=ft.colors.RED_50,
            border_radius=8, animate_size=200 
        )

        self.fila_controles = ft.Row([self.contenedor_tabs, ft.Container(width=20), self.dropdown_dias], alignment=ft.MainAxisAlignment.START)
        self.chart_container = ft.Container(height=400)

        self.extraer_datos()
        self._construir_ui()
        self.dibujar_grafico("ALL")

    def _make_metric_card(self, label: str, valor: str) -> ft.Container:
        val = ft.Text(valor, size=15, color=ft.colors.RED_900, weight=ft.FontWeight.W_600)
        return ft.Container(
            content=ft.Column([ft.Text(label, size=10, color=ft.colors.GREY_600), val], spacing=2, tight=True),
            bgcolor=ft.colors.RED_50, border_radius=8, padding=ft.padding.symmetric(horizontal=12, vertical=8), expand=True, data=val
        )

    def _actualizar_metricas(self):
        try:
            totales_dias = [d["total"] for d in self.datos_diarios.values() if d["total"] > 0]
            total_sum = sum(totales_dias)
            promedio = total_sum / len(totales_dias) if totales_dias else 0
            maximo = max(totales_dias) if totales_dias else 0
            
            mayor_cat = "–"
            if self.categorias_activas and self.datos_diarios:
                sumas_cat = {c: sum(d["valores"].get(c, 0) for d in self.datos_diarios.values()) for c in self.categorias_activas}
                mayor_cat = max(sumas_cat, key=sumas_cat.get) if sumas_cat else "–"

            self.card_total.data.value = f"$ {total_sum:,.2f}"
            self.card_promedio.data.value = f"$ {promedio:,.2f}"
            self.card_maximo.data.value = f"$ {maximo:,.2f}"
            self.card_mayor.data.value = mayor_cat[:15].title()
        except: pass

    def get_color_ft(self, idx: int, cat: str = ""):
        if self.nivel_actual == "DETALLE_CAJA": return obtener_color_proveedor(cat, idx)
        elif self.modo_vista == "ENTIDADES": return obtener_color(cat, modo="ENTIDADES", nivel=self.nivel_actual)
        else: return obtener_color_proveedor(cat, idx)

    def _construir_ui(self):
        self.content = ft.Column([
            ft.Row([self.titulo, self.leyenda_container], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Container(height=8), self.fila_metricas,
            ft.Container(height=8), self.fila_controles,
            ft.Container(height=4), self.hover_container, 
            ft.Divider(height=10, color=ft.colors.GREY_100),
            self.chart_container,
        ], spacing=0)

    def set_modo(self, modo: str):
        self.modo_vista = modo
        self.nivel_actual = "GENERAL"
        self.caja_seleccionada = None
        self.extraer_datos()
        self.dibujar_grafico("ALL")
        if self.page: self.update()

    def set_nivel(self, nuevo_nivel: str, caja_sel: str = None):
        self.nivel_actual = nuevo_nivel
        self.caja_seleccionada = caja_sel
        self.extraer_datos()
        self.dibujar_grafico(self.dropdown_dias.value)
        if self.page: self.update()

    def extraer_datos(self):
        try:
            dias_cortos = {0:"Lun",1:"Mar",2:"Mie",3:"Jue",4:"Vie",5:"Sab",6:"Dom"}
            dias_completos = {0:"Lunes",1:"Martes",2:"Miercoles",3:"Jueves",4:"Viernes",5:"Sabado",6:"Domingo"}

            if self.modo_vista == "GASTOS":
                self._extraer_gastos_2335(dias_cortos, dias_completos)
                return

            if not os.path.exists("local_cache/base_global.parquet"): return
            df = pl.read_parquet("local_cache/base_global.parquet").to_pandas()
            df["Fecha"] = pd.to_datetime(df["Fecha"], dayfirst=True, errors="coerce")
            df = df.dropna(subset=["Fecha"])
            df["Dia"] = df["Fecha"].dt.day
            df["Dia_Semana"] = df["Fecha"].dt.dayofweek

            if self.modo_vista == "ENTIDADES":
                self._extraer_entidades(df, dias_cortos, dias_completos)
            else:
                self._extraer_proveedores(df, dias_cortos, dias_completos)
        except: pass

    def _extraer_gastos_2335(self, dias_cortos, dias_completos):
        # Mapeo a nivel general de gastos (esta funcion no cambió)
        ruta_gastos = "local_cache/gastos_2335.xlsx"
        db_path = "local_cache/maestros.db"
        if not os.path.exists(ruta_gastos) or not os.path.exists(db_path):
            self.categorias_activas, self.datos_diarios = [], {}
            return

        mapping_numero_caja = {}
        if os.path.exists("local_cache/base_global.parquet"):
            try:
                df_global = pl.read_parquet("local_cache/base_global.parquet").to_pandas()
                df_caja = df_global[(df_global['Origen'].str.upper() == 'CAJA')].copy()
                mapeo_cajas = {}
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT codigo, recauda FROM centros_costos")
                    for r in cursor.fetchall():
                        if str(r[1]).strip(): mapeo_cajas[str(r[0]).strip()] = str(r[1]).strip().upper()
                df_caja['CCO_Clean'] = df_caja['NOMBRE_CCO'].astype(str).str.extract(r'(\d{5})', expand=False)
                df_caja['Caja_Real'] = df_caja['CCO_Clean'].map(mapeo_cajas).fillna(df_caja['NOMBRE_CCO']).str.upper()
                
                if 'Numero_Doc' in df_caja.columns:
                    for _, row in df_caja.iterrows():
                        num = str(row['Numero_Doc']).strip().replace(".0", "")
                        if num and num != "NAN":
                            mapping_numero_caja[num] = str(row['Caja_Real']).upper()
            except: pass

        df = pd.read_excel(ruta_gastos)
        df.columns = df.columns.str.strip().str.upper()
        if 'MCNFECHA' not in df.columns or 'MCNVALDEBI' not in df.columns: return
        
        df['MCNVALDEBI'] = pd.to_numeric(df['MCNVALDEBI'], errors='coerce').fillna(0)
        df_pagos = df[df['MCNVALDEBI'] > 0].copy()
        
        df_pagos['Fecha'] = pd.to_datetime(df_pagos['MCNFECHA'], errors='coerce')
        df_pagos = df_pagos.dropna(subset=['Fecha'])
        df_pagos['Dia'] = df_pagos['Fecha'].dt.day
        df_pagos['Dia_Semana'] = df_pagos['Fecha'].dt.dayofweek

        if 'MCNNUMEDOC' in df_pagos.columns:
            df_pagos['MCNNUMEDOC_str'] = df_pagos['MCNNUMEDOC'].astype(str).str.strip().str.replace(".0", "", regex=False)
            df_pagos['Categoria'] = df_pagos['MCNNUMEDOC_str'].apply(lambda x: mapping_numero_caja.get(x, "OTRAS CAJAS/BANCOS"))
        else:
            df_pagos['Categoria'] = "General"

        agrupado = df_pagos.groupby(["Dia", "Categoria"]).agg({"MCNVALDEBI": "sum", "Dia_Semana": "first"}).reset_index()
        totales_cat = agrupado.groupby("Categoria")["MCNVALDEBI"].sum().sort_values(ascending=False)
        self.categorias_activas = totales_cat.head(10).index.tolist()

        opciones = [ft.dropdown.Option(key="ALL", text="Todo el mes")]
        self.datos_diarios = {}
        for d in sorted(agrupado["Dia"].unique()):
            subset = agrupado[agrupado["Dia"] == d]
            dsn = int(subset["Dia_Semana"].iloc[0])
            valores_dia = {cat: float(subset[subset["Categoria"] == cat]["MCNVALDEBI"].sum()) if cat in subset["Categoria"].values else 0.0 for cat in self.categorias_activas}
            self.datos_diarios[d] = {"label_corta": f"{dias_cortos[dsn]} {d}", "label_larga": f"{dias_completos[dsn]} {d}", "valores": valores_dia, "total": sum(valores_dia.values())}
            opciones.append(ft.dropdown.Option(key=str(d), text=self.datos_diarios[d]["label_larga"]))

        self.dropdown_dias.options = opciones
        self._actualizar_metricas()
        self._construir_leyenda()

    def _extraer_entidades(self, df, dias_cortos, dias_completos):
        db_path = "local_cache/maestros.db"
        mapeo_cajas, dict_cuentas_2335, prov_lista = {}, {}, set()
        if os.path.exists(db_path):
            try:
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT codigo, nombre FROM proveedores")
                    for r in cursor.fetchall(): prov_lista.add(str(r[1]).strip().upper())
                    cursor.execute("SELECT codigo, nombre FROM cuentas_2335")
                    for r in cursor.fetchall(): dict_cuentas_2335[str(r[0]).strip()] = str(r[1]).strip().title()
                    cursor.execute("SELECT codigo, recauda FROM centros_costos")
                    for r in cursor.fetchall():
                        c, rec = str(r[0]).strip(), str(r[1]).strip().upper()
                        if rec: mapeo_cajas[c] = rec
            except: pass

        df_egr = df[df["Egreso"] > 0].copy()
        df_egr['CCO_Clean'] = df_egr['NOMBRE_CCO'].astype(str).str.extract(r'(\d{5})', expand=False)
        df_egr['Caja_Real'] = df_egr['CCO_Clean'].map(mapeo_cajas).fillna(df_egr['NOMBRE_CCO']).str.upper()

        if self.nivel_actual == "GENERAL": 
            df_egr["Categoria"] = df_egr["Origen"].apply(lambda x: "Caja" if str(x).strip().upper() == "CAJA" else "Bancos")
        elif self.nivel_actual == "BANCOS":
            df_egr = df_egr[df_egr["Origen"].str.strip().str.upper() != "CAJA"].copy()
            df_egr["Categoria"] = df_egr["Origen"].str.capitalize()
        elif self.nivel_actual == "CAJA":
            df_egr = df_egr[df_egr["Origen"].str.strip().str.upper() == "CAJA"].copy()
            df_egr["Categoria"] = df_egr["Caja_Real"]
            
            ruta_gastos = "local_cache/gastos_2335.xlsx"
            if os.path.exists(ruta_gastos):
                try:
                    df_g = pd.read_excel(ruta_gastos)
                    df_g.columns = df_g.columns.str.strip().str.upper()
                    if 'MCNVALDEBI' in df_g.columns and 'MCNFECHA' in df_g.columns and 'MCNNUMEDOC' in df_g.columns:
                        df_g['MCNVALDEBI'] = pd.to_numeric(df_g['MCNVALDEBI'], errors='coerce').fillna(0)
                        df_g = df_g[df_g['MCNVALDEBI'] > 0].copy()
                        df_g['Fecha'] = pd.to_datetime(df_g['MCNFECHA'], errors='coerce')
                        df_g = df_g.dropna(subset=['Fecha'])
                        df_g['Dia'] = df_g['Fecha'].dt.day
                        df_g['Dia_Semana'] = df_g['Fecha'].dt.dayofweek
                        
                        mapping_numero_caja = {}
                        if 'Numero_Doc' in df_egr.columns:
                            for _, row in df_egr.iterrows():
                                num = str(row['Numero_Doc']).strip().replace(".0", "")
                                if num and num != "NAN":
                                    mapping_numero_caja[num] = str(row['Caja_Real']).upper()
                                    
                        df_g['MCNNUMEDOC_str'] = df_g['MCNNUMEDOC'].astype(str).str.strip().str.replace(".0", "", regex=False)
                        df_g['Categoria'] = df_g['MCNNUMEDOC_str'].apply(lambda x: mapping_numero_caja.get(x, "OTRAS CAJAS"))
                        
                        df_g = df_g[['Dia', 'Dia_Semana', 'Categoria', 'MCNVALDEBI']].rename(columns={'MCNVALDEBI': 'Egreso'})
                        df_egr = pd.concat([df_egr[['Dia', 'Dia_Semana', 'Categoria', 'Egreso']], df_g], ignore_index=True)
                except: pass

        elif self.nivel_actual == "DETALLE_CAJA" and self.caja_seleccionada:
            caja_str = str(self.caja_seleccionada).upper()
            df_egr = df_egr[(df_egr["Origen"].str.strip().str.upper() == "CAJA") & (df_egr["Caja_Real"] == caja_str)].copy()
            df_egr["Categoria"] = df_egr["Tercero"].apply(lambda x: "Proveedores" if str(x).strip().upper() in prov_lista else "Otros Gastos")
            
            ruta_gastos = "local_cache/gastos_2335.xlsx"
            if os.path.exists(ruta_gastos):
                try:
                    df_g = pd.read_excel(ruta_gastos)
                    df_g.columns = df_g.columns.str.strip().str.upper()
                    if 'MCNVALDEBI' in df_g.columns and 'MCNFECHA' in df_g.columns and 'MCNNUMEDOC' in df_g.columns:
                        df_g['MCNVALDEBI'] = pd.to_numeric(df_g['MCNVALDEBI'], errors='coerce').fillna(0)
                        df_g = df_g[df_g['MCNVALDEBI'] > 0].copy()
                        
                        mapping_numero_caja = {}
                        if 'Numero_Doc' in df_egr.columns:
                            for _, row in df_egr.iterrows():
                                num = str(row['Numero_Doc']).strip().replace(".0", "")
                                if num and num != "NAN":
                                    mapping_numero_caja[num] = str(row['Caja_Real']).upper()
                                    
                        df_g['MCNNUMEDOC_str'] = df_g['MCNNUMEDOC'].astype(str).str.strip().str.replace(".0", "", regex=False)
                        df_g['Origen_Caja'] = df_g['MCNNUMEDOC_str'].apply(lambda x: mapping_numero_caja.get(x, "OTRO"))
                        
                        df_g = df_g[df_g['Origen_Caja'] == caja_str].copy()
                        if not df_g.empty:
                            df_g['Fecha'] = pd.to_datetime(df_g['MCNFECHA'], errors='coerce')
                            df_g = df_g.dropna(subset=['Fecha'])
                            df_g['Dia'] = df_g['Fecha'].dt.day
                            df_g['Dia_Semana'] = df_g['Fecha'].dt.dayofweek
                            
                            def mapear_cuenta(codigo):
                                cod_str = str(codigo).strip()
                                if cod_str.endswith(".0"): cod_str = cod_str[:-2]
                                if cod_str in dict_cuentas_2335: return dict_cuentas_2335[cod_str]
                                if len(cod_str) >= 6:
                                    raiz = cod_str[:6]
                                    for c_bd, n_bd in dict_cuentas_2335.items():
                                        if str(c_bd).startswith(raiz): return n_bd
                                return "Gastos Operacionales"

                            df_g['Categoria'] = df_g['MCNCUENTA'].apply(mapear_cuenta)
                            df_g = df_g[['Dia', 'Dia_Semana', 'Categoria', 'MCNVALDEBI']].rename(columns={'MCNVALDEBI': 'Egreso'})
                            df_egr = pd.concat([df_egr[['Dia', 'Dia_Semana', 'Categoria', 'Egreso']], df_g], ignore_index=True)
                except: pass

        if df_egr.empty:
            self.categorias_activas, self.datos_diarios = [], {}
            return

        agrupado = df_egr.groupby(["Dia", "Categoria"]).agg({"Egreso": "sum", "Dia_Semana": "first"}).reset_index()
        totales_cat = agrupado.groupby("Categoria")["Egreso"].sum().sort_values(ascending=False)
        self.categorias_activas = totales_cat.head(10).index.tolist()

        opciones = [ft.dropdown.Option(key="ALL", text="Todo el mes")]
        self.datos_diarios = {}
        for d in sorted(agrupado["Dia"].unique()):
            subset = agrupado[agrupado["Dia"] == d]
            dsn = int(subset["Dia_Semana"].iloc[0])
            valores_dia = {cat: float(subset[subset["Categoria"] == cat]["Egreso"].sum()) if cat in subset["Categoria"].values else 0.0 for cat in self.categorias_activas}
            self.datos_diarios[d] = {"label_corta": f"{dias_cortos[dsn]} {d}", "label_larga": f"{dias_completos[dsn]} {d}", "valores": valores_dia, "total": sum(valores_dia.values())}
            opciones.append(ft.dropdown.Option(key=str(d), text=self.datos_diarios[d]["label_larga"]))

        self.dropdown_dias.options = opciones
        self._actualizar_metricas()
        self._construir_leyenda()

    def _extraer_proveedores(self, df, dias_cortos, dias_completos):
        try:
            if self.nivel_actual == "GENERAL":
                df_prov = pl.read_parquet("local_cache/base_resumen.parquet").to_pandas()
                provedores_caja, provedores_banco = set(), set()
                valores_caja, valores_banco = {}, {}
                
                for idx, row in df_prov.iterrows():
                    if pd.notna(row['Valor']) and row['Valor'] > 0:
                        conc = str(row['Concepto'])
                        if 'Prov Caja:' in conc: provedores_caja.add(conc.replace('   > Prov Caja: ', '').strip().upper())
                        elif 'Prov Banco:' in conc: provedores_banco.add(conc.replace('   > Prov Banco: ', '').strip().upper())
                
                if provedores_caja or provedores_banco:
                    df_egr = df[(df["Egreso"] > 0) & (~df["Categoria_Flujo"].isin(["Traslado_Salida", "Traslado_Entrada"]))].copy()
                    df_egr["EsProvCaja"] = df_egr["Tercero"].apply(lambda x: str(x).strip().upper() in provedores_caja if pd.notna(x) else False)
                    df_egr["EsProvBanco"] = df_egr["Tercero"].apply(lambda x: str(x).strip().upper() in provedores_banco if pd.notna(x) else False)
                    
                    valores_caja = df_egr[df_egr["EsProvCaja"]].groupby("Dia")["Egreso"].sum().to_dict()
                    valores_banco = df_egr[df_egr["EsProvBanco"]].groupby("Dia")["Egreso"].sum().to_dict()
                
                self.categorias_activas = []
                if provedores_caja: self.categorias_activas.append("Proveedores por Caja")
                if provedores_banco: self.categorias_activas.append("Proveedores por Banco")
                
                self.datos_diarios = {}
                dias_presentes = set(valores_caja.keys()) | set(valores_banco.keys())
                
                opciones = [ft.dropdown.Option(key="ALL", text="Todo el mes")]
                for d in sorted(dias_presentes):
                    dia_semana = int(df[df["Dia"] == d]["Dia_Semana"].iloc[0]) if d in df["Dia"].values else 0
                    val_caja = valores_caja.get(d, 0.0)
                    val_banco = valores_banco.get(d, 0.0)
                    valores = {}
                    if "Proveedores por Caja" in self.categorias_activas: valores["Proveedores por Caja"] = val_caja
                    if "Proveedores por Banco" in self.categorias_activas: valores["Proveedores por Banco"] = val_banco
                    
                    self.datos_diarios[d] = {"label_corta": f"{dias_cortos.get(dia_semana, '?')} {d}", "label_larga": f"{dias_completos.get(dia_semana, '?')} {d}", "valores": valores, "total": val_caja + val_banco}
                    opciones.append(ft.dropdown.Option(key=str(d), text=self.datos_diarios[d]["label_larga"]))
                
                self.dropdown_dias.options = opciones
                self._actualizar_metricas()
                self._construir_leyenda()
                return
            
            df_egr = df[(df["Egreso"] > 0) & (~df["Categoria_Flujo"].isin(["Traslado_Salida", "Traslado_Entrada"]))].copy()
            df_prov = pl.read_parquet("local_cache/base_resumen.parquet").to_pandas()
            provedores_caja, provedores_banco = set(), set()
            for idx, row in df_prov.iterrows():
                if pd.notna(row['Valor']) and row['Valor'] > 0:
                    conc = str(row['Concepto'])
                    if 'Prov Caja:' in conc: provedores_caja.add(conc.replace('   > Prov Caja: ', '').strip().upper())
                    elif 'Prov Banco:' in conc: provedores_banco.add(conc.replace('   > Prov Banco: ', '').strip().upper())
            
            proveedores_filtrar = provedores_caja if self.nivel_actual == "CAJA" else provedores_banco
            
            if not proveedores_filtrar:
                self.categorias_activas, self.datos_diarios = [], {}
                return
            
            df_egr["EsProveedorCanal"] = df_egr["Tercero"].apply(lambda x: str(x).strip().upper() in proveedores_filtrar if pd.notna(x) else False)
            df_prov_dia = df_egr[df_egr["EsProveedorCanal"]].copy()
            df_prov_dia["Proveedor"] = df_prov_dia["Tercero"].str.upper().str.strip()
            
            agrupado = df_prov_dia.groupby(["Dia", "Proveedor"]).agg({"Egreso": "sum", "Dia_Semana": "first"}).reset_index()
            totales_prov = agrupado.groupby("Proveedor")["Egreso"].sum().sort_values(ascending=False)
            self.categorias_activas = totales_prov.head(8).index.tolist()
            
            opciones = [ft.dropdown.Option(key="ALL", text="Todo el mes")]
            self.datos_diarios = {}
            for d in sorted(agrupado["Dia"].unique()):
                subset = agrupado[agrupado["Dia"] == d]
                dsn = int(subset["Dia_Semana"].iloc[0])
                valores_dia = {cat: float(subset[subset["Proveedor"] == cat]["Egreso"].sum()) if cat in subset["Proveedor"].values else 0.0 for cat in self.categorias_activas}
                self.datos_diarios[d] = {"label_corta": f"{dias_cortos[dsn]} {d}", "label_larga": f"{dias_completos[dsn]} {d}", "valores": valores_dia, "total": sum(valores_dia.values())}
                opciones.append(ft.dropdown.Option(key=str(d), text=self.datos_diarios[d]["label_larga"]))
            
            self.dropdown_dias.options = opciones
            self._actualizar_metricas()
            self._construir_leyenda()
        except: pass

    def _construir_leyenda(self):
        self.btn_entidades.style = ft.ButtonStyle(bgcolor=ft.colors.RED_50 if self.modo_vista == "ENTIDADES" else ft.colors.TRANSPARENT, color=ft.colors.RED_900 if self.modo_vista == "ENTIDADES" else ft.colors.GREY_500)
        self.btn_proveedores.style = ft.ButtonStyle(bgcolor=ft.colors.RED_50 if self.modo_vista == "PROVEEDORES" else ft.colors.TRANSPARENT, color=ft.colors.RED_900 if self.modo_vista == "PROVEEDORES" else ft.colors.GREY_500)
        self.btn_gastos.style = ft.ButtonStyle(bgcolor=ft.colors.RED_50 if self.modo_vista == "GASTOS" else ft.colors.TRANSPARENT, color=ft.colors.RED_900 if self.modo_vista == "GASTOS" else ft.colors.GREY_500)
        
        self.leyenda_row.controls = []
        for i, cat in enumerate(self.categorias_activas):
            nombre = cat.title()[:20] if self.modo_vista == "ENTIDADES" else cat[:20]
            self.leyenda_row.controls.append(
                ft.Row([
                    ft.Container(width=8, height=8, border_radius=4, bgcolor=self.get_color_ft(i, cat)),
                    ft.Text(nombre, size=10, weight=ft.FontWeight.W_500, color=ft.colors.GREY_700)
                ], spacing=4, tight=True)
            )

    def on_hover_chart(self, e):
        if self.dropdown_dias.value != "ALL": return
        try:
            dia_encontrado = None
            if hasattr(e, "data") and e.data:
                data = json.loads(e.data)
                spots = data.get("spots", [])
                if spots:
                    spot_idx = spots[0].get("spot_index")
                    if spot_idx is not None:
                        dias_ord = sorted(self.datos_diarios.keys())
                        if spot_idx < len(dias_ord):
                            dia_encontrado = dias_ord[spot_idx]

            if dia_encontrado is not None:
                datos = self.datos_diarios.get(dia_encontrado)
                if datos:
                    controles = []
                    cats_ord = sorted(self.categorias_activas, key=lambda c: datos["valores"].get(c, 0), reverse=True)
                    for cat in cats_ord:
                        val = datos["valores"].get(cat, 0)
                        if val > 0:
                            idx = self.categorias_activas.index(cat)
                            nombre = cat.title()[:15] if self.modo_vista == "ENTIDADES" else cat[:15]
                            controles.append(
                                ft.Row([
                                    ft.Container(width=7, height=7, border_radius=4, bgcolor=self.get_color_ft(idx, cat)),
                                    ft.Text(f"{nombre}: $ {val:,.2f}", size=11, color=self.get_color_ft(idx, cat), weight=ft.FontWeight.W_600)
                                ], spacing=4, tight=True)
                            )
                    self.panel_hover.controls = controles
                    self.txt_total_hover.value = f"Resumen {datos['label_corta']} (Total: $ {datos['total']:,.2f})"
            else:
                self.panel_hover.controls = []
                self.txt_total_hover.value = "Pasa el mouse sobre el grafico para ver detalles"
            if self.page: self.update()
        except: pass

    def dibujar_grafico(self, seleccion: str):
        if not self.datos_diarios:
            self.chart_container.content = ft.Text("No hay datos para esta vista.", color=ft.colors.GREY_500)
            return
        
        todos_valores = [v for d in self.datos_diarios.values() for v in d["valores"].values() if v > 0]
        max_val = max(todos_valores) if todos_valores else 0
        max_m = max_val / 1_000_000
        techo_m = math.ceil(max_m / 10) * 10 if max_m > 0 else 50
        paso = techo_m / 4
        labels_y = [ft.ChartAxisLabel(value=i*paso, label=ft.Text(f"{int(i*paso)}M", size=10, color=ft.colors.GREY_500)) for i in range(5)]

        if seleccion == "ALL":
            data_series = []
            for i, cat in enumerate(self.categorias_activas):
                puntos = [ft.LineChartDataPoint(x=d, y=round(self.datos_diarios[d]["valores"][cat]/1_000_000, 2), tooltip=" ") for d in sorted(self.datos_diarios.keys())]
                data_series.append(ft.LineChartData(data_points=puntos, stroke_width=1.5, color=self.get_color_ft(i, cat), curved=True, stroke_cap_round=True, point=ft.ChartCirclePoint(radius=1.5)))

            labels_x = [ft.ChartAxisLabel(value=d, label=ft.Container(content=ft.Column([
                ft.Text(self.datos_diarios[d]["label_corta"].split()[0].upper(), size=8, color=ft.colors.RED_700, weight=ft.FontWeight.W_600),
                ft.Text(str(d), size=10, color=ft.colors.GREY_500)
            ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER))) for d in sorted(self.datos_diarios.keys())]

            chart = ft.LineChart(
                data_series=data_series, bottom_axis=ft.ChartAxis(labels=labels_x, labels_size=26),
                left_axis=ft.ChartAxis(labels=labels_y, labels_size=44), min_y=0, max_y=techo_m * 1.05,
                border=ft.border.all(1, ft.colors.TRANSPARENT), tooltip_bgcolor=ft.colors.TRANSPARENT,
                on_chart_event=self.on_hover_chart, expand=True
            )
            self.chart_container.content = ft.Row([ft.Container(content=chart, width=2500, height=400)], scroll=ft.ScrollMode.ALWAYS)
        else:
            dia = int(seleccion)
            datos = self.datos_diarios[dia]
            cats_ord = [c for c in self.categorias_activas if datos["valores"].get(c, 0) > 0]
            bar_groups = [ft.BarChartGroup(x=pos, bar_rods=[ft.BarChartRod(
                from_y=0, to_y=round(datos["valores"][cat]/1_000_000, 2), width=40, color=self.get_color_ft(self.categorias_activas.index(cat), cat),
                border_radius=5, tooltip=f"$ {datos['valores'][cat]:,.2f}"
            )]) for pos, cat in enumerate(cats_ord)]
            
            labels_bottom = [ft.ChartAxisLabel(value=pos, label=ft.Text(cat[:10], size=10, weight=ft.FontWeight.W_600, color=ft.colors.RED_900)) for pos, cat in enumerate(cats_ord)]
            
            chart = ft.BarChart(
                bar_groups=bar_groups, bottom_axis=ft.ChartAxis(labels=labels_bottom, labels_size=26),
                left_axis=ft.ChartAxis(labels=labels_y, labels_size=44), max_y=techo_m * 1.1,
                border=ft.border.all(1, ft.colors.TRANSPARENT), tooltip_bgcolor=ft.colors.WHITE, expand=True
            )
            self.chart_container.content = chart
            
    def mostrar_detalle_dia(self, e):
        self.dibujar_grafico(self.dropdown_dias.value)
        if self.page: self.update()