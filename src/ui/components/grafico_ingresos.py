# ui/components/grafico_ingresos.py
import flet as ft
import polars as pl
import re
from src.core.db_manager import DBManager
from src.core.mapeos import obtener_color_ingresos
from src.core.logger import app_logger
from src.utils.data_loader import DataLoader
from src.ui.components.base_grafico import BaseGrafico, TEMA_INGRESOS

class GraficoIngresos(BaseGrafico):
    def __init__(self, banco="TODOS", mes=None, on_nivel_change=None):
        super().__init__(on_nivel_change=on_nivel_change, banco=banco, mes=mes)
        self.datos_general = {}
        self.datos_bancos = {}
        self.datos_caja = {}
        self.extraer_datos_grafico()
        self.actualizar_dona_ui()

    def _get_tema_colores(self):
        return TEMA_INGRESOS

    def _obtener_color(self, label, idx):
        return obtener_color_ingresos(label, self.nivel_dona)

    def _get_datos_nivel(self):
        if self.nivel_dona == "GENERAL":
            return self.datos_general
        elif self.nivel_dona == "BANCOS":
            return self.datos_bancos
        elif self.nivel_dona == "CAJA":
            return dict(sorted(self.datos_caja.items(), key=lambda x: x[1], reverse=True))
        return {}

    def _get_titulo_para_nivel(self):
        if self.nivel_dona == "GENERAL":
            return "Ingresos (Bancos vs Caja)"
        elif self.nivel_dona == "BANCOS":
            return "Detalle Ingresos Bancarios"
        elif self.nivel_dona == "CAJA":
            return "Detalle Ingresos por Cajas"
        return self.nivel_dona.replace("_", " ").title()

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

    def actualizar_dona_ui(self):
        datos = self._get_datos_nivel()
        if not datos or all(v == 0 for v in datos.values()):
            self.dona_grafico.sections = []
            self.leyenda_contenedor.controls = [
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.icons.INFO_OUTLINE, size=30, color=ft.colors.GREY_400),
                        ft.Text("No hay datos para esta selección", size=14, color=ft.colors.GREY_500, weight=ft.FontWeight.W_500),
                    ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    alignment=ft.alignment.center, expand=True, height=200
                )
            ]
            self.tabla_detalle.rows = [
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text("—", size=11, color=ft.colors.GREY_400)),
                    ft.DataCell(ft.Text("—", size=11, color=ft.colors.GREY_400)),
                    ft.DataCell(ft.Text("—", size=11, color=ft.colors.GREY_400)),
                ])
            ]
            self.texto_hover.value = "Sin datos disponibles"
            self.texto_hover.color = ft.colors.GREY_400
            self.titulo_grafico.value = self._get_titulo_para_nivel()
            self.boton_volver.visible = self.nivel_dona != "GENERAL"
            self.update_safe()
            return

        secciones = []
        leyenda_items = []
        filas_tabla = []
        self.datos_hover = []

        total = sum(datos.values()) if sum(datos.values()) > 0 else 1

        for i, (label, valor) in enumerate(datos.items()):
            color = self._obtener_color(label, i)
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
            tema = self._get_tema_colores()
            leyenda_items.append(
                ft.Container(
                    content=ft.Row([
                        ft.Container(width=10, height=10, border_radius=5, bgcolor=color),
                        ft.Column([
                            ft.Text(label + (" (Clic aquí)" if es_clicable else ""), size=11, weight=ft.FontWeight.BOLD, color=tema["primary"]),
                            ft.Text(f"$ {valor:,.2f}", size=11, color=ft.colors.GREY_600)
                        ], spacing=1, expand=True)
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    on_click=crear_evento(label) if es_clicable else None,
                    padding=5, border_radius=5, height=45
                )
            )

            filas_tabla.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(label, size=11, color=tema["primary"])),
                    ft.DataCell(ft.Text(f"{pct:.1f}%", size=11, color=ft.colors.GREY_700)),
                    ft.DataCell(ft.Text(f"$ {valor:,.2f}", size=11, color=tema["accent"], weight=ft.FontWeight.BOLD)),
                ])
            )

        filas_tabla.append(
            ft.DataRow(cells=[
                ft.DataCell(ft.Text("TOTAL", size=11, weight=ft.FontWeight.W_900, color=tema["primary"])),
                ft.DataCell(ft.Text("100%", size=11, weight=ft.FontWeight.W_900, color=tema["primary"])),
                ft.DataCell(ft.Text(f"$ {total:,.2f}", size=11, weight=ft.FontWeight.W_900, color=tema["accent_900"])),
            ])
        )

        self.dona_grafico.sections = secciones
        self.leyenda_contenedor.controls = leyenda_items
        self.tabla_detalle.rows = filas_tabla
        self.titulo_grafico.value = self._get_titulo_para_nivel()
        self.boton_volver.visible = self.nivel_dona != "GENERAL"

        if self.on_nivel_change:
            self.on_nivel_change(self.nivel_dona)

        self.update_safe()

    def extraer_datos_grafico(self, movimientos=None):
        try:
            movs = movimientos if movimientos is not None else DBManager().get_movimientos(mes=self.mes)
            if not movs:
                return
            df = pl.DataFrame(movs)
            df = df.filter(
                (pl.col("ingreso") > 0) &
                (~pl.col("categoria_flujo").is_in(["Traslado_Salida"])) &
                (~pl.col("concepto").fill_null("").str.to_uppercase().str.contains("APORTE"))
            )

            if self.banco and self.banco != "TODOS":
                df = df.filter(pl.col("origen").str.to_uppercase() == self.banco)
            if self.mes:
                df = df.filter(pl.col("fecha").str.starts_with(self.mes))

            if df.is_empty():
                return

            df_bancos = df.filter(pl.col("origen").str.to_uppercase() != "CAJA")
            df_caja = df.filter(pl.col("origen").str.to_uppercase() == "CAJA")

            total_bancos = df_bancos["ingreso"].sum()
            total_caja = df_caja["ingreso"].sum()
            self.datos_general = {"Bancos": total_bancos, "Caja": total_caja}

            self.datos_bancos = {
                str(row["origen"]).capitalize(): row["ingreso"]
                for row in df_bancos.group_by("origen").agg(pl.col("ingreso").sum()).iter_rows(named=True)
                if row["ingreso"] > 0
            }

            df_raw = pl.DataFrame(movs)
            if self.mes:
                df_raw = df_raw.filter(pl.col("fecha").str.starts_with(self.mes))
            df_traslados = df_raw.filter(
                pl.col("origen").str.to_uppercase().is_in(["CAJA", "ALIANZA"]) &
                (pl.col("categoria_flujo") == "Traslado_Salida")
            )
            traslados_caja = df_traslados.filter(
                pl.col("origen").str.to_uppercase() == "CAJA"
            )["egreso"].sum()
            traslados_alianza_ban = df_traslados.filter(
                (pl.col("origen").str.to_uppercase() == "ALIANZA") &
                (~pl.col("concepto").fill_null("").str.to_uppercase().str.contains("OCCIDENTE"))
            )["egreso"].sum()
            traslados_alianza_occ = df_traslados.filter(
                (pl.col("origen").str.to_uppercase() == "ALIANZA") &
                (pl.col("concepto").fill_null("").str.to_uppercase().str.contains("OCCIDENTE"))
            )["egreso"].sum()
            traslados_a_bancolombia = traslados_caja + traslados_alianza_ban

            if "Bancolombia" in self.datos_bancos and traslados_a_bancolombia > 0:
                self.datos_bancos["Bancolombia"] -= traslados_a_bancolombia

            if "Occidente" in self.datos_bancos and traslados_alianza_occ > 0:
                self.datos_bancos["Occidente"] -= traslados_alianza_occ

            total_otros = sum(v for k, v in self.datos_bancos.items() if k.lower() != "alianza")
            ingreso_bancos_total = sum(self.datos_bancos.values())
            ingreso_real_alianza = ingreso_bancos_total - total_otros
            if "Alianza" in self.datos_bancos:
                self.datos_bancos["Alianza"] = ingreso_real_alianza

            total_bancos = sum(self.datos_bancos.values())
            self.datos_general["Bancos"] = total_bancos

            mapeo_cajas, _ = DataLoader.load_mapeos_caja()

            don_diego = df_caja.filter(pl.col("categoria_flujo") == "Ajuste_Don_Diego")

            self.datos_caja = {}
            for row in df_caja.group_by("centro_costos").agg(pl.col("ingreso").sum()).iter_rows(named=True):
                if row["ingreso"] > 0:
                    codigo = str(row["centro_costos"])
                    match = re.search(r"(\d{5})", codigo)
                    cod_clean = match.group(1) if match else codigo
                    nombre = mapeo_cajas.get(cod_clean, codigo.title())
                    self.datos_caja[nombre] = self.datos_caja.get(nombre, 0) + row["ingreso"]

            app_logger.debug(f"DONA INGRESOS - banco={self.banco} mes={self.mes} nivel={self.nivel_dona}")
        except:
            import traceback
            traceback.print_exc()
