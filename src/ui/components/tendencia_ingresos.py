# ui/components/tendencia_ingresos.py
import flet as ft
import polars as pl
import pandas as pd
import os
import json
import math
from src.core.mapeos import MAPEO_CAJAS_TITULO, COLORES_FT, obtener_color_ingresos

class TendenciaIngresos(ft.Container):
    def __init__(self):
        super().__init__()
        self.expand = True
        self.height = 650 
        self.bgcolor = ft.colors.WHITE
        self.border_radius = 12
        self.padding = ft.padding.all(16)
        self.border = ft.border.all(1, ft.colors.GREY_200)

        self.nivel_actual = "GENERAL"
        self.categorias_activas = []
        self.datos_diarios = {}

        self.titulo = ft.Text("Tendencia de ingresos diarios", weight=ft.FontWeight.W_600, size=15, color=ft.colors.BLUE_GREY_900)

        self.dropdown_dias = ft.Dropdown(
            label="Vista", 
            width=200, 
            options=[ft.dropdown.Option(key="ALL", text="Todo el mes")],
            on_change=self.mostrar_detalle_dia, 
            text_size=13,
            height=50,    
            content_padding=ft.padding.only(left=15, right=10, top=10, bottom=10),
            value="ALL",
            border_radius=8,
            border_color=ft.colors.GREY_300,
            focused_border_color=ft.colors.BLUE_500,
            label_style=ft.TextStyle(size=12, color=ft.colors.BLUE_GREY_500)
        )

        self.card_total    = self._make_metric_card("Total Ingresos", "–")
        self.card_promedio = self._make_metric_card("Promedio diario", "–")
        self.card_maximo   = self._make_metric_card("Máximo diario", "–")
        self.card_mayor    = self._make_metric_card("Mayor concepto", "–")

        self.fila_metricas = ft.Row([self.card_total, self.card_promedio, self.card_maximo, self.card_mayor], spacing=10)
        
        self.leyenda_row = ft.Row(wrap=True, spacing=8, scroll=ft.ScrollMode.AUTO)
        self.leyenda_container = ft.Container(content=self.leyenda_row, height=50, expand=True)

        self.txt_total_hover = ft.Text("Pasa el mouse sobre el gráfico para ver detalles", size=12, color=ft.colors.BLUE_GREY_700, weight=ft.FontWeight.W_600)
        self.panel_hover = ft.Row(wrap=True, spacing=12) 
        
        self.hover_container = ft.Container(
            content=ft.Column([self.txt_total_hover, self.panel_hover], spacing=4, tight=True),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            bgcolor=ft.colors.GREY_50,
            border_radius=8,
            animate_size=200 
        )

        self.fila_controles = ft.Row([self.dropdown_dias], alignment=ft.MainAxisAlignment.START)
        
        # AUMENTO DE ALTURA: De 355 a 420 para que empuje el gráfico y la barra hasta el fondo
        self.chart_container = ft.Container(height=400)

        self.extraer_datos()
        self._construir_ui()
        self.dibujar_grafico("ALL")

    def _make_metric_card(self, label: str, valor: str) -> ft.Container:
        val = ft.Text(valor, size=15, color=ft.colors.BLUE_GREY_900, weight=ft.FontWeight.W_600)
        return ft.Container(
            content=ft.Column([ft.Text(label, size=10, color=ft.colors.GREY_600), val], spacing=2, tight=True),
            bgcolor=ft.colors.GREY_50, border_radius=8, padding=ft.padding.symmetric(horizontal=12, vertical=8), expand=True, data=val
        )

    def _actualizar_metricas(self):
        try:
            df_res = pl.read_parquet("local_cache/base_resumen.parquet").to_pandas()
            
            def get_val(concepto):
                v = df_res.loc[df_res['Concepto'] == concepto, 'Valor'].values
                return float(v[0]) if len(v) > 0 else 0.0

            ing_mes = get_val('Total Ingresos del mes')
            
            if self.nivel_actual == "GENERAL":
                total_mostrar =  ing_mes
                mayor_nombre = "Bancos" if get_val('Total Ingresos x Bancos') > get_val('Total Ingresos x Caja') else "Caja"
            else:
                clave = 'Total Ingresos x Bancos' if self.nivel_actual == "BANCOS" else 'Total Ingresos x Caja'
                total_mostrar = get_val(clave)
                mayor_nombre = self.nivel_actual.capitalize()

            totales_dias = [d["total"] for d in self.datos_diarios.values() if d["total"] > 0]
            promedio = sum(totales_dias) / len(totales_dias) if totales_dias else 0
            maximo = max(totales_dias) if totales_dias else 0

            self.card_total.data.value = f"$ {total_mostrar:,.2f}"
            self.card_promedio.data.value = f"$ {promedio:,.2f}"
            self.card_maximo.data.value = f"$ {maximo:,.2f}"
            self.card_mayor.data.value = mayor_nombre
        except: pass

    def get_color_ft(self, idx: int, cat: str):
        return obtener_color_ingresos(cat, self.nivel_actual)

    def _construir_ui(self):
        self.content = ft.Column([
            ft.Row([self.titulo, self.leyenda_container], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Container(height=8), self.fila_metricas,
            ft.Container(height=8), self.fila_controles,
            ft.Container(height=4), self.hover_container, 
            ft.Divider(height=10, color=ft.colors.GREY_100),
            self.chart_container,
        ], spacing=0)

    def set_nivel(self, nuevo_nivel: str):
        self.nivel_actual = nuevo_nivel
        self.extraer_datos()
        self.dibujar_grafico(self.dropdown_dias.value)
        if self.page: self.update()

    def extraer_datos(self):
        try:
            if not os.path.exists("local_cache/base_global.parquet"): return
            df = pl.read_parquet("local_cache/base_global.parquet").to_pandas()
            df["Fecha"] = pd.to_datetime(df["Fecha"], dayfirst=True, errors="coerce")
            df = df.dropna(subset=["Fecha"])
            df["Dia"] = df["Fecha"].dt.day
            df["Dia_Semana"] = df["Fecha"].dt.dayofweek

            dias_cortos = {0:"Lun",1:"Mar",2:"Mié",3:"Jue",4:"Vie",5:"Sáb",6:"Dom"}
            dias_completos = {0:"Lunes",1:"Martes",2:"Miércoles",3:"Jueves",4:"Viernes",5:"Sábado",6:"Domingo"}

            df_ing = df[(df["Ingreso"] > 0) & 
                        (~df["Categoria_Flujo"].isin(["Traslado_Salida", "Traslado_Entrada"])) &
                        (~df["Concepto"].str.upper().str.contains("APORTE", na=False))].copy()
            if self.nivel_actual == "GENERAL":
                df_ing["Categoria"] = df_ing["Origen"].apply(lambda x: "Caja" if str(x).strip().upper() == "CAJA" else "Bancos")
            elif self.nivel_actual == "BANCOS":
                df_ing = df_ing[df_ing["Origen"].str.strip().str.upper() != "CAJA"].copy()
                df_ing["Categoria"] = df_ing["Origen"].str.capitalize()
            elif self.nivel_actual == "CAJA":
                df_ing = df_ing[df_ing["Origen"].str.strip().str.upper() == "CAJA"].copy()
                df_ing["CCO_Clean"] = df_ing["NOMBRE_CCO"].astype(str).str.extract(r"(\d{5})", expand=False)
                df_ing["Categoria"] = df_ing["CCO_Clean"].map(MAPEO_CAJAS_TITULO).fillna(df_ing["NOMBRE_CCO"]).str.title()

            agrupado = df_ing.groupby(["Dia", "Categoria"]).agg({"Ingreso": "sum", "Dia_Semana": "first"}).reset_index()
            totales_cat = agrupado.groupby("Categoria")["Ingreso"].sum().sort_values(ascending=False)
            self.categorias_activas = totales_cat.index.tolist()

            opciones = [ft.dropdown.Option(key="ALL", text="Todo el mes")]
            self.datos_diarios = {}
            for d in sorted(agrupado["Dia"].unique()):
                subset = agrupado[agrupado["Dia"] == d]
                dsn = int(subset["Dia_Semana"].iloc[0])
                valores_dia = {cat: float(subset[subset["Categoria"] == cat]["Ingreso"].sum()) if cat in subset["Categoria"].values else 0.0 for cat in self.categorias_activas}
                self.datos_diarios[d] = {"label_corta": f"{dias_cortos[dsn]} {d}", "label_larga": f"{dias_completos[dsn]} {d}", "valores": valores_dia, "total": sum(valores_dia.values())}
                opciones.append(ft.dropdown.Option(key=str(d), text=self.datos_diarios[d]["label_larga"]))

            self.dropdown_dias.options = opciones
            self._actualizar_metricas()
            self._construir_leyenda()
        except: pass

    def _construir_leyenda(self):
        self.leyenda_row.controls = [ft.Row([ft.Container(width=8, height=8, border_radius=4, bgcolor=self.get_color_ft(i, cat)), ft.Text(cat[:16], size=10, weight=ft.FontWeight.W_500, color=ft.colors.GREY_700)], spacing=4, tight=True) for i, cat in enumerate(self.categorias_activas)]

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
                            controles.append(ft.Row([ft.Container(width=7, height=7, border_radius=4, bgcolor=self.get_color_ft(idx, cat)), ft.Text(f"{cat[:12]}: $ {val:,.2f}", size=11, color=self.get_color_ft(idx, cat), weight=ft.FontWeight.W_600)], spacing=4, tight=True))
                    
                    self.panel_hover.controls = controles
                    self.txt_total_hover.value = f"Resumen {datos['label_corta']} (Total: $ {datos['total']:,.2f})"
            else:
                self.panel_hover.controls = []
                self.txt_total_hover.value = "Pasa el mouse sobre el gráfico para ver detalles"
            if self.page: self.update()
        except: pass

    def dibujar_grafico(self, seleccion: str):
        if not self.datos_diarios: return
        
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
                data_series.append(ft.LineChartData(
                    data_points=puntos, 
                    stroke_width=1.5, 
                    color=self.get_color_ft(i, cat), 
                    curved=True, 
                    stroke_cap_round=True, 
                    point=ft.ChartCirclePoint(radius=1.5)
                ))

            # Para pegar el texto al scrollbar, le damos un height mínimo al contenedor del texto y le quitamos los paddings extras.
            labels_x = [ft.ChartAxisLabel(value=d, label=ft.Container(content=ft.Column([ft.Text(self.datos_diarios[d]["label_corta"].split()[0].upper(), size=8, color=ft.colors.BLUE_GREY_700, weight=ft.FontWeight.W_600), ft.Text(str(d), size=10, color=ft.colors.GREY_500)], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER))) for d in sorted(self.datos_diarios.keys())]

            # Aumentamos ligeramente el labels_size para que Flet no corte la letra por debajo, pero sin separarlo de la barra
            chart = ft.LineChart(data_series=data_series, bottom_axis=ft.ChartAxis(labels=labels_x, labels_size=26), left_axis=ft.ChartAxis(labels=labels_y, labels_size=44), min_y=0, max_y=techo_m * 1.05, border=ft.border.all(1, ft.colors.TRANSPARENT), tooltip_bgcolor=ft.colors.TRANSPARENT, on_chart_event=self.on_hover_chart, expand=True)
            
            # AUMENTO DE ALTURA INTERNA: De 350 a 415 para que llene el contenedor nuevo y baje los textos hasta el scroll
            self.chart_container.content = ft.Row(
                [ft.Container(content=chart, width=2500, height=400)], 
                scroll=ft.ScrollMode.ALWAYS
            )
        else:
            dia = int(seleccion)
            datos = self.datos_diarios[dia]
            cats_ord = [c for c in self.categorias_activas if datos["valores"].get(c, 0) > 0]
            bar_groups = [ft.BarChartGroup(x=pos, bar_rods=[ft.BarChartRod(from_y=0, to_y=round(datos["valores"][cat]/1_000_000, 2), width=40, color=self.get_color_ft(self.categorias_activas.index(cat), cat), border_radius=5, tooltip=f"$ {datos['valores'][cat]:,.2f}")]) for pos, cat in enumerate(cats_ord)]
            
            labels_bottom = [ft.ChartAxisLabel(value=pos, label=ft.Text(cat[:10], size=10, weight=ft.FontWeight.W_600)) for pos, cat in enumerate(cats_ord)]
            
            chart = ft.BarChart(bar_groups=bar_groups, bottom_axis=ft.ChartAxis(labels=labels_bottom, labels_size=26), left_axis=ft.ChartAxis(labels=labels_y, labels_size=44), max_y=techo_m * 1.1, border=ft.border.all(1, ft.colors.TRANSPARENT), tooltip_bgcolor=ft.colors.WHITE, expand=True)
            self.chart_container.content = chart
            
    def mostrar_detalle_dia(self, e):
        self.dibujar_grafico(self.dropdown_dias.value)
        if self.page: self.update()