# src/ui/components/base_tendencia.py
import flet as ft
import json
import math
import polars as pl
from src.core.logger import app_logger

TEMA_TENDENCIA_INGRESOS = {
    "leyenda_bg": ft.colors.BLUE_50,
    "accent": ft.colors.BLUE_500,
}

TEMA_TENDENCIA_EGRESOS = {
    "leyenda_bg": ft.colors.RED_50,
    "accent": ft.colors.RED_500,
}

class BaseTendencia(ft.Container):
    def __init__(self, banco="TODOS", mes=None):
        super().__init__()
        self.banco = banco
        self.mes = mes
        self.expand = True
        self.height = 650
        self.bgcolor = ft.colors.WHITE
        self.border_radius = 12
        self.padding = ft.padding.all(16)
        self.border = ft.border.all(1, ft.colors.GREY_200)

        self.nivel_actual = "GENERAL"
        self.categorias_activas = []
        self.datos_diarios = {}
        self.max_categorias = 5
        self.categorias_activadas = None
        self.todas_categorias = []
        self._agrupado_cache = None

        self.titulo = ft.Text("", weight=ft.FontWeight.W_600, size=15, color=ft.colors.BLUE_GREY_900)

        self.dropdown_dias = ft.Dropdown(
            label="Vista", width=200,
            options=[ft.dropdown.Option(key="ALL", text="Todo el mes")],
            on_change=self.mostrar_detalle_dia, text_size=13, height=50,
            content_padding=ft.padding.only(left=15, right=10, top=10, bottom=10),
            value="ALL", border_radius=8, border_color=ft.colors.GREY_300,
            focused_border_color=ft.colors.BLUE_500,
            label_style=ft.TextStyle(size=12, color=ft.colors.BLUE_GREY_500)
        )

        self.card_total = self._make_metric_card("Total", "–")
        self.card_promedio = self._make_metric_card("Promedio diario", "–")
        self.card_maximo = self._make_metric_card("Máximo diario", "–")
        self.card_mayor = self._make_metric_card("Mayor concepto", "–")

        self.fila_metricas = ft.Row([self.card_total, self.card_promedio, self.card_maximo, self.card_mayor], spacing=10)
        self.leyenda_row = ft.Row(wrap=True, spacing=8, scroll=ft.ScrollMode.AUTO)
        self.leyenda_container = ft.Container(content=self.leyenda_row, height=50, expand=True)

        self.txt_total_hover = ft.Text("Pasa el mouse sobre el gráfico para ver detalles", size=12,
                                       color=ft.colors.BLUE_GREY_700, weight=ft.FontWeight.W_600)
        self.panel_hover = ft.Row(wrap=True, spacing=12)
        self.hover_container = ft.Container(
            content=ft.Column([self.txt_total_hover, self.panel_hover], spacing=4, tight=True),
            padding=ft.padding.symmetric(horizontal=12, vertical=8), bgcolor=ft.colors.GREY_50,
            border_radius=8, animate_size=200
        )

        self.dropdown_categorias = ft.Dropdown(
            label="Categorías activas", width=350,
            options=[ft.dropdown.Option("TOP", "Top 5 mayores")],
            value="TOP", on_change=self._toggle_categoria,
            text_size=13, height=50,
            content_padding=ft.padding.only(left=15, right=10, top=10, bottom=10),
            visible=False, border_radius=8,
            border_color=ft.colors.GREY_300, focused_border_color=ft.colors.BLUE_500,
            label_style=ft.TextStyle(size=12, color=ft.colors.BLUE_GREY_500)
        )

        self.fila_controles = ft.Row([self.dropdown_dias, self.dropdown_categorias], alignment=ft.MainAxisAlignment.START)
        self.chart_container = ft.Container(height=400)

    def _get_tema_tendencia(self):
        return TEMA_TENDENCIA_INGRESOS

    def _get_nombre_columna(self):
        return "Ingreso"

    def _make_metric_card(self, label: str, valor: str) -> ft.Container:
        val = ft.Text(valor, size=15, color=ft.colors.BLUE_GREY_900, weight=ft.FontWeight.W_600)
        return ft.Container(
            content=ft.Column([ft.Text(label, size=10, color=ft.colors.GREY_600), val], spacing=2, tight=True),
            bgcolor=ft.colors.GREY_50, border_radius=8, padding=ft.padding.symmetric(horizontal=12, vertical=8),
            expand=True, data=val
        )

    def _construir_ui(self):
        self.content = ft.Column([
            ft.Row([self.titulo, self.leyenda_container], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Container(height=8), self.fila_metricas,
            ft.Container(height=8), self.fila_controles,
            ft.Container(height=4), self.hover_container,
            ft.Divider(height=10, color=ft.colors.GREY_100),
            self.chart_container,
        ], spacing=0)

    def _toggle_categoria(self, e):
        cat = e.control.value
        col = self._get_nombre_columna()
        if cat == "TOP":
            self.categorias_activadas = None
        else:
            activas = list(self.categorias_activadas or self.todas_categorias[:self.max_categorias])
            if cat in activas:
                activas.remove(cat)
            elif len(activas) < self.max_categorias:
                activas.append(cat)
            else:
                activas[-1] = cat
            self.categorias_activadas = activas
        activas = self.categorias_activadas or self.todas_categorias[:self.max_categorias]
        self.categorias_activas = [c for c in self.todas_categorias if c in activas][:self.max_categorias]
        self.dropdown_categorias.options = [ft.dropdown.Option("TOP", f"Top {self.max_categorias} mayores")] + [
            ft.dropdown.Option(c, ("✓ " if c in self.categorias_activas else "") + c) for c in self.todas_categorias
        ]
        self.dropdown_categorias.value = "TOP"
        label_cats = " · ".join(self.categorias_activas)
        self.dropdown_categorias.label = f"Mostrando {len(self.categorias_activas)}: {label_cats[:40]}..."

        if self._agrupado_cache is not None:
            agrupado = self._agrupado_cache
            dias_cortos = {0: "Lun", 1: "Mar", 2: "Mié", 3: "Jue", 4: "Vie", 5: "Sáb", 6: "Dom"}
            dias_completos = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"}
            self.datos_diarios = {}
            for d in sorted(agrupado["Dia"].unique().to_list()):
                subset = agrupado.filter(pl.col("Dia") == d)
                dsn = int(subset["Dia_Semana"].to_list()[0]) if not subset.is_empty() else 0
                valores_dia = {
                    cat: float(subset.filter(pl.col("Categoria") == cat)[col].sum() or 0.0)
                    for cat in self.categorias_activas
                }
                self.datos_diarios[d] = {
                    "label_corta": f"{dias_cortos.get(dsn, '')} {d}",
                    "label_larga": f"{dias_completos.get(dsn, '')} {d}",
                    "valores": valores_dia,
                    "total": sum(valores_dia.values())
                }

        self._post_rebuild_datos()
        self._actualizar_metricas()
        self._construir_leyenda()
        self.dibujar_grafico(self.dropdown_dias.value)
        self.update_safe()

    def update_safe(self):
        try:
            self.update()
        except:
            pass

    def _construir_leyenda(self):
        tema = self._get_tema_tendencia()
        self.leyenda_row.controls = []
        for i, cat in enumerate(self.categorias_activas):
            nombre = cat.title()[:25]
            self.leyenda_row.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Container(width=10, height=10, border_radius=5, bgcolor=self.get_color_ft(i, cat)),
                        ft.Text(nombre, size=11, weight=ft.FontWeight.W_600, color=ft.colors.BLUE_GREY_800),
                    ], spacing=6, tight=True),
                    padding=ft.padding.symmetric(horizontal=8, vertical=4),
                    bgcolor=tema["leyenda_bg"],
                    border_radius=15
                )
            )

    def on_hover_chart(self, e):
        if self.dropdown_dias.value != "ALL":
            return
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
                            controles.append(ft.Row([
                                ft.Container(width=7, height=7, border_radius=4, bgcolor=self.get_color_ft(idx, cat)),
                                ft.Text(f"{cat[:12]}: $ {val:,.2f}", size=11, color=self.get_color_ft(idx, cat),
                                        weight=ft.FontWeight.W_600)
                            ], spacing=4, tight=True))
                    self.panel_hover.controls = controles
                    self.txt_total_hover.value = f"Resumen {datos['label_corta']} (Total: $ {datos['total']:,.2f})"
            else:
                self.panel_hover.controls = []
                self.txt_total_hover.value = "Pasa el mouse sobre el gráfico para ver detalles"
            self.update_safe()
        except:
            import traceback
            traceback.print_exc()

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
        labels_y = [ft.ChartAxisLabel(value=i * paso, label=ft.Text(f"{int(i * paso)}M", size=10, color=ft.colors.GREY_500))
                    for i in range(5)]

        if seleccion == "ALL":
            data_series = []
            for i, cat in enumerate(self.categorias_activas):
                puntos = [ft.LineChartDataPoint(
                    x=d, y=round(self.datos_diarios[d]["valores"][cat] / 1_000_000, 2), tooltip=" ")
                    for d in sorted(self.datos_diarios.keys())]
                data_series.append(ft.LineChartData(
                    data_points=puntos, stroke_width=1.5, color=self.get_color_ft(i, cat),
                    curved=True, stroke_cap_round=True,
                    point=ft.ChartCirclePoint(radius=1.5, color=self.get_color_ft(i, cat))
                ))

            labels_x = [ft.ChartAxisLabel(value=d, label=ft.Container(content=ft.Column([
                ft.Text(self.datos_diarios[d]["label_corta"].split()[0].upper(), size=8,
                        color=ft.colors.BLUE_GREY_700, weight=ft.FontWeight.W_600),
                ft.Text(str(d), size=10, color=ft.colors.GREY_500)
            ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER)))
                for d in sorted(self.datos_diarios.keys())]

            chart = ft.LineChart(
                data_series=data_series, bottom_axis=ft.ChartAxis(labels=labels_x, labels_size=26),
                left_axis=ft.ChartAxis(labels=labels_y, labels_size=44), min_y=0, max_y=techo_m * 1.05,
                border=ft.border.all(1, ft.colors.TRANSPARENT), tooltip_bgcolor=ft.colors.TRANSPARENT,
                on_chart_event=self.on_hover_chart, expand=True,
                horizontal_grid_lines=ft.ChartGridLines(color=ft.colors.GREY_200, width=1, dash_pattern=[5, 5])
            )
            self.chart_container.content = ft.Row(
                [ft.Container(content=chart, width=2500, height=400)], scroll=ft.ScrollMode.ALWAYS
            )
        else:
            dia = int(seleccion)
            datos = self.datos_diarios[dia]
            cats_ord = [c for c in self.categorias_activas if datos["valores"].get(c, 0) > 0]
            bar_groups = [ft.BarChartGroup(x=pos, bar_rods=[ft.BarChartRod(
                from_y=0, to_y=round(datos["valores"][cat] / 1_000_000, 2), width=40,
                color=self.get_color_ft(self.categorias_activas.index(cat), cat),
                border_radius=5, tooltip=f"$ {datos['valores'][cat]:,.2f}"
            )]) for pos, cat in enumerate(cats_ord)]

            labels_bottom = [ft.ChartAxisLabel(value=pos, label=ft.Text(cat[:10], size=10, weight=ft.FontWeight.W_600))
                             for pos, cat in enumerate(cats_ord)]

            chart = ft.BarChart(
                bar_groups=bar_groups, bottom_axis=ft.ChartAxis(labels=labels_bottom, labels_size=26),
                left_axis=ft.ChartAxis(labels=labels_y, labels_size=44), max_y=techo_m * 1.1,
                border=ft.border.all(1, ft.colors.TRANSPARENT), tooltip_bgcolor=ft.colors.WHITE, expand=True,
                horizontal_grid_lines=ft.ChartGridLines(color=ft.colors.GREY_200, width=1, dash_pattern=[5, 5])
            )
            self.chart_container.content = chart

    def mostrar_detalle_dia(self, e):
        self.dibujar_grafico(self.dropdown_dias.value)
        self.update_safe()

    def _post_rebuild_datos(self):
        pass
