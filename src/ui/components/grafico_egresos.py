# src/ui/components/grafico_egresos.py
import flet as ft
import json
import polars as pl
import re
import os
import pandas as pd
from src.core.db_manager import DBManager
from src.core.mapeos import obtener_color, obtener_color_proveedor
from src.data_engine.transformers.rules_caja import procesar_datos_grafico_egresos
from src.utils.data_loader import DataLoader
from src.core.logger import app_logger
from src.ui.components.base_grafico import BaseGrafico, TEMA_EGRESOS

class GraficoEgresos(BaseGrafico):
    def __init__(self, banco="TODOS", mes=None, on_nivel_change=None, on_modo_change=None):
        self.on_modo_change = on_modo_change
        self.modo_vista = "ENTIDADES"
        self.caja_seleccionada = None
        self.datos_gen_entidades = {}
        self.datos_ban_entidades = {}
        self.datos_caj_entidades = {}
        self.datos_caj_categorias = {}
        self.datos_caj_prov_detalle = {}
        self.datos_caj_gas_detalle = {}
        self.datos_caj_nom_detalle = {}
        super().__init__(on_nivel_change=on_nivel_change, banco=banco, mes=mes)

    def _get_tema_colores(self):
        return TEMA_EGRESOS

    def _obtener_color(self, label, idx):
        if self.nivel_dona in ["CATEGORIAS_CAJA", "PROVEEDORES_CAJA", "GASTOS_CAJA", "NOMINA_CAJA"]:
            return obtener_color_proveedor(label, idx)
        return obtener_color(label, modo="ENTIDADES", nivel=self.nivel_dona)

    def _build_extra_ui(self):
        tema = self._get_tema_colores()
        self.btn_entidades = ft.TextButton("Entidades", on_click=lambda e: self.volver_inicio())
        self.contenedor_tabs = ft.Row([self.btn_entidades], spacing=0)

    def _build_top_row_extra(self):
        return self.contenedor_tabs

    def _get_datos_nivel(self):
        caja_key = self.caja_seleccionada or ""
        if self.nivel_dona == "GENERAL":
            return self.datos_gen_entidades
        elif self.nivel_dona == "BANCOS":
            return self.datos_ban_entidades
        elif self.nivel_dona == "CAJA":
            return self.datos_caj_entidades
        elif self.nivel_dona == "CATEGORIAS_CAJA":
            return self.datos_caj_categorias.get(caja_key, {})
        elif self.nivel_dona == "PROVEEDORES_CAJA":
            return self.datos_caj_prov_detalle.get(caja_key, {})
        elif self.nivel_dona == "GASTOS_CAJA":
            return self.datos_caj_gas_detalle.get(caja_key, {})
        elif self.nivel_dona == "NOMINA_CAJA":
            return self.datos_caj_nom_detalle.get(caja_key, {})
        return {}

    def _get_titulo_para_nivel(self):
        caja = self.caja_seleccionada or ""
        if self.nivel_dona == "GENERAL":
            return "Salidas (Bancos vs Caja)"
        elif self.nivel_dona == "BANCOS":
            return "Detalle Salidas Bancarias"
        elif self.nivel_dona == "CAJA":
            return "Detalle Salidas por Cajas"
        elif self.nivel_dona == "CATEGORIAS_CAJA":
            return f"Egresos {caja.title()}" if caja else "Categorías de Caja"
        elif self.nivel_dona == "PROVEEDORES_CAJA":
            return f"Proveedores {caja.title()}" if caja else "Proveedores"
        elif self.nivel_dona == "GASTOS_CAJA":
            return f"Gastos {caja.title()}" if caja else "Gastos"
        elif self.nivel_dona == "NOMINA_CAJA":
            return f"Nómina {caja.title()}" if caja else "Nómina"
        return self.nivel_dona.replace("_", " ").title()

    def actualizar_dona_ui(self):
        datos = self._get_datos_nivel()
        tema = self._get_tema_colores()
        self.btn_entidades.style = ft.ButtonStyle(bgcolor=tema["primary_50"], color=tema["primary"])
        es_clicable = self.nivel_dona in ("GENERAL", "CAJA", "CATEGORIAS_CAJA")

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

        datos = {k: v for k, v in datos.items() if v > 0}
        datos = dict(sorted(datos.items(), key=lambda x: x[1], reverse=True))

        secciones, leyenda_items, filas_tabla = [], [], []
        self.datos_hover = []
        total = sum(datos.values()) if sum(datos.values()) > 0 else 1

        for i, (label, valor) in enumerate(datos.items()):
            color = self._obtener_color(label, i)
            pct = (valor / total) * 100
            secciones.append(ft.PieChartSection(value=valor, color=color, radius=55, title=f"{pct:.0f}%" if pct >= 4 else "",
                                                title_style=ft.TextStyle(size=11, color=ft.colors.WHITE, weight=ft.FontWeight.BOLD)))
            self.datos_hover.append({"label": label.title(), "valor": valor, "pct": pct, "color": color})

            def crear_evento(cat_label):
                def on_click(e):
                    if self.nivel_dona == "GENERAL":
                        self.nivel_dona = cat_label.upper()
                    elif self.nivel_dona == "CAJA":
                        self.nivel_dona = "CATEGORIAS_CAJA"
                        self.caja_seleccionada = cat_label.upper()
                    elif self.nivel_dona == "CATEGORIAS_CAJA":
                        cl = cat_label.upper().replace("Ó", "O")
                        if cl == "PROVEEDORES":
                            self.nivel_dona = "PROVEEDORES_CAJA"
                        elif cl in ("GASTOS OPERACIONALES", "GASTOS"):
                            self.nivel_dona = "GASTOS_CAJA"
                        elif cl in ("NÓMINA", "NOMINA"):
                            self.nivel_dona = "NOMINA_CAJA"
                    self.actualizar_dona_ui()
                return on_click

            nombre_mostrar = label.title()
            puede_click = es_clicable and label.upper() not in ["OTROS EGRESOS"]
            leyenda_items.append(
                ft.Container(
                    content=ft.Row([
                        ft.Container(width=10, height=10, border_radius=5, bgcolor=color),
                        ft.Column([
                            ft.Text(nombre_mostrar + (" (Clic aquí)" if puede_click else ""),
                                    size=11, weight=ft.FontWeight.BOLD, color=tema["primary"]),
                            ft.Text(f"$ {valor:,.2f}", size=11, color=ft.colors.GREY_600)
                        ], spacing=1, expand=True)
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    on_click=crear_evento(label) if puede_click else None,
                    padding=5, border_radius=5
                )
            )

            filas_tabla.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(nombre_mostrar[:25] + "..." if len(nombre_mostrar) > 25 else nombre_mostrar, size=11, color=tema["primary"])),
                ft.DataCell(ft.Text(f"{pct:.1f}%", size=11, color=ft.colors.GREY_700)),
                ft.DataCell(ft.Text(f"$ {valor:,.2f}", size=11, color=tema["accent"], weight=ft.FontWeight.BOLD)),
            ]))

        filas_tabla.append(ft.DataRow(cells=[
            ft.DataCell(ft.Text("TOTAL", size=11, weight=ft.FontWeight.W_900, color=tema["primary"])),
            ft.DataCell(ft.Text("100%", size=11, weight=ft.FontWeight.W_900, color=tema["primary"])),
            ft.DataCell(ft.Text(f"$ {total:,.2f}", size=11, weight=ft.FontWeight.W_900, color=tema["accent_900"])),
        ]))

        self.dona_grafico.sections = secciones
        self.leyenda_contenedor.controls = leyenda_items
        self.tabla_detalle.rows = filas_tabla
        self.titulo_grafico.value = self._get_titulo_para_nivel()
        self.boton_volver.visible = self.nivel_dona != "GENERAL"

        if self.on_nivel_change:
            estado_tendencia = "DETALLE_CAJA" if self.nivel_dona == "CATEGORIAS_CAJA" else self.nivel_dona
            self.on_nivel_change(estado_tendencia, self.caja_seleccionada)

        self.update_safe()

    def volver_inicio(self):
        self.nivel_dona = "GENERAL"
        self.caja_seleccionada = None
        self.actualizar_dona_ui()
        if self.on_nivel_change:
            self.on_nivel_change("GENERAL", None)

    def volver_dona(self, e):
        if self.nivel_dona in ["BANCOS", "CAJA"]:
            self.nivel_dona = "GENERAL"
            self.caja_seleccionada = None
        elif self.nivel_dona == "CATEGORIAS_CAJA":
            self.nivel_dona = "CAJA"
            self.caja_seleccionada = None
        elif self.nivel_dona in ["PROVEEDORES_CAJA", "GASTOS_CAJA", "NOMINA_CAJA"]:
            self.nivel_dona = "CATEGORIAS_CAJA"
        self.actualizar_dona_ui()

    def _cargar_desde_bd(self, movs=None, movimientos_externos=None):
        try:
            if movs is None:
                movs = movimientos_externos if movimientos_externos is not None else DBManager().get_movimientos()
            if not movs:
                return
            df = pl.DataFrame(movs)
            df = df.filter(
                (pl.col("egreso") > 0) &
                (~pl.col("categoria_flujo").is_in(["Traslado_Salida", "Traslado_Entrada", "Anulacion"])) &
                (~pl.col("concepto").fill_null("").str.to_uppercase().str.contains("APORTE"))
            )
            if df.is_empty():
                return

            if self.mes:
                df = df.filter(pl.col("fecha").str.starts_with(self.mes))

            df_bancos = df.filter(pl.col("origen").str.to_uppercase() != "CAJA")
            df_caja = df.filter(pl.col("origen").str.to_uppercase() == "CAJA")

            self.datos_gen_entidades = {
                "Bancos": df_bancos["egreso"].sum(),
                "CAJA": df_caja["egreso"].sum()
            }

            self.datos_ban_entidades = {
                str(row["origen"]).capitalize(): row["egreso"]
                for row in df_bancos.group_by("origen").agg(pl.col("egreso").sum()).iter_rows(named=True)
                if row["egreso"] > 0
            }

            self.datos_caj_entidades = {}
            mapeo_cajas, _ = DataLoader.load_mapeos_caja()
            for row in df_caja.group_by("centro_costos").agg(pl.col("egreso").sum()).iter_rows(named=True):
                if row["egreso"] > 0:
                    codigo = str(row["centro_costos"])
                    match = re.search(r"(\d{5})", codigo)
                    cod_clean = match.group(1) if match else codigo
                    nombre = mapeo_cajas.get(cod_clean, codigo.upper()).upper()
                    self.datos_caj_entidades[nombre] = self.datos_caj_entidades.get(nombre, 0) + row["egreso"]

            don_diego = pl.DataFrame(movs)
            if self.mes:
                don_diego = don_diego.filter(pl.col("fecha").str.starts_with(self.mes))
            don_diego = don_diego.filter(
                (pl.col("origen").str.to_uppercase() == "CAJA") &
                (pl.col("categoria_flujo") == "Ajuste_Don_Diego")
            )["ingreso"].sum()

            if don_diego > 0:
                self.datos_gen_entidades["CAJA"] -= don_diego
                if "CAJA POPAYAN PPAL" in self.datos_caj_entidades:
                    self.datos_caj_entidades["CAJA POPAYAN PPAL"] -= don_diego
                    if self.datos_caj_entidades["CAJA POPAYAN PPAL"] < 0:
                        self.datos_caj_entidades["CAJA POPAYAN PPAL"] = 0.0
        except:
            import traceback
            traceback.print_exc()

    def cargar_y_construir(self, movimientos=None):
        datos_excel = procesar_datos_grafico_egresos(solo_excel=True)

        self.datos_caj_categorias = {str(k).upper(): v for k, v in datos_excel.get("datos_caj_categorias", {}).items()}
        self.datos_caj_prov_detalle = {str(k).upper(): v for k, v in datos_excel.get("datos_caj_prov_detalle", {}).items()}
        self.datos_caj_gas_detalle = {str(k).upper(): v for k, v in datos_excel.get("datos_caj_gas_detalle", {}).items()}
        self.datos_caj_nom_detalle = {str(k).upper(): v for k, v in datos_excel.get("datos_caj_nom_detalle", {}).items()}

        try:
            movs = movimientos if movimientos is not None else DBManager().get_movimientos(mes=self.mes)
            if movs:
                df = pl.DataFrame(movs)
                if self.mes:
                    df = df.filter(pl.col("fecha").str.starts_with(self.mes))
                df_caja = df.filter(pl.col("origen").str.to_uppercase() == "CAJA")
                mapeo_cajas, _ = DataLoader.load_mapeos_caja()

                df_prov = df_caja.filter(
                    pl.col("documento_referencia").str.starts_with("EB") &
                    (pl.col("egreso") > 0)
                )
                if not df_prov.is_empty():
                    for row in df_prov.iter_rows(named=True):
                        codigo = str(row["centro_costos"])
                        match = re.search(r"(\d{5})", codigo)
                        cod_clean = match.group(1) if match else codigo
                        caja = mapeo_cajas.get(cod_clean, codigo.upper()).upper()
                        tercero = str(row["tercero"]).strip().title()
                        valor = float(row["egreso"] or 0)
                        if caja not in self.datos_caj_categorias:
                            self.datos_caj_categorias[caja] = {"Proveedores": 0.0, "Gastos Operacionales": 0.0, "Nómina": 0.0}
                        if caja not in self.datos_caj_prov_detalle:
                            self.datos_caj_prov_detalle[caja] = {}
                        self.datos_caj_categorias[caja]["Proveedores"] += valor
                        self.datos_caj_prov_detalle[caja][tercero] = self.datos_caj_prov_detalle[caja].get(tercero, 0.0) + valor

                if self.mes:
                    db = DBManager()
                    gastos_bd = db.get_aux_gastos(self.mes)
                    keys_gastos = set()
                    for g in gastos_bd:
                        key = str(g.get("tipo_doc", "")) + str(g.get("num_doc", ""))
                        if key:
                            keys_gastos.add(key)
                    app_logger.info(f"GASTOS BD keys: total: {len(keys_gastos)}")
                    if keys_gastos:
                        df_caja_keys = df_caja.with_columns(
                            (pl.col("documento_referencia").fill_null("").cast(pl.Utf8) +
                             pl.col("numero_doc").fill_null("").cast(pl.Utf8).str.replace(r"\.0$", ""))
                            .alias("_key")
                        )
                        df_gas = df_caja_keys.filter(
                            pl.col("_key").is_in(keys_gastos) &
                            (pl.col("egreso") > 0)
                        )
                        if not df_gas.is_empty():
                            for row in df_gas.iter_rows(named=True):
                                codigo = str(row["centro_costos"])
                                match = re.search(r"(\d{5})", codigo)
                                cod_clean = match.group(1) if match else codigo
                                caja = mapeo_cajas.get(cod_clean, codigo.upper()).upper()
                                concepto = str(row["concepto"]).strip().title()[:30]
                                valor = float(row["egreso"] or 0)
                                if caja not in self.datos_caj_categorias:
                                    self.datos_caj_categorias[caja] = {"Proveedores": 0.0, "Gastos Operacionales": 0.0, "Nómina": 0.0}
                                if caja not in self.datos_caj_gas_detalle:
                                    self.datos_caj_gas_detalle[caja] = {}
                                self.datos_caj_categorias[caja]["Gastos Operacionales"] += valor
                                self.datos_caj_gas_detalle[caja][concepto] = self.datos_caj_gas_detalle[caja].get(concepto, 0.0) + valor
        except:
            import traceback
            traceback.print_exc()

        if self.mes:
            try:
                nomina_bd = DBManager().get_nomina_por_caja(self.mes)
                for r in nomina_bd:
                    c = r["caja"]
                    v = r["valor"]
                    if c not in self.datos_caj_categorias:
                        self.datos_caj_categorias[c] = {"Proveedores": 0.0, "Gastos Operacionales": 0.0, "Nómina": 0.0}
                    self.datos_caj_categorias[c]["Nómina"] = self.datos_caj_categorias[c].get("Nómina", 0.0) + v
                    if c not in self.datos_caj_nom_detalle:
                        self.datos_caj_nom_detalle[c] = {}
                    empleado = str(r.get('empleado', 'EMPLEADO')).strip().title()
                    self.datos_caj_nom_detalle[c][empleado] = self.datos_caj_nom_detalle[c].get(empleado, 0.0) + v
            except:
                import traceback
                traceback.print_exc()

        self._cargar_desde_bd(movimientos_externos=movimientos)

        for c, v_total in self.datos_caj_entidades.items():
            if c not in self.datos_caj_categorias:
                self.datos_caj_categorias[c] = {"Proveedores": 0.0, "Gastos Operacionales": 0.0, "Nómina": 0.0, "Otros Egresos": v_total}
            else:
                suma = (self.datos_caj_categorias[c].get("Proveedores", 0.0) +
                        self.datos_caj_categorias[c].get("Gastos Operacionales", 0.0) +
                        self.datos_caj_categorias[c].get("Nómina", 0.0))
                diff = v_total - suma
                if diff > 1000:
                    self.datos_caj_categorias[c]["Otros Egresos"] = diff

        if self.banco and self.banco != "TODOS":
            banco_key = self.banco.capitalize()
            if banco_key in self.datos_ban_entidades:
                self.datos_ban_entidades = {banco_key: self.datos_ban_entidades[banco_key]}
                self.datos_gen_entidades["Bancos"] = self.datos_ban_entidades[banco_key]
            else:
                self.datos_ban_entidades = {}
                self.datos_gen_entidades["Bancos"] = 0

        self.construir_ui()
        self.actualizar_dona_ui()
