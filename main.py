# main.py
import flet as ft
from src.ui.main_window import build_main_window

if __name__ == "__main__":
    ft.app(target=build_main_window, assets_dir="assets")