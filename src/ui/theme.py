import flet as ft

COLOR_BG = "#F8FAFC"
COLOR_BG_CARD = ft.colors.WHITE
COLOR_BORDER = ft.colors.GREY_200
COLOR_TITLE = ft.colors.BLUE_900
COLOR_SUBTITLE = ft.colors.GREY_700
COLOR_WHITE = ft.colors.WHITE
COLOR_PRIMARY = ft.colors.BLUE_800
COLOR_PRIMARY_900 = ft.colors.BLUE_900
COLOR_PRIMARY_50 = ft.colors.BLUE_50
COLOR_SECONDARY = ft.colors.BLUE_GREY_800
COLOR_ACCENT = ft.colors.DEEP_ORANGE_400
COLOR_INGRESO = ft.colors.GREEN_600
COLOR_EGRESO = ft.colors.RED_600

COLOR_TEXT_PRIMARY = ft.colors.BLUE_900
COLOR_TEXT_SECONDARY = ft.colors.GREY_700
COLOR_TEXT_MUTED = ft.colors.GREY_500
COLOR_TEXT_LIGHT = ft.colors.BLUE_GREY_300

PADDING_VIEW = 30
PADDING_CARD = 15
PADDING_SECTION = 20

BORDER_RADIUS_CARD = 12
BORDER_RADIUS_SMALL = 8
BORDER_RADIUS_TABLE = 8

SIZE_TITLE = 24
SIZE_TITLE_SM = 28
SIZE_SECTION_TITLE = 18
SIZE_SUBSECTION_TITLE = 16
SIZE_BODY = 14
SIZE_SMALL = 13
SIZE_XS = 11
SIZE_XXS = 10

WEIGHT_TITLE = ft.FontWeight.W_900
WEIGHT_SECTION = ft.FontWeight.W_800
WEIGHT_SUBSECTION = ft.FontWeight.W_600
WEIGHT_BOLD = ft.FontWeight.BOLD
WEIGHT_NORMAL = ft.FontWeight.NORMAL

SHADOW_CARD = ft.BoxShadow(
    blur_radius=10,
    color=ft.colors.BLACK12,
    offset=ft.Offset(0, 3),
)

SHADOW_ELEVATED = ft.BoxShadow(
    blur_radius=15,
    color=ft.colors.BLACK12,
    offset=ft.Offset(0, 5),
)

BORDER_CARD = ft.border.all(1, COLOR_BORDER)

STYLE_BUTTON_PRIMARY = ft.ButtonStyle(
    bgcolor=COLOR_PRIMARY,
    color=COLOR_WHITE,
    shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS_SMALL),
)

COLOR_CHART_INGRESOS = {
    "primary": ft.colors.BLUE_900,
    "primary_50": ft.colors.BLUE_50,
    "accent": ft.colors.GREEN_700,
    "accent_900": ft.colors.GREEN_900,
    "border": ft.colors.GREY_200,
    "titulo": ft.colors.BLUE_900,
}

COLOR_CHART_EGRESOS = {
    "primary": ft.colors.RED_900,
    "primary_50": ft.colors.RED_50,
    "accent": ft.colors.RED_700,
    "accent_900": ft.colors.RED_900,
    "border": ft.colors.GREY_200,
    "titulo": ft.colors.RED_900,
}

TEMA_TENDENCIA_INGRESOS = {
    "leyenda_bg": ft.colors.BLUE_50,
    "accent": ft.colors.BLUE_500,
}

TEMA_TENDENCIA_EGRESOS = {
    "leyenda_bg": ft.colors.RED_50,
    "accent": ft.colors.RED_500,
}


def crear_header_vista(titulo: str, subtitulo: str = None) -> ft.Column:
    controles = [
        ft.Text(titulo, size=SIZE_TITLE_SM, weight=WEIGHT_TITLE, color=COLOR_TITLE),
    ]
    if subtitulo:
        controles.append(
            ft.Text(subtitulo, size=SIZE_BODY, color=COLOR_SUBTITLE)
        )
    controles.append(ft.Divider(height=20, color=ft.colors.TRANSPARENT))
    return ft.Column(controles)


def crear_contenedor_seccion(
    content, padding=PADDING_SECTION, bgcolor=COLOR_BG_CARD,
    border_radius=BORDER_RADIUS_CARD, border=BORDER_CARD, shadow=None,
    expand=False
) -> ft.Container:
    return ft.Container(
        content=content,
        padding=padding,
        bgcolor=bgcolor,
        border_radius=border_radius,
        border=border,
        shadow=shadow or SHADOW_CARD,
        expand=expand,
    )
