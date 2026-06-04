# src/ui/components/base_grafico.py
import flet as ft
import polars as pl
import math
import re
import json
from src.utils.data_loader import DataLoader
from src.core.logger import app_logger

TEMA_INGRESOS = {
    "primary": ft.colors.BLUE_900,
    "primary_50": ft.colors.BLUE_50,
    "accent": ft.colors.GREEN_700,
    "accent_900": ft.colors.GREEN_900,
    "border": ft.colors.GREY_200,
    "titulo": ft.colors.BLUE_900,
}

TEMA_EGRESOS = {
    "primary": ft.colors.RED_900,
    "primary_50": ft.colors.RED_50,
    "accent": ft.colors.RED_700,
    "accent_900": ft.colors.RED_900,
    "border": ft.colors.GREY_200,
    "titulo": ft.colors.RED_900,
}

class BaseGrafico(ft.Container):
    def __init__(self, on_nivel_change=None, **kwargs):
        super().__init__()
        self.on_nivel_change = on_nivel_change
        self.banco = kwargs.get("banco", "TODOS")
        self.mes = kwargs.get("mes", None)
        self.nivel_dona = "GENERAL"
        self.datos_hover = []

        self.expand = True
        self.height = 350
        self.bgcolor = ft.colors.WHITE
        self.border_radius = 12
        self.padding = 20
        self.border = ft.border.all(1, ft.colors.GREY_200)

        tema = self._get_tema_colores()

        self.dona_grafico = ft.PieChart(
            sections=[], sections_space=2, center_space_radius=35,
            on_chart_event=self.on_hover_dona
        )
        self.texto_hover = ft.Text(
            "Apunta al grafico para detalles", size=12,
            color=ft.colors.GREY_600, italic=True
        )
        self.leyenda_contenedor = ft.Column(scroll=ft.ScrollMode.ALWAYS, spacing=5)
        self.tabla_detalle = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Concepto", size=12, weight=ft.FontWeight.BOLD, color=tema["primary"])),
                ft.DataColumn(ft.Text("%", size=12, weight=ft.FontWeight.BOLD, color=tema["primary"])),
                ft.DataColumn(ft.Text("Valor", size=12, weight=ft.FontWeight.BOLD, color=tema["primary"])),
            ],
            rows=[], column_spacing=15, heading_row_color=tema["primary_50"]
        )
        self.titulo_grafico = ft.Text("", size=16, weight=ft.FontWeight.BOLD, color=tema["titulo"])
        self.boton_volver = ft.Container(
            content=ft.Text("← Volver", size=12, weight=ft.FontWeight.BOLD, color=tema["accent"]),
            on_click=self.volver_dona,
            visible=False,
        )

        self._build_extra_ui()
        self.construir_ui()

    def _get_tema_colores(self):
        return TEMA_INGRESOS

    def _build_extra_ui(self):
        pass

    def _get_datos_nivel(self):
        return {}

    def _obtener_color(self, label, idx):
        return ft.colors.BLUE_500

    def construir_ui(self):
        extra = self._build_top_row_extra()
        top_row = ft.Row([self.titulo_grafico], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        if extra:
            top_row = ft.Row([self.titulo_grafico, ft.Container(width=15), extra],
                             alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        self.content = ft.Column([
            ft.Row([top_row, self.boton_volver], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(height=10, color=ft.colors.GREY_200),
            ft.Row([
                ft.Container(
                    content=ft.Column([self.dona_grafico, self.texto_hover], spacing=5, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    width=240,
                ),
                ft.Container(
                    content=self.leyenda_contenedor,
                    width=220, height=260,
                    border=ft.border.only(right=ft.border.BorderSide(1, ft.colors.GREY_200)),
                ),
                ft.Container(
                    content=ft.Column([self.tabla_detalle], scroll=ft.ScrollMode.ALWAYS, expand=True),
                    expand=True, height=260,
                    padding=ft.padding.only(left=20),
                ),
            ], spacing=0),
        ], spacing=0)

    def _build_top_row_extra(self):
        return None

    def actualizar_dona_ui(self):
        tema = self._get_tema_colores()
        datos = self._get_datos_nivel()
        if not datos:
            self.dona_grafico.sections = []
            self.leyenda_contenedor.controls = [
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.INFO_OUTLINE, size=16, color=ft.colors.GREY_400),
                        ft.Text("No hay datos para este nivel", size=12, color=ft.colors.GREY_500),
                    ]),
                    padding=10,
                )
            ]
            self.tabla_detalle.rows = [
                ft.DataRow(cells=[ft.DataCell(ft.Text("—")), ft.DataCell(ft.Text("—")), ft.DataCell(ft.Text("—"))])
            ]
            self.titulo_grafico.value = "Sin datos disponibles"
            self.boton_volver.visible = self.nivel_dona != "GENERAL"
            self.dona_grafico.sections = []
            self.update_safe()
            return

        total = sum(datos.values())
        secciones = []
        self.datos_hover = []
        leyenda_items = []
        filas_tabla = []

        items = sorted(datos.items(), key=lambda x: x[1], reverse=True)
        for idx, (label, valor) in enumerate(items):
            if valor <= 0:
                continue
            pct = (valor / total) * 100 if total > 0 else 0
            color = self._obtener_color(label, idx)
            secciones.append(ft.PieChartSection(
                value=round(valor, 2), title=f"{pct:.1f}%", color=color,
                title_style=ft.TextStyle(size=11, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE),
                radius=55, title_radius=65,
            ))
            self.datos_hover.append({"label": label, "valor": valor, "pct": pct, "color": color})

            leyenda_items.append(
                ft.Container(
                    content=ft.Row([
                        ft.Container(width=10, height=10, border_radius=5, bgcolor=color),
                        ft.Column([
                            ft.Text(label[:25], size=11, weight=ft.FontWeight.W_600, color=tema["primary"]),
                            ft.Text(f"$ {valor:,.2f}  ({pct:.1f}%)", size=10, color=ft.colors.GREY_600),
                        ], spacing=1, tight=True),
                    ], spacing=8),
                    padding=ft.padding.symmetric(vertical=3),
                )
            )

            filas_tabla.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(label[:30], size=11)),
                ft.DataCell(ft.Text(f"{pct:.1f}%", size=11)),
                ft.DataCell(ft.Text(f"$ {valor:,.2f}", size=11, color=tema["accent"], weight=ft.FontWeight.BOLD)),
            ]))

        filas_tabla.append(ft.DataRow(cells=[
            ft.DataCell(ft.Text("TOTAL", size=12, weight=ft.FontWeight.BOLD)),
            ft.DataCell(ft.Text("100%", size=12, weight=ft.FontWeight.BOLD)),
            ft.DataCell(ft.Text(f"$ {total:,.2f}", size=12, color=tema["accent_900"], weight=ft.FontWeight.BOLD)),
        ]))

        self.dona_grafico.sections = secciones
        self.leyenda_contenedor.controls = leyenda_items
        self.tabla_detalle.rows = filas_tabla
        self.titulo_grafico.value = self._get_titulo_para_nivel()
        self.boton_volver.visible = self.nivel_dona != "GENERAL"

        if self.on_nivel_change:
            self.on_nivel_change(self.nivel_dona)

        self.update_safe()

    def _get_titulo_para_nivel(self):
        return self.nivel_dona.replace("_", " ").title()

    def volver_dona(self, e):
        if self.nivel_dona in ("BANCOS", "CAJA"):
            self.nivel_dona = "GENERAL"
        self.actualizar_dona_ui()

    def on_hover_dona(self, e):
        try:
            if e.data:
                data = json.loads(e.data)
                idx = data.get("section_index")
                if idx is not None and 0 <= idx < len(self.datos_hover):
                    d = self.datos_hover[idx]
                    self.texto_hover.value = f"  {d['label']}: $ {d['valor']:,.2f} ({d['pct']:.1f}%)"
                    self.texto_hover.color = d["color"]
                    self.texto_hover.weight = ft.FontWeight.BOLD
                    if idx < len(self.dona_grafico.sections):
                        self.dona_grafico.sections[idx].radius = 63
                        self.dona_grafico.sections[idx].title_radius = 73
                else:
                    self.texto_hover.value = "Apunta al grafico para detalles"
                    self.texto_hover.color = ft.colors.GREY_600
                    self.texto_hover.weight = ft.FontWeight.NORMAL
                    for s in self.dona_grafico.sections:
                        s.radius = 55
                        s.title_radius = 65
                self.update_safe()
        except:
            pass

    def update_safe(self):
        try:
            self.update()
        except:
            pass
