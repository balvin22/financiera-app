# src/ui/components/grafico_egresos.py
import flet as ft
import polars as pl
import pandas as pd
import json
import sqlite3
import os
from src.core.mapeos import (
    COLORES_ENTIDADES, COLORES_BANCOS, COLORES_CAJAS, COLORES_PROVEEDORES,
    obtener_color, obtener_color_proveedor
)

class GraficoEgresos(ft.Container):
    def __init__(self, on_nivel_change=None, on_modo_change=None):
        super().__init__()
        self.on_nivel_change = on_nivel_change
        self.on_modo_change = on_modo_change
        self.expand = True
        self.height = 350
        self.bgcolor = ft.colors.WHITE
        self.border_radius = 12
        self.padding = 20
        self.border = ft.border.all(1, ft.colors.GREY_200)

        self.modo_vista = "ENTIDADES" 
        self.nivel_dona = "GENERAL"
        self.caja_seleccionada = None
        
        self.datos_gen_entidades, self.datos_ban_entidades, self.datos_caj_entidades = {}, {}, {}
        self.datos_gen_proveedores, self.datos_ban_proveedores, self.datos_caj_proveedores = {}, {}, {}
        self.datos_gen_gastos, self.datos_caj_gastos = {}, {}
        
        self.datos_caj_categorias = {} 
        self.datos_caj_prov_detalle = {} 
        self.datos_caj_gas_detalle = {} 
        
        self.datos_hover = [] 
        
        self.dona_grafico = ft.PieChart(sections=[], sections_space=2, center_space_radius=35, on_chart_event=self.on_hover_dona)
        self.texto_hover = ft.Text("Apunta al grafico para detalles", size=11, color=ft.colors.GREY_400, text_align=ft.TextAlign.CENTER)
        self.leyenda_contenedor = ft.Column(scroll=ft.ScrollMode.ALWAYS, spacing=5)
        self.titulo_grafico = ft.Text("Salidas Operacionales", weight=ft.FontWeight.BOLD, size=16, color=ft.colors.RED_900)
        
        self.btn_entidades = ft.TextButton("Entidades", on_click=lambda e: self.cambiar_modo("ENTIDADES"))
        self.btn_proveedores = ft.TextButton("Proveedores", on_click=lambda e: self.cambiar_modo("PROVEEDORES"))
        self.btn_gastos = ft.TextButton("Gastos (2335)", on_click=lambda e: self.cambiar_modo("GASTOS"))
        
        self.contenedor_tabs = ft.Row([self.btn_entidades, self.btn_proveedores, self.btn_gastos], spacing=0)
        self.boton_volver = ft.ElevatedButton("← Volver", on_click=self.volver_dona, visible=False, style=ft.ButtonStyle(color=ft.colors.RED_700, bgcolor=ft.colors.RED_50, padding=10))
        
        self.tabla_detalle = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Concepto", size=12, weight=ft.FontWeight.BOLD, color=ft.colors.RED_900)),
                ft.DataColumn(ft.Text("%", size=12, weight=ft.FontWeight.BOLD, color=ft.colors.RED_900)),
                ft.DataColumn(ft.Text("Valor", size=12, weight=ft.FontWeight.BOLD, color=ft.colors.RED_900))
            ],
            rows=[], column_spacing=15, heading_row_color=ft.colors.RED_50
        )

        self.extraer_datos_grafico()
        self.construir_ui()
        self.actualizar_dona_ui()

    def construir_ui(self):
        self.content = ft.Column([
            ft.Row([ft.Row([self.titulo_grafico, ft.Container(width=15), self.contenedor_tabs]), self.boton_volver], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(height=10, color=ft.colors.GREY_200),
            ft.Row([
                ft.Container(content=ft.Column([ft.Container(content=self.dona_grafico, width=240, height=240), self.texto_hover], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10), width=240),
                ft.Container(content=self.leyenda_contenedor, width=220, height=260),
                ft.Container(content=ft.Column([self.tabla_detalle], scroll=ft.ScrollMode.AUTO), expand=True, height=260, border=ft.border.only(left=ft.border.BorderSide(1, ft.colors.GREY_200)), padding=ft.padding.only(left=20))
            ], vertical_alignment=ft.CrossAxisAlignment.START)
        ])

    def extraer_datos_grafico(self):
        db_path = "local_cache/maestros.db"
        mapeo_cajas, dict_cuentas_2335, proveedores_lista = {}, {}, set()

        if os.path.exists(db_path):
            try:
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT codigo, nombre FROM proveedores")
                    for r in cursor.fetchall(): proveedores_lista.add(str(r[1]).strip().upper())
                    cursor.execute("SELECT codigo, nombre FROM cuentas_2335")
                    for r in cursor.fetchall(): dict_cuentas_2335[str(r[0]).strip()] = str(r[1]).strip().title()
                    cursor.execute("SELECT codigo, recauda FROM centros_costos")
                    for r in cursor.fetchall():
                        c, rec = str(r[0]).strip(), str(r[1]).strip().upper()
                        if rec: mapeo_cajas[c] = rec
            except: pass

        try:
            df_res = pl.read_parquet("local_cache/base_resumen.parquet").to_pandas()
            try: self.datos_gen_entidades = {"Bancos": df_res.loc[df_res['Concepto'] == 'Total Salidas x Bancos', 'Valor'].values[0], "CAJA": df_res.loc[df_res['Concepto'] == 'Total Salidas x Caja', 'Valor'].values[0]}
            except: pass
            
            try:
                idx_start = df_res.index[df_res['Concepto'] == 'DETALLE DE SALIDAS BANCARIAS'][0]
                idx_end = df_res.index[df_res['Concepto'] == 'Total Salidas x Bancos'][0]
                for _, row in df_res.iloc[idx_start+1 : idx_end].iterrows():
                    if pd.notna(row['Valor']) and row['Valor'] > 0: self.datos_ban_entidades[str(row['Concepto']).replace("Salidas ", "").upper()] = row['Valor']
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
                            self.datos_caj_entidades[key_clean] = val
                
                if "CAJA POPAYAN PPAL" in self.datos_caj_entidades and ajuste_cruce != 0:
                    self.datos_caj_entidades["CAJA POPAYAN PPAL"] -= abs(ajuste_cruce)
                    if self.datos_caj_entidades["CAJA POPAYAN PPAL"] < 0: self.datos_caj_entidades["CAJA POPAYAN PPAL"] = 0.0
            except: pass
            
            try: self.datos_gen_proveedores = {"Bancos": df_res.loc[df_res['Concepto'] == 'Pagos por Bancos', 'Valor'].values[0], "CAJA": df_res.loc[df_res['Concepto'] == 'Pagos por Caja', 'Valor'].values[0]}
            except: pass
            
            try:
                idx_start = df_res.index[df_res['Concepto'] == 'DESGLOSE DE PROVEEDORES (BANCOS)'][0]
                idx_end = df_res.index[df_res['Concepto'] == 'SALIDAS POR GASTOS OPERACIONALES'][0] if 'SALIDAS POR GASTOS OPERACIONALES' in df_res['Concepto'].values else len(df_res)
                for _, row in df_res.iloc[idx_start+1 : idx_end].iterrows():
                    if pd.notna(row['Valor']) and row['Valor'] > 0 and 'Prov Banco:' in str(row['Concepto']): self.datos_ban_proveedores[str(row['Concepto']).replace("   > Prov Banco: ", "").upper()] = row['Valor']
            except: pass
            
            try:
                idx_start = df_res.index[df_res['Concepto'] == 'DESGLOSE DE PROVEEDORES (CAJA)'][0]
                idx_end = df_res.index[df_res['Concepto'] == 'DESGLOSE DE PROVEEDORES (BANCOS)'][0]
                for _, row in df_res.iloc[idx_start+1 : idx_end].iterrows():
                    if pd.notna(row['Valor']) and row['Valor'] > 0 and 'Prov Caja:' in str(row['Concepto']): self.datos_caj_proveedores[str(row['Concepto']).replace("   > Prov Caja: ", "").upper()] = row['Valor']
            except: pass
        except: pass

        self.datos_caj_categorias = {}
        self.datos_caj_prov_detalle = {}
        self.datos_caj_gas_detalle = {}
        mapping_numero_caja = {}  # <--- DICCIONARIO CRUCE NUMERO A CAJA
        
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
                
                # --- TU IDEA APLICADA AQUÍ: CREAR EL MAPEO EXACTO ---
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
                    
                    if c not in self.datos_caj_categorias: self.datos_caj_categorias[c] = {"Proveedores": 0.0, "Gastos Operacionales": 0.0}
                    if c not in self.datos_caj_prov_detalle: self.datos_caj_prov_detalle[c] = {}
                        
                    self.datos_caj_categorias[c]["Proveedores"] += v
                    self.datos_caj_prov_detalle[c][prov_name] = self.datos_caj_prov_detalle[c].get(prov_name, 0.0) + v
            except: pass

        ruta_gastos = "local_cache/gastos_2335.xlsx"
        if os.path.exists(ruta_gastos):
            try:
                df_gastos = pd.read_excel(ruta_gastos)
                df_gastos.columns = df_gastos.columns.str.strip().str.upper()
                if 'MCNVALDEBI' in df_gastos.columns and 'MCNNUMEDOC' in df_gastos.columns:
                    df_gastos['MCNVALDEBI'] = pd.to_numeric(df_gastos['MCNVALDEBI'], errors='coerce').fillna(0)
                    df_pagos = df_gastos[df_gastos['MCNVALDEBI'] > 0].copy()
                    
                    # --- CRUCE PERFECTO NUMERO VS MCNNUMEDOC ---
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
                    
                    agrupado_caja = df_pagos.groupby('Origen_Caja')['MCNVALDEBI'].sum()
                    for cat, valor in agrupado_caja.items():
                        if valor > 0: self.datos_caj_gastos[cat] = float(valor)
                    self.datos_gen_gastos = {"Gastos Operacionales (2335)": df_pagos['MCNVALDEBI'].sum()}
                    
                    df_pagos_caja = df_pagos[df_pagos['Origen_Caja'] != "OTRO"].copy()
                    for _, row in df_pagos_caja.iterrows():
                        c = str(row['Origen_Caja'])
                        v = float(row['MCNVALDEBI'])
                        cat = str(row['Categoria'])
                        
                        if c not in self.datos_caj_categorias: self.datos_caj_categorias[c] = {"Proveedores": 0.0, "Gastos Operacionales": 0.0}
                        if c not in self.datos_caj_gas_detalle: self.datos_caj_gas_detalle[c] = {}
                            
                        self.datos_caj_categorias[c]["Gastos Operacionales"] += v
                        self.datos_caj_gas_detalle[c][cat] = self.datos_caj_gas_detalle[c].get(cat, 0.0) + v
            except: pass
            
        for c, v_total in self.datos_caj_entidades.items():
            if c not in self.datos_caj_categorias:
                self.datos_caj_categorias[c] = {"Proveedores": 0.0, "Gastos Operacionales": 0.0, "Otros Egresos": v_total}
            else:
                sum_identificados = self.datos_caj_categorias[c].get("Proveedores", 0.0) + self.datos_caj_categorias[c].get("Gastos Operacionales", 0.0)
                diff = v_total - sum_identificados
                
                if diff > 1000: 
                    self.datos_caj_categorias[c]["Otros Egresos"] = diff
                elif diff < -1000:
                    exceso = abs(diff)
                    if self.datos_caj_categorias[c].get("Gastos Operacionales", 0.0) >= exceso:
                        self.datos_caj_categorias[c]["Gastos Operacionales"] -= exceso
                    elif self.datos_caj_categorias[c].get("Proveedores", 0.0) >= exceso:
                        self.datos_caj_categorias[c]["Proveedores"] -= exceso

    def cambiar_modo(self, modo: str):
        self.modo_vista = modo
        self.nivel_dona = "GENERAL"
        self.caja_seleccionada = None
        self.actualizar_dona_ui()
        if self.on_modo_change: self.on_modo_change(modo)

    def volver_dona(self, e):
        if self.nivel_dona in ["BANCOS", "CAJA"] or (self.modo_vista == "GASTOS" and self.nivel_dona != "GENERAL"):
            self.nivel_dona = "GENERAL"
            self.caja_seleccionada = None
        elif self.nivel_dona == "CATEGORIAS_CAJA":
            self.nivel_dona = "CAJA"
            self.caja_seleccionada = None
        elif self.nivel_dona in ["PROVEEDORES_CAJA", "GASTOS_CAJA"]:
            self.nivel_dona = "CATEGORIAS_CAJA"
            
        self.actualizar_dona_ui()

    def actualizar_dona_ui(self):
        datos = {}
        self.btn_entidades.style = ft.ButtonStyle(bgcolor=ft.colors.RED_50 if self.modo_vista == "ENTIDADES" else ft.colors.TRANSPARENT, color=ft.colors.RED_900 if self.modo_vista == "ENTIDADES" else ft.colors.GREY_500)
        self.btn_proveedores.style = ft.ButtonStyle(bgcolor=ft.colors.RED_50 if self.modo_vista == "PROVEEDORES" else ft.colors.TRANSPARENT, color=ft.colors.RED_900 if self.modo_vista == "PROVEEDORES" else ft.colors.GREY_500)
        self.btn_gastos.style = ft.ButtonStyle(bgcolor=ft.colors.RED_50 if self.modo_vista == "GASTOS" else ft.colors.TRANSPARENT, color=ft.colors.RED_900 if self.modo_vista == "GASTOS" else ft.colors.GREY_500)

        es_clicable = False

        if self.modo_vista == "ENTIDADES":
            if self.nivel_dona == "GENERAL":
                datos, self.titulo_grafico.value, self.boton_volver.visible, es_clicable = self.datos_gen_entidades, "Salidas (Bancos vs Caja)", False, True
            elif self.nivel_dona == "BANCOS":
                datos, self.titulo_grafico.value, self.boton_volver.visible = self.datos_ban_entidades, "Detalle Salidas Bancarias", True
            elif self.nivel_dona == "CAJA":
                datos, self.titulo_grafico.value, self.boton_volver.visible, es_clicable = self.datos_caj_entidades, "Detalle Salidas por Cajas", True, True
            elif self.nivel_dona == "CATEGORIAS_CAJA":
                datos = self.datos_caj_categorias.get(self.caja_seleccionada, {})
                self.titulo_grafico.value = f"Egresos {self.caja_seleccionada.title()}"
                self.boton_volver.visible, es_clicable = True, True
            elif self.nivel_dona == "PROVEEDORES_CAJA":
                datos = self.datos_caj_prov_detalle.get(self.caja_seleccionada, {})
                self.titulo_grafico.value = f"Proveedores {self.caja_seleccionada.title()}"
                self.boton_volver.visible = True
            elif self.nivel_dona == "GASTOS_CAJA":
                datos = self.datos_caj_gas_detalle.get(self.caja_seleccionada, {})
                self.titulo_grafico.value = f"Gastos {self.caja_seleccionada.title()}"
                self.boton_volver.visible = True

        elif self.modo_vista == "PROVEEDORES":
            if self.nivel_dona == "GENERAL":
                datos, self.titulo_grafico.value, self.boton_volver.visible, es_clicable = self.datos_gen_proveedores, "Pago Proveedores (Canal)", False, True
            elif self.nivel_dona == "BANCOS":
                datos, self.titulo_grafico.value, self.boton_volver.visible = self.datos_ban_proveedores, "Proveedores por Banco", True
            elif self.nivel_dona == "CAJA":
                datos, self.titulo_grafico.value, self.boton_volver.visible = self.datos_caj_proveedores, "Proveedores por Caja", True

        elif self.modo_vista == "GASTOS":
            if self.nivel_dona == "GENERAL":
                datos, self.titulo_grafico.value, self.boton_volver.visible, es_clicable = self.datos_gen_gastos, "Total Gastos 2335", False, True
            elif self.nivel_dona == "GASTOS OPERACIONALES (2335)":
                datos, self.titulo_grafico.value, self.boton_volver.visible = self.datos_caj_gastos, "Egresos 2335 por Caja", True

        datos = {k: v for k, v in datos.items() if v > 0}
        datos = dict(sorted(datos.items(), key=lambda x: x[1], reverse=True))
        
        secciones, leyenda_items, filas_tabla = [], [], []
        self.datos_hover = [] 
        total = sum(datos.values()) if sum(datos.values()) > 0 else 1
        
        for i, (label, valor) in enumerate(datos.items()):
            if self.modo_vista == "ENTIDADES":
                if self.nivel_dona in ["CATEGORIAS_CAJA", "PROVEEDORES_CAJA", "GASTOS_CAJA"]: color = obtener_color_proveedor(label, i)
                else: color = obtener_color(label, modo="ENTIDADES", nivel=self.nivel_dona)
            else: color = obtener_color_proveedor(label, i)
            
            pct = (valor / total) * 100
            secciones.append(ft.PieChartSection(value=valor, color=color, radius=55, title=f"{pct:.0f}%" if pct >= 4 else "", title_style=ft.TextStyle(size=11, color=ft.colors.WHITE, weight=ft.FontWeight.BOLD)))
            self.datos_hover.append({"label": label.title(), "valor": valor, "pct": pct, "color": color}) 
            
            def crear_evento(cat_label):
                def on_click(e):
                    if self.nivel_dona == "GENERAL": self.nivel_dona = cat_label.upper()
                    elif self.nivel_dona == "CAJA":
                        self.nivel_dona = "CATEGORIAS_CAJA"
                        self.caja_seleccionada = cat_label.upper()
                    elif self.nivel_dona == "CATEGORIAS_CAJA":
                        if cat_label.upper() == "PROVEEDORES": self.nivel_dona = "PROVEEDORES_CAJA"
                        elif cat_label.upper() == "GASTOS OPERACIONALES": self.nivel_dona = "GASTOS_CAJA"
                    self.actualizar_dona_ui()
                return on_click
            
            nombre_mostrar = label.title()
            leyenda_items.append(
                ft.Container(
                    content=ft.Row([
                        ft.Container(width=10, height=10, border_radius=5, bgcolor=color),
                        ft.Column([
                            ft.Text(nombre_mostrar + (" (Clic aquí)" if es_clicable and label.upper() not in ["OTROS EGRESOS", "BANCOS"] else ""), size=11, weight=ft.FontWeight.BOLD, color=ft.colors.RED_900),
                            ft.Text(f"$ {valor:,.2f}", size=11, color=ft.colors.GREY_600)
                        ], spacing=1, expand=True) 
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    on_click=crear_evento(label) if es_clicable else None,
                    padding=5, border_radius=5 
                )
            )

            filas_tabla.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(nombre_mostrar[:25] + "..." if len(nombre_mostrar)>25 else nombre_mostrar, size=11, color=ft.colors.RED_900)), 
                ft.DataCell(ft.Text(f"{pct:.1f}%", size=11, color=ft.colors.GREY_700)),
                ft.DataCell(ft.Text(f"$ {valor:,.2f}", size=11, color=ft.colors.RED_700, weight=ft.FontWeight.BOLD)),
            ]))
            
        filas_tabla.append(ft.DataRow(cells=[
            ft.DataCell(ft.Text("TOTAL", size=11, weight=ft.FontWeight.W_900, color=ft.colors.RED_900)),
            ft.DataCell(ft.Text("100%", size=11, weight=ft.FontWeight.W_900, color=ft.colors.RED_900)),
            ft.DataCell(ft.Text(f"$ {total:,.2f}", size=11, weight=ft.FontWeight.W_900, color=ft.colors.RED_900)),
        ]))
            
        self.dona_grafico.sections = secciones
        self.leyenda_contenedor.controls = leyenda_items
        self.tabla_detalle.rows = filas_tabla
        
        if self.on_nivel_change:
            estado_tendencia = "DETALLE_CAJA" if self.nivel_dona in ["CATEGORIAS_CAJA", "PROVEEDORES_CAJA", "GASTOS_CAJA"] else self.nivel_dona
            self.on_nivel_change(estado_tendencia, self.caja_seleccionada)
            
        self.update_safe()

    def on_hover_dona(self, e):
        try:
            idx = getattr(e, 'section_index', -1)
            if idx == -1 and hasattr(e, 'data') and e.data:
                try: idx = json.loads(e.data).get("section_index", -1)
                except: pass
            
            for i, section in enumerate(self.dona_grafico.sections):
                if i == idx:
                    section.radius = 63 
                    data = self.datos_hover[i]
                    self.texto_hover.value = f"{data['label']}\n{data['pct']:.1f}%  |  $ {data['valor']:,.2f}"
                    self.texto_hover.color = data['color'] 
                    self.texto_hover.weight = ft.FontWeight.W_900
                else: section.radius = 55 
            
            if idx == -1:
                self.texto_hover.value = "Apunta al grafico para detalles"
                self.texto_hover.color = ft.colors.GREY_400
                self.texto_hover.weight = ft.FontWeight.NORMAL
            self.update_safe()
        except: pass 

    def update_safe(self):
        if self.page and getattr(self, 'uid', None): self.update()