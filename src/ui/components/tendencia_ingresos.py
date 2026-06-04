# ui/components/tendencia_ingresos.py
import flet as ft
import polars as pl
from src.core.db_manager import DBManager
from src.core.mapeos import MAPEO_CAJAS_TITULO, obtener_color_ingresos
from src.core.logger import app_logger
from src.ui.components.base_tendencia import BaseTendencia, TEMA_TENDENCIA_INGRESOS

class TendenciaIngresos(BaseTendencia):
    def __init__(self, banco="TODOS", mes=None):
        super().__init__(banco=banco, mes=mes)
        self.titulo.value = "Tendencia de ingresos diarios"
        self.card_total.content.controls[0].value = "Total Ingresos"
        self.card_promedio.content.controls[0].value = "Promedio diario"
        self.card_maximo.content.controls[0].value = "Máximo diario"
        self.card_mayor.content.controls[0].value = "Mayor concepto"
        self.total_neto_ingresos = 0
        self._movs_raw = None

    def _get_tema_tendencia(self):
        return TEMA_TENDENCIA_INGRESOS

    def _get_nombre_columna(self):
        return "Ingreso"

    def get_color_ft(self, idx: int, cat: str):
        return obtener_color_ingresos(cat, self.nivel_actual)

    def set_nivel(self, nuevo_nivel: str):
        self.nivel_actual = nuevo_nivel
        self.extraer_datos()
        self.dibujar_grafico(self.dropdown_dias.value)
        self.update_safe()

    def _actualizar_metricas(self):
        try:
            if not self.datos_diarios:
                return
            totales_dias = [d["total"] for d in self.datos_diarios.values() if d["total"] > 0]
            if not totales_dias:
                return

            total_mostrar = getattr(self, 'total_neto_ingresos', sum(totales_dias))
            promedio = sum(totales_dias) / len(totales_dias)
            maximo = max(totales_dias)

            if self.nivel_actual == "GENERAL":
                total_bancos = sum(d["valores"].get("Bancos", 0) for d in self.datos_diarios.values())
                total_caja = sum(d["valores"].get("Caja", 0) for d in self.datos_diarios.values())
                mayor_nombre = "Bancos" if total_bancos > total_caja else "Caja"
            else:
                mayor_nombre = self.nivel_actual.capitalize()

            self.card_total.data.value = f"$ {total_mostrar:,.2f}"
            self.card_promedio.data.value = f"$ {promedio:,.2f}"
            self.card_maximo.data.value = f"$ {maximo:,.2f}"
            self.card_mayor.data.value = mayor_nombre
        except:
            pass

    def extraer_datos(self, movimientos=None):
        try:
            movs = movimientos if movimientos is not None else DBManager().get_movimientos(mes=self.mes)
            if not movs:
                return
            self._movs_raw = movs
            df = pl.DataFrame(movs)
            if df.is_empty():
                return

            df = df.filter(
                (pl.col("ingreso") > 0) &
                (~pl.col("categoria_flujo").is_in(["Traslado_Salida"])) &
                (~pl.col("concepto").fill_null("").str.to_uppercase().str.contains("APORTE"))
            )
            if df.is_empty():
                return

            if self.banco and self.banco != "TODOS":
                df = df.filter(pl.col("origen").str.to_uppercase() == self.banco)
            if self.mes:
                df = df.filter(pl.col("fecha").str.starts_with(self.mes))

            df = df.with_columns(pl.col("fecha").str.to_date("%Y-%m-%d"))

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
                df = df.with_columns(
                    pl.col("centro_costos").fill_null("").alias("CCO_Clean"),
                    pl.lit("Desconocido").alias("Categoria")
                )
                df = df.with_columns(
                    pl.col("CCO_Clean").str.extract(r"(\d{5})", 1)
                    .fill_null(pl.col("centro_costos"))
                    .replace_strict(MAPEO_CAJAS_TITULO, default=pl.col("centro_costos")).alias("Categoria")
                )

            if df.is_empty():
                return

            agrupado = df.group_by(["Dia", "Dia_Semana", "Categoria"]).agg(pl.col("ingreso").sum().alias("Ingreso"))
            self._agrupado_cache = agrupado
            totales_cat = agrupado.group_by("Categoria").agg(pl.col("Ingreso").sum()).sort("Ingreso", descending=True)
            self.categorias_activas = totales_cat["Categoria"].to_list()

            if self.nivel_actual in ("BANCOS", "CAJA"):
                self.todas_categorias = self.categorias_activas.copy()
                activas = self.categorias_activadas if self.categorias_activadas else self.todas_categorias[:self.max_categorias]
                self.categorias_activas = [c for c in self.todas_categorias if c in activas][:self.max_categorias]
                self.dropdown_categorias.options = [ft.dropdown.Option("TOP", f"Top {self.max_categorias} mayores")] + [
                    ft.dropdown.Option(c, ("✓ " if c in self.categorias_activas else "") + c) for c in self.todas_categorias
                ]
                self.dropdown_categorias.value = "TOP" if self.categorias_activadas is None else "TOP"
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
                    cat: float(subset.filter(pl.col("Categoria") == cat)["Ingreso"].sum() or 0.0)
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
            self._construir_ui()

            df_raw_net = pl.DataFrame(self._movs_raw)
            if self.mes:
                df_raw_net = df_raw_net.filter(pl.col("fecha").str.starts_with(self.mes))
            df_tras = df_raw_net.filter(
                pl.col("origen").str.to_uppercase().is_in(["CAJA", "ALIANZA"]) &
                (pl.col("categoria_flujo") == "Traslado_Salida")
            )
            traslados_caja = df_tras.filter(
                pl.col("origen").str.to_uppercase() == "CAJA"
            )["egreso"].sum()
            traslados_alianza_ban = df_tras.filter(
                (pl.col("origen").str.to_uppercase() == "ALIANZA") &
                (~pl.col("concepto").fill_null("").str.to_uppercase().str.contains("OCCIDENTE"))
            )["egreso"].sum()
            traslados_alianza_occ = df_tras.filter(
                (pl.col("origen").str.to_uppercase() == "ALIANZA") &
                (pl.col("concepto").fill_null("").str.to_uppercase().str.contains("OCCIDENTE"))
            )["egreso"].sum()

            if self.nivel_actual == "GENERAL":
                total_bancos_raw = sum(d["valores"].get("Bancos", 0) for d in self.datos_diarios.values())
                total_caja = sum(d["valores"].get("Caja", 0) for d in self.datos_diarios.values())
                if not self.banco or self.banco == "TODOS":
                    total_bancos_neto = total_bancos_raw - traslados_caja - traslados_alianza_ban - traslados_alianza_occ
                else:
                    banco_up = self.banco.upper()
                    if banco_up == "BANCOLOMBIA":
                        neteo_banco = traslados_caja + traslados_alianza_ban
                    elif banco_up == "OCCIDENTE":
                        neteo_banco = traslados_alianza_occ
                    elif banco_up == "ALIANZA":
                        neteo_banco = traslados_caja + traslados_alianza_ban + traslados_alianza_occ
                    else:
                        neteo_banco = 0
                    total_bancos_neto = total_bancos_raw - neteo_banco
                self.total_neto_ingresos = total_bancos_neto + total_caja
                total_raw = total_bancos_raw + total_caja
                if total_raw > 0 and self.total_neto_ingresos != total_raw:
                    factor = self.total_neto_ingresos / total_raw
                    for d in self.datos_diarios:
                        for cat in self.datos_diarios[d]["valores"]:
                            self.datos_diarios[d]["valores"][cat] *= factor
                        self.datos_diarios[d]["total"] = sum(self.datos_diarios[d]["valores"].values())
            else:
                total_raw = sum(d["total"] for d in self.datos_diarios.values())
                neteo_don_diego = 0
                if self.nivel_actual in ("BANCOS", "CAJA"):
                    if self.nivel_actual == "BANCOS" and (not self.banco or self.banco == "TODOS"):
                        neteo_don_diego = traslados_caja + traslados_alianza_ban + traslados_alianza_occ
                    elif self.banco:
                        banco_up = self.banco.upper()
                        if banco_up == "BANCOLOMBIA":
                            neteo_don_diego = traslados_caja + traslados_alianza_ban
                        elif banco_up == "OCCIDENTE":
                            neteo_don_diego = traslados_alianza_occ
                        elif banco_up == "ALIANZA":
                            neteo_don_diego = traslados_caja + traslados_alianza_ban + traslados_alianza_occ
                self.total_neto_ingresos = total_raw - neteo_don_diego
                if total_raw > 0 and neteo_don_diego > 0:
                    factor = self.total_neto_ingresos / total_raw
                    for d in self.datos_diarios:
                        for cat in self.datos_diarios[d]["valores"]:
                            self.datos_diarios[d]["valores"][cat] *= factor
                        self.datos_diarios[d]["total"] = sum(self.datos_diarios[d]["valores"].values())
                app_logger.info(f"TD {self.nivel_actual}: raw={total_raw:,.0f} neteo={neteo_don_diego:,.0f} final={self.total_neto_ingresos:,.0f}")

            self._actualizar_metricas()
            self._construir_leyenda()
        except:
            import traceback
            traceback.print_exc()
