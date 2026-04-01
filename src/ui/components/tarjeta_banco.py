# ui/components/tarjeta_banco.py
import flet as ft

class TarjetaBanco(ft.Container):
    def __init__(self, banco_id: str, nombre: str, color: str, on_cargar_click, icono: str = None, logo_path: str = None):
        super().__init__()
        self.banco_id = banco_id
        
        self.width = 200
        self.height = 235
        self.bgcolor = ft.colors.WHITE
        self.border_radius = 15
        self.padding = 15
        self.alignment = ft.alignment.center
        self.border = ft.border.all(1, ft.colors.GREY_200)
        self.shadow = ft.BoxShadow(blur_radius=15, color=ft.colors.BLACK12, offset=ft.Offset(0, 5))

        self.texto_estado = ft.Text("Esperando archivo...", color=ft.colors.GREY_500, size=12)
        
        self.input_saldo = ft.TextField(
            label="Saldo Inicial", value="", hint_text="0.00", width=160, height=48, dense=True, 
            prefix_text="$ ", text_size=13, content_padding=ft.padding.symmetric(horizontal=10, vertical=10), 
            border_color=ft.colors.BLUE_200, focused_border_color=ft.colors.BLUE_600,
            tooltip=f"Ingresa el saldo inicial real de {nombre}"
        )

        # --- LÓGICA MIXTA (LOGO O ICONO) ---
        if logo_path:
            # Si pasaste una ruta de logo, pinta la imagen con un tamaño controlado
            encabezado_visual = ft.Image(src=logo_path, width=80, height=35, fit=ft.ImageFit.CONTAIN)
        else:
            # Si no hay logo, usa el icono estándar que ya teníamos
            encabezado_visual = ft.Icon(icono, size=30, color=color)

        self.content = ft.Column([
            encabezado_visual,
            ft.Text(nombre, size=16, weight=ft.FontWeight.W_700),
            self.texto_estado,
            ft.ElevatedButton(
                "Cargar Archivo", icon=ft.icons.UPLOAD_FILE,
                on_click=lambda e: on_cargar_click(self.banco_id),
                style=ft.ButtonStyle(
                    bgcolor={ft.MaterialState.DEFAULT: ft.colors.WHITE, ft.MaterialState.HOVERED: color},
                    color={ft.MaterialState.DEFAULT: color, ft.MaterialState.HOVERED: ft.colors.WHITE},
                    side=ft.BorderSide(1, color)
                )
            ),
            ft.Container(height=5),
            self.input_saldo
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    def marcar_como_cargado(self):
        self.texto_estado.value = "✅ Archivo Cargado"
        self.texto_estado.color = ft.colors.GREEN_600
        self.texto_estado.weight = ft.FontWeight.BOLD
        self.update()

    def obtener_saldo(self) -> float:
        val = self.input_saldo.value.replace("$", "").replace(",", "").strip()
        return float(val) if val else 0.0

    def set_saldo(self, valor: float):
        self.input_saldo.value = f"{valor:.2f}"
        self.input_saldo.border_color = ft.colors.GREEN_500
        self.update()

    def limpiar(self):
        self.texto_estado.value = "Esperando archivo..."
        self.texto_estado.color = ft.colors.GREY_500
        self.texto_estado.weight = ft.FontWeight.NORMAL
        self.input_saldo.value = ""
        self.input_saldo.border_color = ft.colors.BLUE_200
        self.update()