# src/ui/components/tendencia_egresos.py
import flet as ft
import polars as pl
from src.core.db_manager import DBManager
from src.core.mapeos import MAPEO_CAJAS_TITULO, obtener_color, obtener_color_proveedor
from src.utils.data_loader import DataLoader
from src.core.logger import app_logger
from src.ui.components.base_tendencia import BaseTendencia, TEMA_TENDENCIA_EGRESOS

class TendenciaEgresos(BaseTendencia):
    def __init__(self, banco="TODOS", mes=None):
        super().__init__(banco=banco, mes=mes)
        self.titulo.value = "Tendencia de salidas diarias"
        self.card_total.content.controls[0].value = "Total Salidas"
        self.card_promedio.content.controls[0].value = "Promedio diario"
        self.card_maximo.content.controls[0].value = "Salida máxima"
        self.card_mayor.content.controls[0].value = "Líder del rubro"
        self.caja_seleccionada = None
        self.ajuste_don_diego = 0
        self._movs_cache = None

    def _get_tema_tendencia(self):
        return TEMA_TENDENCIA_EGRESOS

    def _get_nombre_columna(self):
        return "Egreso"

    def get_color_ft(self, idx: int, cat: str = ""):
        if cat == "Otros Egresos" or cat == "Otras Cajas":
            return ft.colors.GREY_500
        if self.nivel_actual == "DETALLE_CAJA":
            return obtener_color_proveedor(cat, idx)
        return obtener_color(cat, modo="ENTIDADES", nivel=self.nivel_actual)

    def set_modo(self, modo: str):
        self.nivel_actual = "GENERAL"
        self.caja_seleccionada = None
        self.cargar_datos_y_dibujar()
        self.update_safe()

    def set_nivel(self, nuevo_nivel: str, caja_sel: str = None):
        self.nivel_actual = nuevo_nivel
        self.caja_seleccionada = caja_sel
        self.cargar_datos_y_dibujar(movimientos=self._movs_cache)
        self.update_safe()

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
        except:
            pass

    def _aplicar_ajuste_don_diego(self):
        if self.ajuste_don_diego <= 0 or not self.datos_diarios:
            return

        if self.nivel_actual == "GENERAL":
            caja_total = sum(d["valores"].get("Caja", 0) for d in self.datos_diarios.values())
            if caja_total > 0:
                for d in self.datos_diarios:
                    if "Caja" in self.datos_diarios[d]["valores"]:
                        proporcion = self.datos_diarios[d]["valores"]["Caja"] / caja_total
                        self.datos_diarios[d]["valores"]["Caja"] = max(
                            0, self.datos_diarios[d]["valores"]["Caja"] - self.ajuste_don_diego * proporcion
                        )
                    self.datos_diarios[d]["total"] = sum(self.datos_diarios[d]["valores"].values())

        elif self.nivel_actual == "CAJA":
            popayan = next((c for c in self.categorias_activas if "POPAYAN" in c.upper()), None)
            if popayan:
                popayan_total = sum(d["valores"].get(popayan, 0) for d in self.datos_diarios.values())
                if popayan_total > 0:
                    for d in self.datos_diarios:
                        if popayan in self.datos_diarios[d]["valores"]:
                            proporcion = self.datos_diarios[d]["valores"][popayan] / popayan_total
                            self.datos_diarios[d]["valores"][popayan] = max(
                                0, self.datos_diarios[d]["valores"][popayan] - self.ajuste_don_diego * proporcion
                            )
                        self.datos_diarios[d]["total"] = sum(self.datos_diarios[d]["valores"].values())

        elif self.nivel_actual in ("DETALLE_CAJA", "PROVEEDORES_CAJA", "GASTOS_CAJA", "NOMINA_CAJA"):
            if self.caja_seleccionada and "POPAYAN" in self.caja_seleccionada.upper():
                total_raw = sum(d["total"] for d in self.datos_diarios.values())
                if total_raw > 0:
                    factor = max(0, (total_raw - self.ajuste_don_diego) / total_raw)
                    for d in self.datos_diarios:
                        for cat in self.datos_diarios[d]["valores"]:
                            self.datos_diarios[d]["valores"][cat] *= factor
                        self.datos_diarios[d]["total"] = sum(self.datos_diarios[d]["valores"].values())

    def _post_rebuild_datos(self):
        self._aplicar_ajuste_don_diego()

    def cargar_datos_y_dibujar(self, movimientos=None):
        try:
            movs = movimientos if movimientos is not None else DBManager().get_movimientos(mes=self.mes)
            if not movs:
                return
            self._movs_cache = movs
            df = pl.DataFrame(movs)
            if df.is_empty():
                return

            self.ajuste_don_diego = df.filter(
                (pl.col("origen").str.to_uppercase() == "CAJA") &
                (pl.col("categoria_flujo") == "Ajuste_Don_Diego")
            )["ingreso"].sum()

            df = df.with_columns(pl.col("fecha").str.to_date("%Y-%m-%d"))
            df = df.filter(
                (pl.col("egreso") > 0) &
                (~pl.col("categoria_flujo").is_in(["Traslado_Salida", "Traslado_Entrada", "Anulacion"])) &
                (~pl.col("concepto").fill_null("").str.to_uppercase().str.contains("APORTE"))
            )

            if self.banco and self.banco != "TODOS":
                df = df.filter(pl.col("origen").str.to_uppercase() == self.banco)

            df = df.with_columns([
                pl.col("fecha").dt.day().alias("Dia"),
                (pl.col("fecha").dt.weekday() - 1).alias("Dia_Semana"),
            ])

            if self.nivel_actual == "GENERAL":
                df = df.with_columns(
                    pl.when(pl.col("origen").str.to_uppercase() == "CAJA")
                    .then(pl.lit("Caja")).otherwise(pl.lit("Bancos")).alias("Categoria")
                )
            elif self.nivel_actual == "BANCOS":
                df = df.filter(pl.col("origen").str.to_uppercase() != "CAJA")
                df = df.with_columns(pl.col("origen").str.to_titlecase().alias("Categoria"))
            elif self.nivel_actual == "CAJA":
                df = df.filter(pl.col("origen").str.to_uppercase() == "CAJA")
                cco_expr = pl.col("centro_costos").fill_null("").str.extract(r"(\d{5})", 1)
                df = df.with_columns(
                    cco_expr.fill_null(pl.col("centro_costos"))
                    .replace_strict(MAPEO_CAJAS_TITULO, default=pl.col("centro_costos")).alias("Categoria")
                )
            elif self.nivel_actual == "DETALLE_CAJA":
                mapeo_cajas, _ = DataLoader.load_mapeos_caja()
                cco_expr = pl.col("centro_costos").fill_null("").str.extract(r"(\d{5})", 1)
                df = df.with_columns(
                    cco_expr.fill_null(pl.col("centro_costos"))
                    .replace_strict(mapeo_cajas, default=pl.col("centro_costos")).str.to_uppercase().alias("caja_nombre")
                )
                caja_filtro = self.caja_seleccionada.upper() if self.caja_seleccionada else ""
                df = df.filter(
                    (pl.col("origen").str.to_uppercase() == "CAJA") &
                    (pl.col("caja_nombre") == caja_filtro)
                )
                df = df.with_columns(
                    pl.when(pl.col("documento_referencia").str.starts_with("EB"))
                      .then(pl.lit("Proveedores"))
                      .when(pl.col("categoria_flujo").str.to_uppercase() == "OPERACION_NORMAL")
                      .then(pl.lit("Gastos Operacionales"))
                      .when(pl.col("categoria_flujo").str.to_uppercase().str.contains("NOMINA"))
                      .then(pl.lit("Nómina"))
                      .otherwise(pl.lit("Otros Egresos"))
                      .alias("Categoria")
                )
            elif self.nivel_actual in ["PROVEEDORES_CAJA", "GASTOS_CAJA", "NOMINA_CAJA"]:
                mapeo_cajas, _ = DataLoader.load_mapeos_caja()
                cco_expr = pl.col("centro_costos").fill_null("").str.extract(r"(\d{5})", 1)
                df = df.with_columns(
                    cco_expr.fill_null(pl.col("centro_costos"))
                    .replace_strict(mapeo_cajas, default=pl.col("centro_costos")).str.to_uppercase().alias("caja_nombre")
                )
                caja_filtro = self.caja_seleccionada.upper() if self.caja_seleccionada else ""
                df = df.filter(
                    (pl.col("origen").str.to_uppercase() == "CAJA") &
                    (pl.col("caja_nombre") == caja_filtro)
                )
                if self.nivel_actual == "PROVEEDORES_CAJA":
                    df = df.filter(pl.col("categoria_flujo").str.to_uppercase() == "OPERACION_NORMAL")
                elif self.nivel_actual == "GASTOS_CAJA":
                    df = df.filter(pl.col("categoria_flujo").str.to_uppercase().str.contains("GASTO"))
                elif self.nivel_actual == "NOMINA_CAJA":
                    df = df.filter(pl.col("categoria_flujo").str.to_uppercase().str.contains("NOMINA"))
                df = df.with_columns(pl.col("tercero").fill_null("Desconocido").str.to_titlecase().alias("Categoria"))

            agrupado = df.group_by(["Dia", "Dia_Semana", "Categoria"]).agg(pl.col("egreso").sum().alias("Egreso"))
            self._agrupado_cache = agrupado
            totales_cat = agrupado.group_by("Categoria").agg(pl.col("Egreso").sum()).sort("Egreso", descending=True)
            self.categorias_activas = totales_cat["Categoria"].to_list()
            self.todas_categorias = self.categorias_activas.copy()

            if self.nivel_actual in ("BANCOS", "CAJA"):
                activas = self.categorias_activadas if self.categorias_activadas else self.todas_categorias[:self.max_categorias]
                self.categorias_activas = [c for c in self.todas_categorias if c in activas][:self.max_categorias]
                self.dropdown_categorias.options = [ft.dropdown.Option("TOP", f"Top {self.max_categorias} mayores")] + [
                    ft.dropdown.Option(c, ("✓ " if c in self.categorias_activas else "") + c) for c in self.todas_categorias
                ]
                self.dropdown_categorias.value = "TOP"
                label_cats = " · ".join(self.categorias_activas)
                self.dropdown_categorias.label = f"Mostrando {len(self.categorias_activas)}: {label_cats[:40]}..."
                self.dropdown_categorias.visible = True
            else:
                self.dropdown_categorias.visible = False

            dias_cortos = {0: "Lun", 1: "Mar", 2: "Mié", 3: "Jue", 4: "Vie", 5: "Sáb", 6: "Dom"}
            dias_completos = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"}

            opciones = [ft.dropdown.Option(key="ALL", text="Todo el mes")]
            self.datos_diarios = {}
            for d in sorted(agrupado["Dia"].unique().to_list()):
                subset = agrupado.filter(pl.col("Dia") == d)
                dsn = int(subset["Dia_Semana"].to_list()[0]) if not subset.is_empty() else 0
                valores_dia = {
                    cat: float(subset.filter(pl.col("Categoria") == cat)["Egreso"].sum() or 0.0)
                    for cat in self.categorias_activas
                }
                self.datos_diarios[d] = {
                    "label_corta": f"{dias_cortos.get(dsn, '')} {d}",
                    "label_larga": f"{dias_completos.get(dsn, '')} {d}",
                    "valores": valores_dia,
                    "total": sum(valores_dia.values())
                }
                opciones.append(ft.dropdown.Option(key=str(d), text=self.datos_diarios[d]["label_larga"]))

            self.dropdown_dias.options = opciones

            self._aplicar_ajuste_don_diego()

            self._construir_ui()
            self._actualizar_metricas()
            self._construir_leyenda()
            self.dibujar_grafico("ALL")
        except:
            import traceback
            traceback.print_exc()
