# ui/components/kpi_card.py
import flet as ft

def crear_tarjeta_kpi(titulo, valor, icono, color_icono, on_click=None, seleccionada=False):
    """Genera una tarjeta KPI estándar y reutilizable, con opción de selección."""
    
    # Si está seleccionada, le ponemos un borde azul más grueso y un fondito azul muy claro
    borde = ft.border.all(2, ft.colors.BLUE_500) if seleccionada else ft.border.all(1, ft.colors.GREY_200)
    fondo = ft.colors.BLUE_50 if seleccionada else ft.colors.WHITE
    
    return ft.Container(
        expand=True,
        on_click=on_click, # Habilitamos el clic (¡sin la propiedad cursor!)
        content=ft.Row([
            ft.Container(content=ft.Icon(icono, color=color_icono, size=24), bgcolor=ft.colors.WHITE, padding=10, border_radius=8),
            ft.Column([
                ft.Text(titulo, size=11, color=ft.colors.GREY_500, weight=ft.FontWeight.BOLD),
                ft.Text(f"$ {valor:,.2f}", size=18, weight=ft.FontWeight.W_900, color=ft.colors.BLUE_900)
            ], spacing=0)
        ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor=fondo, border_radius=12, padding=15,
        border=borde,
        shadow=ft.BoxShadow(blur_radius=10, color=ft.colors.BLACK12, offset=ft.Offset(0, 3))
    )

def crear_tarjeta_kpi_compuesta(titulo, saldo_inicial, ingresos_mes, total, icono, color_icono, on_click=None, seleccionada=False):
    """Genera la tarjeta KPI compuesta, con opción de selección."""
    
    borde = ft.border.all(2, ft.colors.BLUE_500) if seleccionada else ft.border.all(1, ft.colors.GREY_200)
    fondo = ft.colors.BLUE_50 if seleccionada else ft.colors.WHITE
    
    return ft.Container(
        expand=True,
        on_click=on_click, # Habilitamos el clic (¡sin la propiedad cursor!)
        content=ft.Row([
            ft.Container(content=ft.Icon(icono, color=color_icono, size=24), bgcolor=ft.colors.WHITE, padding=10, border_radius=8),
            ft.Column([
                ft.Text(titulo, size=11, color=ft.colors.GREY_500, weight=ft.FontWeight.BOLD),
                ft.Text(f"$ {total:,.2f}", size=18, weight=ft.FontWeight.W_900, color=ft.colors.BLUE_900),
                ft.Container(
                    content=ft.Column([
                        ft.Row([ft.Text("Saldo Inicial:", size=10, color=ft.colors.GREY_500), ft.Text(f"$ {saldo_inicial:,.2f}", size=10, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_700)]),
                        ft.Row([ft.Text("Ingresos Mes:", size=10, color=ft.colors.GREY_500), ft.Text(f"$ {ingresos_mes:,.2f}", size=10, weight=ft.FontWeight.BOLD, color=ft.colors.GREEN_700)])
                    ], spacing=2),
                    padding=ft.padding.only(top=3)
                )
            ], spacing=0)
        ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor=fondo, border_radius=12, padding=15,
        border=borde,
        shadow=ft.BoxShadow(blur_radius=10, color=ft.colors.BLACK12, offset=ft.Offset(0, 3))
    )