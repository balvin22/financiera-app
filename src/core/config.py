# src/core/config.py
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CACHE_DIR = BASE_DIR / "local_cache"
ASSETS_DIR = BASE_DIR / "assets"

BANCOS_CONFIG = {
    "bancolombia": {"nombre": "Bancolombia", "color": "#1a56db"},
    "davivienda": {"nombre": "Davivienda", "color": "#dc2626"},
    "occidente": {"nombre": "Banco Occidente", "color": "#1e3a8a"},
    "agrario": {"nombre": "Banco Agrario", "color": "#16a34a"},
    "alianza": {"nombre": "Alianza Fiduciaria", "color": "#0d9488"},
    "caja": {"nombre": "Caja General", "color": "#ea580c"},
    "caja_bancos": {"nombre": "Mov. Bancos (Prov)", "color": "#9333ea"},
}

CAJAS_LOGOS = {
    "bancolombia": "logos/bancolombia.png",
    "davivienda": "logos/davivienda.png",
    "occidente": "logos/occidente.png",
    "agrario": "logos/agrario.svg",
    "alianza": "logos/alianza.png",
}

PROVEEDORES_PATH = CACHE_DIR / "proveedores.xlsx"
PROVEEDORES_KEYWORDS = [
    "LG ELECTRONICS COLOMBIA LTDA",
    "INDUSTRIAS FANTASIA SAS",
    "CHALLENGER SAS",
    "SAMSUNG ELECTRONICS COLOMBIA SA",
    "MABE COLOMBIA SAS",
    "MIDEA COLOMBIA EQUIPMENTS SAS",
    "INDURAMA ECUADOR SAS"
]

ALIENZA_CLAVE_PDF = "900333755"
