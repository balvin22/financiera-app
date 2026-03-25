# ui/components/grafico_ingresos.py
import flet as ft
import polars as pl
import pandas as pd
import json
from src.core.mapeos import obtener_color_ingresos

class GraficoIngresos(ft.Container):
    # --- NUEVO: Recibimos una función para avisar cuando cambie el nivel ---
    def __init__(self, on_nivel_change=None):
        super().__init__()
        self.on_nivel_change = on_nivel_change 
        
        self.expand = True
        self.height = 350
        self.bgcolor = ft.colors.WHITE
        self.border_radius = 12
        self.padding = 20
        self.border = ft.border.all(1, ft.colors.GREY_200)

        self.nivel_dona = "GENERAL"
        self.datos_general = {}
        self.datos_bancos = {}
        self.datos_caja = {}
        self.datos_hover = [] 
        
        self.dona_grafico = ft.PieChart(
            sections=[], 
            sections_space=2, 
            center_space_radius=35,
            on_chart_event=self.on_hover_dona 
        )
        
        self.texto_hover = ft.Text("Apunta al gráfico para detalles", size=11, color=ft.colors.GREY_400, text_align=ft.TextAlign.CENTER)
        self.leyenda_contenedor = ft.Column(scroll=ft.ScrollMode.ALWAYS, spacing=5)
        self.titulo_grafico = ft.Text("Distribución de Ingresos", weight=ft.FontWeight.BOLD, size=16, color=ft.colors.BLUE_900)
        self.boton_volver = ft.ElevatedButton("← Volver", on_click=self.volver_dona, visible=False, style=ft.ButtonStyle(color=ft.colors.BLUE_700, bgcolor=ft.colors.BLUE_50, padding=10))

        self.tabla_detalle = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Concepto", size=12, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_900)),
                ft.DataColumn(ft.Text("%", size=12, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_900)),
                ft.DataColumn(ft.Text("Valor", size=12, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_900))
            ],
            rows=[],
            column_spacing=15,
            heading_row_color=ft.colors.BLUE_50
        )

        self.extraer_datos_grafico()
        self.construir_ui()
        self.actualizar_dona_ui()

    def construir_ui(self):
        self.content = ft.Column([
            ft.Row([self.titulo_grafico, self.boton_volver], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(height=10, color=ft.colors.GREY_200),
            ft.Row([
                ft.Container(
                    content=ft.Column([
                        ft.Container(content=self.dona_grafico, width=240, height=240),
                        self.texto_hover
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                    width=240
                ),
                ft.Container(content=self.leyenda_contenedor, width=220, height=260),
                ft.Container(
                    content=ft.Column([self.tabla_detalle], scroll=ft.ScrollMode.AUTO),
                    expand=True,
                    height=260,
                    border=ft.border.only(left=ft.border.BorderSide(1, ft.colors.GREY_200)), 
                    padding=ft.padding.only(left=20)
                )
            ], vertical_alignment=ft.CrossAxisAlignment.START) 
        ])

    def extraer_datos_grafico(self):
        try:
            df_res = pl.read_parquet("local_cache/base_resumen.parquet").to_pandas()
            try:
                self.datos_general = {
                    "Bancos": df_res.loc[df_res['Concepto'] == 'Total Ingresos x Bancos', 'Valor'].values[0],
                    "Caja": df_res.loc[df_res['Concepto'] == 'Total Ingresos x Caja', 'Valor'].values[0]
                }
            except: pass

            try:
                idx_start = df_res.index[df_res['Concepto'] == 'DETALLE DE INGRESOS BANCARIOS'][0]
                idx_end = df_res.index[df_res['Concepto'] == 'Total Ingresos x Bancos'][0]
                for _, row in df_res.iloc[idx_start+1 : idx_end].iterrows():
                    if pd.notna(row['Valor']) and row['Valor'] > 0:
                        self.datos_bancos[str(row['Concepto']).replace("Ingresos ", "")] = row['Valor']
            except: pass

            try:
                idx_start = df_res.index[df_res['Concepto'] == 'DETALLE DE INGRESOS POR CAJA'][0]
                idx_end = df_res.index[df_res['Concepto'] == 'Total Ingresos x Caja'][0]
                for _, row in df_res.iloc[idx_start+1 : idx_end].iterrows():
                    if pd.notna(row['Valor']) and row['Valor'] > 0:
                        nombre = str(row['Concepto']).replace("   > C.C: ", "").replace("   > ", "")
                        self.datos_caja[nombre] = row['Valor']
            except: pass
        except: pass

    def volver_dona(self, e):
        self.nivel_dona = "GENERAL"
        self.actualizar_dona_ui()

    def actualizar_dona_ui(self):
        datos = {}
        if self.nivel_dona == "GENERAL":
            datos = self.datos_general
            self.titulo_grafico.value = "Ingresos (Bancos vs Caja)"
            self.boton_volver.visible = False
        elif self.nivel_dona == "BANCOS":
            datos = self.datos_bancos
            self.titulo_grafico.value = "Detalle Ingresos Bancarios"
            self.boton_volver.visible = True
        elif self.nivel_dona == "CAJA":
            datos = dict(sorted(self.datos_caja.items(), key=lambda x: x[1], reverse=True))
            self.titulo_grafico.value = "Detalle Ingresos por Cajas"
            self.boton_volver.visible = True

        secciones = []
        leyenda_items = []
        filas_tabla = []
        self.datos_hover = []
        
        total = sum(datos.values()) if sum(datos.values()) > 0 else 1
        
        for i, (label, valor) in enumerate(datos.items()):
            color = obtener_color_ingresos(label, self.nivel_dona)
            pct = (valor / total) * 100
            
            secciones.append(
                ft.PieChartSection(value=valor, color=color, radius=55, title=f"{pct:.0f}%" if pct >= 4 else "", 
                                   title_style=ft.TextStyle(size=11, color=ft.colors.WHITE, weight=ft.FontWeight.BOLD))
            )
            self.datos_hover.append({"label": label, "valor": valor, "pct": pct, "color": color})
            
            def crear_evento(cat_label):
                def on_click(e):
                    if self.nivel_dona == "GENERAL":
                        self.nivel_dona = cat_label.upper()
                        self.actualizar_dona_ui()
                return on_click

            es_clicable = self.nivel_dona == "GENERAL"
            leyenda_items.append(
                ft.Container(
                    content=ft.Row([
                        ft.Container(width=10, height=10, border_radius=5, bgcolor=color),
                        ft.Column([
                            ft.Text(label + (" (Clic aquí)" if es_clicable else ""), size=11, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_900),
                            ft.Text(f"$ {valor:,.2f}", size=11, color=ft.colors.GREY_600)
                        ], spacing=1, expand=True) 
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    on_click=crear_evento(label) if es_clicable else None,
                    padding=5, border_radius=5, height=45 
                )
            )

            filas_tabla.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(label, size=11, color=ft.colors.BLUE_900)),
                    ft.DataCell(ft.Text(f"{pct:.1f}%", size=11, color=ft.colors.GREY_700)),
                    ft.DataCell(ft.Text(f"$ {valor:,.2f}", size=11, color=ft.colors.GREEN_700, weight=ft.FontWeight.BOLD)),
                ])
            )
        
        filas_tabla.append(
            ft.DataRow(cells=[
                ft.DataCell(ft.Text("TOTAL", size=11, weight=ft.FontWeight.W_900, color=ft.colors.BLUE_900)),
                ft.DataCell(ft.Text("100%", size=11, weight=ft.FontWeight.W_900, color=ft.colors.BLUE_900)),
                ft.DataCell(ft.Text(f"$ {total:,.2f}", size=11, weight=ft.FontWeight.W_900, color=ft.colors.GREEN_900)),
            ])
        )
            
        self.dona_grafico.sections = secciones
        self.leyenda_contenedor.controls = leyenda_items
        self.tabla_detalle.rows = filas_tabla 

        # --- NUEVO: Disparamos el evento al Padre (el Dashboard) ---
        if self.on_nivel_change:
            self.on_nivel_change(self.nivel_dona)

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
                else:
                    section.radius = 55 
            
            if idx == -1:
                self.texto_hover.value = "Apunta al grafico para detalles"
                self.texto_hover.color = ft.colors.GREY_400
                self.texto_hover.weight = ft.FontWeight.NORMAL
            
            self.update_safe()
        except: pass 

    def update_safe(self):
        if self.page and getattr(self, 'uid', None):
            self.update()