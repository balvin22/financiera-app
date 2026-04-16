# src/ui/components/tendencia_egresos.py
import flet as ft
import json
import math
from src.core.mapeos import obtener_color, obtener_color_proveedor
from src.data_engine.transformers.rules_tendencias import procesar_tendencias

class TendenciaEgresos(ft.Container):
    def __init__(self):
        super().__init__()
        self.expand = True
        self.height = 650 
        self.bgcolor = ft.colors.WHITE
        self.border_radius = 12
        self.padding = ft.padding.all(16)
        self.border = ft.border.all(1, ft.colors.GREY_200)

        self.nivel_actual = "GENERAL"
        self.caja_seleccionada = None
        self.categorias_activas = []
        self.datos_diarios = {}

        self.titulo = ft.Text("Evolución Diaria (Sincronización Perfecta)", weight=ft.FontWeight.W_800, size=16, color=ft.colors.BLUE_900)

        self.dropdown_dias = ft.Dropdown(
            label="Vista", width=200, options=[ft.dropdown.Option(key="ALL", text="Todo el mes")],
            on_change=self.mostrar_detalle_dia, text_size=13, height=50,    
            content_padding=ft.padding.only(left=15, right=10, top=10, bottom=10), value="ALL",
            border_radius=8, border_color=ft.colors.GREY_300, focused_border_color=ft.colors.BLUE_500,
            label_style=ft.TextStyle(size=12, color=ft.colors.BLUE_700)
        )

        self.card_total    = self._make_metric_card("Total Salidas", "–")
        self.card_promedio = self._make_metric_card("Promedio diario", "–")
        self.card_maximo   = self._make_metric_card("Salida máxima", "–")
        self.card_mayor    = self._make_metric_card("Líder del rubro", "–")

        self.fila_metricas = ft.Row([self.card_total, self.card_promedio, self.card_maximo, self.card_mayor], spacing=10)
        self.leyenda_row = ft.Row(wrap=True, spacing=8, scroll=ft.ScrollMode.AUTO)
        self.leyenda_container = ft.Container(content=self.leyenda_row, height=50, expand=True)

        self.txt_total_hover = ft.Text("Pasa el mouse sobre el gráfico para ver detalles", size=12, color=ft.colors.BLUE_800, weight=ft.FontWeight.W_600)
        self.panel_hover = ft.Row(wrap=True, spacing=12) 
        self.hover_container = ft.Container(
            content=ft.Column([self.txt_total_hover, self.panel_hover], spacing=4, tight=True),
            padding=ft.padding.symmetric(horizontal=12, vertical=8), bgcolor=ft.colors.BLUE_50,
            border_radius=8, animate_size=200 
        )

        self.fila_controles = ft.Row([self.leyenda_container, self.dropdown_dias], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        self.chart_container = ft.Container(height=400)

        self.cargar_datos_y_dibujar()

    def cargar_datos_y_dibujar(self):
        """Llama al motor de reglas y repinta la UI."""
        self.categorias_activas, self.datos_diarios = procesar_tendencias(self.nivel_actual, self.caja_seleccionada)
        
        opciones = [ft.dropdown.Option(key="ALL", text="Todo el mes")]
        for d in sorted(self.datos_diarios.keys()):
            opciones.append(ft.dropdown.Option(key=str(d), text=self.datos_diarios[d]["label_larga"]))
        self.dropdown_dias.options = opciones

        self._construir_ui()
        self._actualizar_metricas()
        self._construir_leyenda()
        self.dibujar_grafico("ALL")

    def _make_metric_card(self, label: str, valor: str) -> ft.Container:
        val = ft.Text(valor, size=15, color=ft.colors.BLUE_900, weight=ft.FontWeight.W_800)
        return ft.Container(
            content=ft.Column([ft.Text(label, size=10, color=ft.colors.GREY_600), val], spacing=2, tight=True),
            bgcolor=ft.colors.WHITE, border_radius=8, padding=ft.padding.symmetric(horizontal=12, vertical=8), expand=True, 
            data=val, border=ft.border.all(1, ft.colors.BLUE_100)
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
        if cat == "Otros Egresos" or cat == "Otras Cajas": return ft.colors.GREY_500
        if self.nivel_actual == "DETALLE_CAJA": return obtener_color_proveedor(cat, idx)
        return obtener_color(cat, modo="ENTIDADES", nivel=self.nivel_actual)

    def _construir_ui(self):
        self.content = ft.Column([
            self.titulo,
            ft.Container(height=8), self.fila_metricas,
            ft.Container(height=15), self.fila_controles,
            ft.Container(height=4), self.hover_container, 
            ft.Divider(height=10, color=ft.colors.GREY_100),
            self.chart_container,
        ], spacing=0)

    def set_modo(self, modo: str):
        self.nivel_actual = "GENERAL"
        self.caja_seleccionada = None
        self.cargar_datos_y_dibujar()
        if self.page: self.update()

    def set_nivel(self, nuevo_nivel: str, caja_sel: str = None):
        self.nivel_actual = nuevo_nivel
        self.caja_seleccionada = caja_sel
        self.cargar_datos_y_dibujar()
        if self.page: self.update()

    def _construir_leyenda(self):
        self.leyenda_row.controls = []
        for i, cat in enumerate(self.categorias_activas):
            nombre = cat.title()[:25]
            self.leyenda_row.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Container(width=10, height=10, border_radius=5, bgcolor=self.get_color_ft(i, cat)),
                        ft.Text(nombre, size=11, weight=ft.FontWeight.W_600, color=ft.colors.BLUE_GREY_800)
                    ], spacing=6, tight=True),
                    padding=ft.padding.symmetric(horizontal=8, vertical=4),
                    bgcolor=ft.colors.BLUE_50,
                    border_radius=15
                )
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
                            nombre = cat.title()[:20]
                            controles.append(
                                ft.Row([
                                    ft.Container(width=8, height=8, border_radius=4, bgcolor=self.get_color_ft(idx, cat)),
                                    ft.Text(f"{nombre}: $ {val:,.0f}", size=11, color=self.get_color_ft(idx, cat), weight=ft.FontWeight.W_800)
                                ], spacing=6, tight=True)
                            )
                    self.panel_hover.controls = controles
                    self.txt_total_hover.value = f"Resumen {datos['label_corta']} (Total: $ {datos['total']:,.0f})"
            else:
                self.panel_hover.controls = []
                self.txt_total_hover.value = "Pasa el mouse sobre el gráfico para ver detalles"
            if self.page: self.update()
        except: pass

    def dibujar_grafico(self, seleccion: str):
        if not self.datos_diarios:
            self.chart_container.content = ft.Container(
                content=ft.Text("No hay datos para esta selección.", color=ft.colors.GREY_500, size=16),
                alignment=ft.alignment.center, expand=True
            )
            return
        
        todos_valores = [v for d in self.datos_diarios.values() for v in d["valores"].values() if v > 0]
        max_val = max(todos_valores) if todos_valores else 0
        max_m = max_val / 1_000_000
        techo_m = math.ceil(max_m / 10) * 10 if max_m > 0 else 50
        paso = techo_m / 4
        labels_y = [ft.ChartAxisLabel(value=i*paso, label=ft.Text(f"{int(i*paso)}M", size=11, color=ft.colors.GREY_500, weight=ft.FontWeight.BOLD)) for i in range(5)]

        if seleccion == "ALL":
            data_series = []
            for i, cat in enumerate(self.categorias_activas):
                puntos = [ft.LineChartDataPoint(x=d, y=round(self.datos_diarios[d]["valores"][cat]/1_000_000, 2), tooltip=" ") for d in sorted(self.datos_diarios.keys())]
                data_series.append(ft.LineChartData(data_points=puntos, stroke_width=2.5, color=self.get_color_ft(i, cat), curved=True, stroke_cap_round=True, point=ft.ChartCirclePoint(radius=2, color=self.get_color_ft(i, cat))))

            labels_x = [ft.ChartAxisLabel(value=d, label=ft.Container(content=ft.Column([
                ft.Text(self.datos_diarios[d]["label_corta"].split()[0].upper(), size=9, color=ft.colors.BLUE_700, weight=ft.FontWeight.W_800),
                ft.Text(str(d), size=11, color=ft.colors.GREY_600)
            ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER))) for d in sorted(self.datos_diarios.keys())]

            chart = ft.LineChart(
                data_series=data_series, bottom_axis=ft.ChartAxis(labels=labels_x, labels_size=30),
                left_axis=ft.ChartAxis(labels=labels_y, labels_size=45), min_y=0, max_y=techo_m * 1.05,
                border=ft.border.all(1, ft.colors.TRANSPARENT), tooltip_bgcolor=ft.colors.TRANSPARENT,
                on_chart_event=self.on_hover_chart, expand=True, horizontal_grid_lines=ft.ChartGridLines(color=ft.colors.GREY_200, width=1, dash_pattern=[5, 5])
            )
            self.chart_container.content = ft.Row([ft.Container(content=chart, width=2500, height=400)], scroll=ft.ScrollMode.ALWAYS)
        else:
            dia = int(seleccion)
            datos = self.datos_diarios[dia]
            cats_ord = [c for c in self.categorias_activas if datos["valores"].get(c, 0) > 0]
            bar_groups = [ft.BarChartGroup(x=pos, bar_rods=[ft.BarChartRod(
                from_y=0, to_y=round(datos["valores"][cat]/1_000_000, 2), width=45, color=self.get_color_ft(self.categorias_activas.index(cat), cat),
                border_radius=ft.border_radius.vertical(top=6), tooltip=f"$ {datos['valores'][cat]:,.0f}"
            )]) for pos, cat in enumerate(cats_ord)]
            
            labels_bottom = [ft.ChartAxisLabel(value=pos, label=ft.Text(cat[:12] + ".." if len(cat)>12 else cat, size=10, weight=ft.FontWeight.W_700, color=ft.colors.BLUE_900)) for pos, cat in enumerate(cats_ord)]
            
            chart = ft.BarChart(
                bar_groups=bar_groups, bottom_axis=ft.ChartAxis(labels=labels_bottom, labels_size=30),
                left_axis=ft.ChartAxis(labels=labels_y, labels_size=45), max_y=techo_m * 1.1,
                border=ft.border.all(1, ft.colors.TRANSPARENT), tooltip_bgcolor=ft.colors.BLUE_GREY_900, expand=True,
                horizontal_grid_lines=ft.ChartGridLines(color=ft.colors.GREY_200, width=1, dash_pattern=[5, 5])
            )
            self.chart_container.content = chart

    def mostrar_detalle_dia(self, e):
        self.dibujar_grafico(self.dropdown_dias.value)
        if self.page: self.update()