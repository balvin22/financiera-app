# ui/views/dashboard_view.py
import flet as ft
import os
import traceback
from src.ui.components.kpi_card import crear_tarjeta_kpi, crear_tarjeta_kpi_compuesta
from src.ui.components.grafico_ingresos import GraficoIngresos
from src.ui.components.grafico_egresos import GraficoEgresos
from src.ui.components.tendencia_ingresos import TendenciaIngresos
from src.ui.components.tendencia_egresos import TendenciaEgresos
from src.ui.views.flujo_diario_graficos import FlujoDiarioGraficos
from src.core.db_manager import DBManager
from src.utils.data_loader import DataLoader
from src.core.logger import app_logger
from src.data_engine.transformers.rules_flujo_diario import procesar_datos_flujo_diario

class DashboardView(ft.Container):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True
        self.padding = 30 
        self.bgcolor = "#F8FAFC"
        self.vista_activa = "INGRESOS"
        self.db_manager = DBManager()
        self.banco_global = "TODOS"
        self.mes_global = None
        self._movimientos_cache = None
        self._movimientos_cache_key = None
        self.vista_flujo_diario = FlujoDiarioGraficos(page)
        self.vista_flujo_diario.on_rebuild = self._reconstruir_flujo
        self.tendencia_ingresos = None
        self.ingresos_dona = None
        self.tendencia_egresos = None
        self.egresos_dona = None
        self.excluir_traslados = True
        self.excluir_anulados = True
        self._contenedor_grafico = ft.Container(expand=True)
        self._fila_kpis = ft.Row(spacing=15)
        self._filtros_row = ft.Row(vertical_alignment=ft.CrossAxisAlignment.CENTER)
        self._titulo_vista = ft.Text("", size=24, weight=ft.FontWeight.W_900, color=ft.colors.BLUE_900)
        self._ultima_actualizacion = ft.Text("", size=11, color=ft.colors.GREY_500)
        self._last_kpi_key = None
        self.build_ui()

    def _obtener_movimientos(self):
        filtro_key = (self.banco_global, self.mes_global)
        if self._movimientos_cache_key == filtro_key and self._movimientos_cache is not None:
            return self._movimientos_cache
        movs = DBManager().get_movimientos(mes=self.mes_global)
        self._movimientos_cache = movs
        self._movimientos_cache_key = filtro_key
        return movs

    def _invalidar_caches(self):
        self._movimientos_cache = None
        self._movimientos_cache_key = None

    def refresh(self):
        self._invalidar_caches()
        self._last_kpi_key = None
        self.build_ui()
        if self.page and self.uid:
            self.update()

    def cambiar_vista(self, nueva_vista):
        if self.vista_activa != nueva_vista:
            app_logger.info(f"VISTA: {nueva_vista} (banco={self.banco_global}, mes={self.mes_global})")
            if nueva_vista != "RESUMEN":
                self.excluir_traslados = True
                self.excluir_anulados = True
            self.vista_activa = nueva_vista
            self._actualizar_contenido()

    def cambiar_banco_global(self, banco):
        if self.banco_global == banco:
            return
        app_logger.info(f"FILTRO BANCO: {banco} (mes={self.mes_global}, vista={self.vista_activa})")
        self.banco_global = banco
        self._invalidar_caches()
        self._actualizar_contenido()

    def cambiar_mes_global(self, mes):
        app_logger.info(f"FILTRO MES: {mes} (banco={self.banco_global}, vista={self.vista_activa})")
        if self.mes_global == mes and self.vista_activa == "RESUMEN" and self.vista_flujo_diario.mostrar_calendario:
            self.vista_flujo_diario.mostrar_calendario = False
        elif self.mes_global != mes:
            self.mes_global = mes
            if self.vista_activa == "RESUMEN":
                self.vista_flujo_diario.mostrar_calendario = True
            self._movimientos_cache = None
            self._movimientos_cache_key = None
        self._actualizar_contenido()

    def _reconstruir_flujo(self):
        self.vista_flujo_diario.excluir_traslados = self.excluir_traslados
        self.vista_flujo_diario.excluir_anulados = self.excluir_anulados
        self.vista_flujo_diario.build_ui(banco=self.banco_global, mes=self.mes_global)
        if self.page and self.uid:
            self.update()

    def _toggle_exclusion(self, clave):
        setattr(self, clave, not getattr(self, clave))
        self._actualizar_contenido()

    def _actualizar_contenido(self):
        if self.page and self.uid:
            self._contenedor_grafico.content = ft.Container(
                content=ft.Column([
                    ft.ProgressRing(width=30, height=30, stroke_width=3),
                    ft.Container(height=10),
                    ft.Text("Cargando datos...", size=14, color=ft.colors.GREY_500),
                ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                alignment=ft.alignment.center, expand=True
            )
            self.update()
        self.build_ui()
        if self.page and self.uid:
            self.update()

    def build_ui(self):
        if not DataLoader.has_data() and not self.db_manager.tiene_movimientos() and not self.db_manager.tiene_saldos_diarios():
            self.content = ft.Column([
                ft.Icon(ft.icons.INSERT_CHART_OUTLINED, size=80, color=ft.colors.BLUE_200),
                ft.Text("Faltan datos para el Dashboard", size=24, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_900),
                ft.Text("Ve a la sección 'Generador', carga tus archivos y procesa el reporte.", color=ft.colors.GREY_600)
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
            return

        try:
            meses_disponibles = self.db_manager.get_meses_disponibles()
            if self.mes_global is None and meses_disponibles:
                self.mes_global = meses_disponibles[-1]

            # Obtener datos para KPIs (cacheado por lru_cache si filtros no cambiaron)
            fechas, saldos_ini, ing_op, ing_tr, egr_op, egr_tr, saldos_fin, ing_neto = procesar_datos_flujo_diario(
                self.banco_global, mes_filtro=self.mes_global,
                excluir_traslados=self.excluir_traslados, excluir_anulados=self.excluir_anulados
            )

            saldo_inicial = saldos_ini[0] if saldos_ini else 0.0
            ingresos_mes = sum(ing_neto)
            total_disponible = saldo_inicial + ingresos_mes
            total_salidas = sum(egr_op)
            saldo_final_neto = total_disponible - total_salidas

            opciones_meses = [ft.dropdown.Option(m, self.vista_flujo_diario._formatear_mes(m)) for m in meses_disponibles]
            filtro_mes = ft.Dropdown(
                label="Seleccionar mes", width=250, options=opciones_meses,
                value=self.mes_global,
                on_change=lambda e: self.cambiar_mes_global(e.control.value)
            )
            self._filtros_row.controls = [filtro_mes]

            self._fila_kpis.controls = [
                crear_tarjeta_kpi_compuesta(
                    titulo="TOTAL INGRESOS (DISPONIBLE)", saldo_inicial=saldo_inicial, ingresos_mes=ingresos_mes, 
                    total=total_disponible, icono=ft.icons.TRENDING_UP, color_icono=ft.colors.GREEN_600,
                    on_click=lambda e: self.cambiar_vista("INGRESOS"), seleccionada=(self.vista_activa == "INGRESOS")     
                ),
                crear_tarjeta_kpi(
                    titulo="TOTAL SALIDAS DEL MES", valor=total_salidas, icono=ft.icons.TRENDING_DOWN, color_icono=ft.colors.RED_600,
                    on_click=lambda e: self.cambiar_vista("SALIDAS"), seleccionada=(self.vista_activa == "SALIDAS")
                ),
                crear_tarjeta_kpi(
                    titulo="SALDO FINAL NETO", valor=saldo_final_neto, icono=ft.icons.ACCOUNT_BALANCE_WALLET, color_icono=ft.colors.BLUE_600,
                    on_click=lambda e: self.cambiar_vista("RESUMEN"), seleccionada=(self.vista_activa == "RESUMEN")
                ),
            ]

            if self.vista_activa == "INGRESOS":
                movimientos = self._obtener_movimientos()
                if self.tendencia_ingresos is None:
                    self.tendencia_ingresos = TendenciaIngresos()
                    self.ingresos_dona = GraficoIngresos(on_nivel_change=self.tendencia_ingresos.set_nivel)
                self.tendencia_ingresos.nivel_actual = getattr(self.ingresos_dona, 'nivel_dona', "GENERAL")
                self.tendencia_ingresos.banco = self.banco_global
                self.tendencia_ingresos.mes = self.mes_global
                self.tendencia_ingresos.extraer_datos(movimientos=movimientos)
                self.tendencia_ingresos.dibujar_grafico(self.tendencia_ingresos.dropdown_dias.value)
                self.ingresos_dona.banco = self.banco_global
                self.ingresos_dona.mes = self.mes_global
                self.ingresos_dona.extraer_datos_grafico(movimientos=movimientos)
                self.ingresos_dona.actualizar_dona_ui()
                self._contenedor_grafico.content = ft.Column([
                    ft.Row([self.ingresos_dona], alignment=ft.MainAxisAlignment.CENTER),
                    ft.Container(height=10),
                    ft.Row([self.tendencia_ingresos], alignment=ft.MainAxisAlignment.CENTER),
                ], spacing=0)
                
            elif self.vista_activa == "SALIDAS":
                movimientos = self._obtener_movimientos()
                if self.tendencia_egresos is None:
                    self.tendencia_egresos = TendenciaEgresos()
                    self.egresos_dona = GraficoEgresos(
                        on_nivel_change=self.tendencia_egresos.set_nivel,
                        on_modo_change=self.tendencia_egresos.set_modo
                    )
                self.tendencia_egresos.banco = self.banco_global
                self.tendencia_egresos.mes = self.mes_global
                self.tendencia_egresos.cargar_datos_y_dibujar(movimientos=movimientos)
                self.egresos_dona.banco = self.banco_global
                self.egresos_dona.mes = self.mes_global
                self.egresos_dona.cargar_y_construir(movimientos=movimientos)
                self._contenedor_grafico.content = ft.Column([
                    ft.Row([self.egresos_dona], alignment=ft.MainAxisAlignment.CENTER),
                    ft.Container(height=10),
                    ft.Row([self.tendencia_egresos], alignment=ft.MainAxisAlignment.CENTER),
                ], spacing=0)
            else:
                self.vista_flujo_diario.excluir_traslados = self.excluir_traslados
                self.vista_flujo_diario.excluir_anulados = self.excluir_anulados
                self.vista_flujo_diario.build_ui(banco=self.banco_global, mes=self.mes_global)

                bancos = self.db_manager.get_bancos_disponibles()
                opciones_bancos = [ft.dropdown.Option("TODOS", "Todos los bancos")] + [
                    ft.dropdown.Option(b, b.replace("_", " ").title()) for b in bancos
                ]
                filtro_banco_resumen = ft.Dropdown(
                    label="Filtrar por banco", width=220, options=opciones_bancos,
                    value=self.banco_global,
                    on_change=lambda e: self.cambiar_banco_global(e.control.value)
                )
                checkboxes_resumen = ft.Row([
                    ft.Container(
                        content=ft.Row([
                            ft.Checkbox(value=self.excluir_traslados, on_change=lambda e: self._toggle_exclusion("excluir_traslados")),
                            ft.Text("Excluir Traslados", size=12, color=ft.colors.GREY_700),
                        ], spacing=2),
                        bgcolor=ft.colors.WHITE, border_radius=8, padding=ft.padding.symmetric(horizontal=10, vertical=2),
                        border=ft.border.all(1, ft.colors.GREY_200),
                    ),
                    ft.Container(
                        content=ft.Row([
                            ft.Checkbox(value=self.excluir_anulados, on_change=lambda e: self._toggle_exclusion("excluir_anulados")),
                            ft.Text("Excluir Anulados", size=12, color=ft.colors.GREY_700),
                        ], spacing=2),
                        bgcolor=ft.colors.WHITE, border_radius=8, padding=ft.padding.symmetric(horizontal=10, vertical=2),
                        border=ft.border.all(1, ft.colors.GREY_200),
                    ),
                ], spacing=8)

                filtros_resumen = ft.Row([
                    checkboxes_resumen,
                    ft.Container(expand=True),
                    filtro_banco_resumen,
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

                self._contenedor_grafico.content = ft.Column([
                    filtros_resumen,
                    ft.Container(height=5),
                    self.vista_flujo_diario,
                ], spacing=0, expand=True)

            self._titulo_vista.value = "Dashboard Ejecutivo"
            self._ultima_actualizacion.value = f"Última actualización: {DataLoader.get_last_update()}"

            self.content = ft.ListView([
                ft.Row([self._titulo_vista, ft.Container(expand=True), self._ultima_actualizacion],
                       vertical_alignment=ft.CrossAxisAlignment.END),
                ft.Container(height=5),
                self._filtros_row,
                ft.Container(height=5),
                self._fila_kpis,
                ft.Container(height=15),
                self._contenedor_grafico 
            ], expand=True, spacing=10)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.content = ft.Column([
                ft.Icon(ft.icons.WARNING_AMBER, size=50, color=ft.colors.ORANGE_400),
                ft.Text("Ocurrió un error al cargar el Dashboard", size=18, weight=ft.FontWeight.BOLD, color=ft.colors.RED_700),
                ft.Text("Revisa que los datos estén generados correctamente en la sección Generador.", size=13, color=ft.colors.GREY_600),
                ft.Container(height=10),
                ft.Text(f"Detalle: {type(e).__name__}", size=11, color=ft.colors.GREY_500),
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True)