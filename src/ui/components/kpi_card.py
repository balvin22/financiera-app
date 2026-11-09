# ui/components/kpi_card.py
import flet as ft
from src.ui.theme import (
    COLOR_PRIMARY_900, COLOR_PRIMARY_50, COLOR_BG_CARD,
    COLOR_BORDER, COLOR_INGRESO,
    COLOR_TEXT_MUTED, COLOR_TEXT_SECONDARY,
    BORDER_RADIUS_CARD, BORDER_RADIUS_SMALL,
    SIZE_XS, SIZE_XXS,
    WEIGHT_BOLD, WEIGHT_TITLE, SHADOW_CARD,
    COLOR_TEXT_PRIMARY
)

def crear_tarjeta_kpi(titulo, valor, icono, color_icono, on_click=None, seleccionada=False):
    borde = ft.border.all(2, ft.colors.BLUE_500) if seleccionada else ft.border.all(1, COLOR_BORDER)
    fondo = COLOR_PRIMARY_50 if seleccionada else COLOR_BG_CARD

    return ft.Container(
        expand=True,
        on_click=on_click,
        content=ft.Row([
            ft.Container(content=ft.Icon(icono, color=color_icono, size=24), bgcolor=COLOR_BG_CARD, padding=10, border_radius=BORDER_RADIUS_SMALL),
            ft.Column([
                ft.Text(titulo, size=SIZE_XS, color=COLOR_TEXT_MUTED, weight=WEIGHT_BOLD),
                ft.Text(f"$ {valor:,.2f}", size=18, weight=WEIGHT_TITLE, color=COLOR_TEXT_PRIMARY)
            ], spacing=0)
        ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor=fondo, border_radius=BORDER_RADIUS_CARD, padding=15,
        border=borde,
        shadow=SHADOW_CARD
    )

def crear_tarjeta_kpi_compuesta(titulo, saldo_inicial, ingresos_mes, total, icono, color_icono, on_click=None, seleccionada=False):
    borde = ft.border.all(2, ft.colors.BLUE_500) if seleccionada else ft.border.all(1, COLOR_BORDER)
    fondo = COLOR_PRIMARY_50 if seleccionada else COLOR_BG_CARD

    return ft.Container(
        expand=True,
        on_click=on_click,
        content=ft.Row([
            ft.Container(content=ft.Icon(icono, color=color_icono, size=24), bgcolor=COLOR_BG_CARD, padding=10, border_radius=BORDER_RADIUS_SMALL),
            ft.Column([
                ft.Text(titulo, size=SIZE_XS, color=COLOR_TEXT_MUTED, weight=WEIGHT_BOLD),
                ft.Text(f"$ {total:,.2f}", size=18, weight=WEIGHT_TITLE, color=COLOR_TEXT_PRIMARY),
                ft.Container(
                    content=ft.Column([
                        ft.Row([ft.Text("Saldo Inicial:", size=SIZE_XXS, color=COLOR_TEXT_MUTED), ft.Text(f"$ {saldo_inicial:,.2f}", size=SIZE_XXS, weight=WEIGHT_BOLD, color=COLOR_PRIMARY_900)]),
                        ft.Row([ft.Text("Ingresos Mes:", size=SIZE_XXS, color=COLOR_TEXT_MUTED), ft.Text(f"$ {ingresos_mes:,.2f}", size=SIZE_XXS, weight=WEIGHT_BOLD, color=COLOR_INGRESO)])
                    ], spacing=2),
                    padding=ft.padding.only(top=3)
                )
            ], spacing=0)
        ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor=fondo, border_radius=BORDER_RADIUS_CARD, padding=15,
        border=borde,
        shadow=SHADOW_CARD
    )