# src/ui/main_window.py
import flet as ft
from src.ui.views.flujo_view import FlujoView
from src.ui.views.dashboard_view import DashboardView
from src.ui.views.maestros_view import MaestrosView # <-- NUEVO: Importamos la vista

def build_main_window(page: ft.Page):
    page.title = "Consolidador Financiero - Flujo de Efectivo"
    page.theme_mode = ft.ThemeMode.LIGHT 
    page.padding = 0
    page.window_width = 1280 
    page.window_height = 800

    # 1. INSTANCIAMOS LAS VISTAS
    vista_flujo = FlujoView(page)
    vista_dashboard = DashboardView(page)
    vista_maestros = MaestrosView(page) # <-- NUEVO: Instanciamos la vista de bases de datos
    
    # 2. CONTENEDOR DINÁMICO (Aquí cambiaremos qué se muestra)
    area_trabajo = ft.Container(content=vista_flujo, expand=True)

    # 3. LÓGICA DE NAVEGACIÓN
    def cambiar_vista(e):
        destino = e.control.data
        if destino == "generador":
            area_trabajo.content = vista_flujo
        elif destino == "dashboard":
            vista_dashboard.build_ui() # Recarga los datos al entrar
            area_trabajo.content = vista_dashboard
        elif destino == "maestros": # <-- NUEVO: Enrutamiento
            vista_maestros.cargar_datos() # Refresca la tabla por si hubo cambios
            area_trabajo.content = vista_maestros
        
        # Efecto visual de selección en el menú
        btn_gen.bgcolor = ft.colors.BLUE_800 if destino == "generador" else ft.colors.TRANSPARENT
        btn_dash.bgcolor = ft.colors.BLUE_800 if destino == "dashboard" else ft.colors.TRANSPARENT
        btn_maestros.bgcolor = ft.colors.BLUE_800 if destino == "maestros" else ft.colors.TRANSPARENT # <-- NUEVO
        page.update()

    # BOTONES DE MENÚ
    btn_gen = ft.ListTile(
        leading=ft.Icon(ft.icons.ACCOUNT_TREE, color=ft.colors.WHITE),
        title=ft.Text("Generador de Reportes", color=ft.colors.WHITE, weight=ft.FontWeight.BOLD),
        bgcolor=ft.colors.BLUE_800, # Activo por defecto
        hover_color=ft.colors.BLUE_700,
        data="generador", on_click=cambiar_vista
    )
    
    btn_dash = ft.ListTile(
        leading=ft.Icon(ft.icons.INSERT_CHART_OUTLINED, color=ft.colors.WHITE),
        title=ft.Text("Dashboard Ejecutivo", color=ft.colors.WHITE, weight=ft.FontWeight.BOLD),
        bgcolor=ft.colors.TRANSPARENT,
        hover_color=ft.colors.BLUE_700,
        data="dashboard", on_click=cambiar_vista
    )

    # <-- NUEVO: Botón de Bases Maestras -->
    btn_maestros = ft.ListTile(
        leading=ft.Icon(ft.icons.STORAGE, color=ft.colors.WHITE),
        title=ft.Text("Bases Maestras", color=ft.colors.WHITE, weight=ft.FontWeight.BOLD),
        bgcolor=ft.colors.TRANSPARENT,
        hover_color=ft.colors.BLUE_700,
        data="maestros", on_click=cambiar_vista
    )

    # PANEL LATERAL
    sidebar = ft.Container(
        width=300, bgcolor=ft.colors.BLUE_GREY_900,
        padding=ft.padding.only(top=35, left=20, right=20, bottom=25),
        content=ft.Column([
            ft.Row([
                ft.Icon(ft.icons.QUERY_STATS, size=38, color=ft.colors.BLUE_400),
                ft.Text("FINANZAS", size=22, weight=ft.FontWeight.W_900, color=ft.colors.WHITE),
            ]),
            ft.Divider(height=30, color=ft.colors.BLUE_GREY_700),
            
            ft.Text("MENÚ PRINCIPAL", size=12, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_GREY_400),
            ft.Container(height=5),
            btn_gen,
            btn_dash,
            btn_maestros, # <-- NUEVO: Agregado a la columna del menú
            
            ft.Container(expand=True),
            ft.Divider(height=20, color=ft.colors.BLUE_GREY_700),
            ft.Row([
                ft.Icon(ft.icons.SUPPORT_AGENT, size=16, color=ft.colors.BLUE_GREY_400),
                ft.Text("Desarrollo y Automatización", size=12, color=ft.colors.BLUE_GREY_400)
            ], alignment=ft.MainAxisAlignment.CENTER)
        ])
    )

    # ARMAMOS LA PANTALLA
    layout = ft.Row([sidebar, area_trabajo], expand=True, spacing=0)
    page.add(layout)