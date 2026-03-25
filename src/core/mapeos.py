# src/core/mapeos.py

MAPEO_CAJAS = {
    "10101": "CAJA POPAYAN PPAL", "10105": "CAJA POPAYAN PPAL", "10106": "CAJA POPAYAN PPAL", "10111": "CAJA POPAYAN PPAL",
    "10102": "CALLE 5TA", "10107": "CALLE 5TA",
    "10120": "CAJA CARTERA",
    "10201": "CAJA BORDO", "10204": "CAJA BORDO",
    "10301": "CAJA SANTANDER", "10305": "CAJA SANTANDER", "10308": "CAJA SANTANDER", "10310": "CAJA SANTANDER",
    "10312": "CAJA PTO TEJADA", "10601": "CAJA PTO TEJADA",
    "10401": "CAJA AMBIENTA", "10402": "CAJA AMBIENTA",
    "10403": "CAJA CL 7", "10501": "CAJA CL 7",
    "20101": "CAJA CALI", "20102": "CAJA CALI", "20106": "CAJA CALI",
    "20105": "CAJA YUMBO", "20103": "CAJA YUMBO",
    "30101": "CAJA PASTO", "30105": "CAJA PASTO", "30119": "CAJA PASTO", "30114": "CAJA PASTO",
    "30102": "CAJA LA UNION",
    "30124": "CAJA TUQUERRES", "30125": "CAJA TUQUERRES", "30126": "CAJA TUQUERRES",
    "30301": "CAJA TUQUERRES", "30303": "CAJA TUQUERRES", "30304": "CAJA TUQUERRES",
    "30312": "CAJA TUQUERRES", "30309": "CAJA TUQUERRES",
    "70101": "CAJA PITALITO", "70102": "CAJA PITALITO", "70103": "CAJA PITALITO"
}

# NUEVO: MAPEO DE PREFIJOS DE DOCUMENTO (EXTRACTO DE LA IMAGEN)
# Esto sirve para cruzar los Egresos del archivo 2335 con la Caja Real
MAPEO_DOCS_CAJA = {
    # Popayán Principal y Cartera comparten consecutivos
    "EI01": "CAJA POPAYAN PPAL", "ES01": "CAJA POPAYAN PPAL",
    "EI01": "CALLE 5TA", "ES01": "CALLE 5TA",
    "EI01": "CAJA CARTERA", "ES01": "CAJA CARTERA",
    
    # Bordo
    "EI02": "CAJA BORDO", "ES02": "CAJA BORDO",
    
    # Santander
    "EI06": "CAJA SANTANDER", "ES06": "CAJA SANTANDER",
    
    # Pto Tejada
    "EI16": "CAJA PTO TEJADA", "ES16": "CAJA PTO TEJADA",
    
    # Ambienta Principal y Calle 7 (Nota: la imagen dice que CL7 era ES14/EI14 pero ahora usa ES10/EI10)
    "EI10": "CAJA AMBIENTA", "ES10": "CAJA AMBIENTA",
    "EI14": "CAJA CL 7", "ES14": "CAJA CL 7", # Lo dejamos por si hay históricos
    
    # Cali Principal y Yumbo comparten consecutivos
    "EI04": "CAJA CALI", "ES04": "CAJA CALI", 
    
    # Pasto Principal y La Unión comparten consecutivos
    "EI05": "CAJA PASTO", "ES05": "CAJA PASTO",
    
    # Tuquerres
    "EI03": "CAJA TUQUERRES", "ES03": "CAJA TUQUERRES",
    
    # Pitalito
    "EI17": "CAJA PITALITO", "ES17": "CAJA PITALITO"
}

MAPEO_CAJAS_TITULO = {
    "10101": "Caja Popayan Ppal", "10105": "Caja Popayan Ppal", "10106": "Caja Popayan Ppal", "10111": "Caja Popayan Ppal",
    "10102": "Calle 5ta", "10107": "Calle 5ta",
    "10120": "Caja Cartera",
    "10201": "Caja Bordo", "10204": "Caja Bordo",
    "10301": "Caja Santander", "10305": "Caja Santander", "10308": "Caja Santander", "10310": "Caja Santander",
    "10312": "Caja Pto Tejada", "10601": "Caja Pto Tejada",
    "10401": "Caja Ambienta", "10402": "Caja Ambienta",
    "10403": "Caja Cl 7", "10501": "Caja Cl 7",
    "20101": "Caja Cali", "20102": "Caja Cali", "20106": "Caja Cali",
    "20105": "Caja Yumbo", "20103": "Caja Yumbo",
    "30101": "Caja Pasto", "30105": "Caja Pasto", "30119": "Caja Pasto", "30114": "Caja Pasto",
    "30102": "Caja La Union",
    "30124": "Caja Tuquerres", "30125": "Caja Tuquerres", "30126": "Caja Tuquerres",
    "30301": "Caja Tuquerres", "30303": "Caja Tuquerres", "30304": "Caja Tuquerres",
    "30312": "Caja Tuquerres", "30309": "Caja Tuquerres",
    "70101": "Caja Pitalito", "70102": "Caja Pitalito", "70103": "Caja Pitalito"
}

ORDEN_BANCOS = {"BANCOLOMBIA": 1, "DAVIVIENDA": 2, "OCCIDENTE": 3, "AGRARIO": 4, "ALIANZA": 5, "CAJA": 6}

COLORES_FT = [
    "BLUE_600", "GREEN_600", "ORANGE_700",
    "PURPLE_600", "CYAN_700", "YELLOW_700",
    "PINK_600", "INDIGO_600", "TEAL_600",
    "RED_600", "DEEP_PURPLE_600", "LIGHT_BLUE_700",
    "LIME_700", "BROWN_500",
]

COLORES_ENTIDADES = {
    "CAJA": "RED_600",
    "BANCOS": "ORANGE_600",
}

COLORES_BANCOS = {
    "BANCOLOMBIA": "BLUE_700",
    "DAVIVIENDA": "RED_600",
    "OCCIDENTE": "GREEN_700",
    "AGRARIO": "TEAL_600",
    "ALIANZA": "PURPLE_600",
    "CAJA_BANCOS": "DEEP_ORANGE_600",
}

COLORES_CAJAS = {
    "CAJA POPAYAN PPAL": "RED_500",
    "CALLE 5TA": "ORANGE_500",
    "CAJA CARTERA": "AMBER_500",
    "CAJA BORDO": "YELLOW_600",
    "CAJA SANTANDER": "LIME_600",
    "CAJA PTO TEJADA": "GREEN_500",
    "CAJA AMBIENTA": "TEAL_500",
    "CAJA CL 7": "CYAN_500",
    "CAJA CALI": "LIGHT_BLUE_600",
    "CAJA YUMBO": "BLUE_500",
    "CAJA PASTO": "INDIGO_500",
    "CAJA LA UNION": "PURPLE_500",
    "CAJA TUQUERRES": "PINK_500",
    "CAJA PITALITO": "DEEP_PURPLE_500",
}

COLORES_PROVEEDORES = [
    "RED_500", "ORANGE_500", "AMBER_500", "YELLOW_600",
    "LIME_600", "GREEN_500", "TEAL_500", "CYAN_500",
    "LIGHT_BLUE_600", "BLUE_500", "INDIGO_500", "PURPLE_500",
]

COLORES_INGRESOS_ENTIDADES = {
    "CAJA": "GREEN_600",
    "BANCOS": "BLUE_600",
}

COLORES_INGRESOS_BANCOS = {
    "BANCOLOMBIA": "BLUE_700",
    "DAVIVIENDA": "RED_600",
    "OCCIDENTE": "GREEN_700",
    "AGRARIO": "TEAL_600",
    "ALIANZA": "PURPLE_600",
    "CAJA_BANCOS": "DEEP_ORANGE_600",
}

COLORES_INGRESOS_CAJAS = {
    "CAJA POPAYAN PPAL": "GREEN_500",
    "CALLE 5TA": "TEAL_500",
    "CAJA CARTERA": "CYAN_500",
    "CAJA BORDO": "LIGHT_BLUE_600",
    "CAJA SANTANDER": "BLUE_500",
    "CAJA PTO TEJADA": "INDIGO_500",
    "CAJA AMBIENTA": "PURPLE_500",
    "CAJA CL 7": "PINK_500",
    "CAJA CALI": "DEEP_PURPLE_500",
    "CAJA YUMBO": "ORANGE_500",
    "CAJA PASTO": "AMBER_500",
    "CAJA LA UNION": "YELLOW_600",
    "CAJA TUQUERRES": "LIME_600",
    "CAJA PITALITO": "BROWN_500",
}

def obtener_color_ingresos(categoria: str, nivel: str = "GENERAL"):
    """Retorna el color consistente para ingresos."""
    import flet as _ft
    
    if nivel == "GENERAL":
        color_nombre = COLORES_INGRESOS_ENTIDADES.get(categoria.upper(), "GREY_500")
    elif nivel == "BANCOS":
        color_nombre = COLORES_INGRESOS_BANCOS.get(categoria.upper(), "GREY_500")
    elif nivel == "CAJA":
        color_nombre = COLORES_INGRESOS_CAJAS.get(categoria.upper(), "GREY_500")
    else:
        color_nombre = "GREY_500"
    
    return getattr(_ft.colors, color_nombre, _ft.colors.GREY_500)

def obtener_color(categoria: str, modo: str = "ENTIDADES", nivel: str = "GENERAL"):
    """Retorna el color consistente para una categoria de egresos."""
    import flet as _ft
    
    if modo == "ENTIDADES":
        if nivel == "GENERAL":
            color_nombre = COLORES_ENTIDADES.get(categoria.upper(), "GREY_500")
        elif nivel == "BANCOS":
            color_nombre = COLORES_BANCOS.get(categoria.upper(), "GREY_500")
        elif nivel == "CAJA":
            color_nombre = COLORES_CAJAS.get(categoria.upper(), "GREY_500")
        else:
            color_nombre = "GREY_500"
    else:
        color_nombre = "GREY_500"
    
    return getattr(_ft.colors, color_nombre, _ft.colors.GREY_500)

def obtener_color_proveedor(categoria: str, indice: int):
    """Retorna el color para un proveedor basado en su índice."""
    import flet as _ft
    color_nombre = COLORES_PROVEEDORES[indice % len(COLORES_PROVEEDORES)]
    return getattr(_ft.colors, color_nombre, _ft.colors.GREY_500)