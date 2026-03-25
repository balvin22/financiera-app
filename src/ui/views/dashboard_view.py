# ui/views/dashboard_view.py
import flet as ft
import polars as pl
import os
import traceback

from src.ui.components.kpi_card import crear_tarjeta_kpi, crear_tarjeta_kpi_compuesta
from src.ui.components.grafico_ingresos import GraficoIngresos
from src.ui.components.grafico_egresos import GraficoEgresos
from src.ui.components.tendencia_ingresos import TendenciaIngresos
from src.ui.components.tendencia_egresos import TendenciaEgresos

class DashboardView(ft.Container):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True
        self.padding = 30 
        self.bgcolor = "#F8FAFC"
        self.vista_activa = "INGRESOS" 
        self.build_ui()

    def cambiar_vista(self, nueva_vista):
        if self.vista_activa != nueva_vista:
            self.vista_activa = nueva_vista
            self.build_ui() 
            if self.page and self.uid:
                self.update()

    def build_ui(self):
        if not os.path.exists("local_cache/base_detallada.parquet") or not os.path.exists("local_cache/base_resumen.parquet"):
            self.content = ft.Column([
                ft.Icon(ft.icons.INSERT_CHART_OUTLINED, size=80, color=ft.colors.BLUE_200),
                ft.Text("Faltan datos para el Dashboard", size=24, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_900),
                ft.Text("Ve a la sección 'Generador', carga tus archivos y procesa el reporte.", color=ft.colors.GREY_600)
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
            return

        try:
            df_res = pl.read_parquet("local_cache/base_resumen.parquet").to_pandas()

            def obtener_valor(concepto_str):
                try:
                    vals = df_res.loc[df_res['Concepto'] == concepto_str, 'Valor'].dropna().values
                    return float(vals[0]) if len(vals) > 0 else 0.0
                except:
                    return 0.0

            ingresos_mes = obtener_valor("Total Ingresos del mes")
            saldo_inicial = obtener_valor("Saldo inicial del mes anterior")
            total_disponible = obtener_valor("Total Disponible")
            total_salidas = obtener_valor("Total salidas del mes")
            saldo_final_neto = total_disponible - total_salidas

            fila_kpis = ft.Row([
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
            ], spacing=15)

            if self.vista_activa == "INGRESOS":
                # --- MAGIA: INSTANCIAMOS Y CONECTAMOS CON EL EVENTO ---
                tendencia_grafico = TendenciaIngresos()
                ingresos_dona = GraficoIngresos(on_nivel_change=tendencia_grafico.set_nivel)

                contenedor_grafico = ft.Column([
                    ft.Row([ingresos_dona], alignment=ft.MainAxisAlignment.CENTER),
                    ft.Container(height=10),
                    ft.Row([tendencia_grafico], alignment=ft.MainAxisAlignment.CENTER) 
                ], spacing=0)
                
            elif self.vista_activa == "SALIDAS":
                tendencia_egresos = TendenciaEgresos()
                egresos_dona = GraficoEgresos(
                    on_nivel_change=tendencia_egresos.set_nivel,
                    on_modo_change=tendencia_egresos.set_modo
                )

                contenedor_grafico = ft.Column([
                    ft.Row([egresos_dona], alignment=ft.MainAxisAlignment.CENTER),
                    ft.Container(height=10),
                    ft.Row([tendencia_egresos], alignment=ft.MainAxisAlignment.CENTER) 
                ], spacing=0)
            else:
                contenedor_grafico = ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.icons.ACCOUNT_BALANCE_WALLET, size=60, color=ft.colors.BLUE_200),
                        ft.Text("Resumen General de Cierre", size=20, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_900)
                    ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    bgcolor=ft.colors.WHITE, border_radius=12, padding=50, border=ft.border.all(1, ft.colors.GREY_200), expand=True, height=350
                )

            self.content = ft.ListView([
                ft.Text("Dashboard Ejecutivo", size=24, weight=ft.FontWeight.W_900, color=ft.colors.BLUE_900),
                ft.Container(height=5),
                fila_kpis,
                ft.Container(height=15),
                contenedor_grafico 
            ], expand=True, spacing=10)

        except Exception as e:
            tb = traceback.format_exc()
            self.content = ft.Column([
                ft.Text(f"Error cargando: {type(e).__name__} - {str(e)}", color=ft.colors.RED_600, weight=ft.FontWeight.BOLD),
                ft.Text(tb, size=11, color=ft.colors.GREY_700, selectable=True)
            ], scroll=ft.ScrollMode.AUTO, expand=True)