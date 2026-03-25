# src/ui/views/maestros_view.py
import flet as ft
from src.core.db_manager import DBManager

class MaestrosView(ft.Container):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page_ref = page 
        self.expand = True
        self.padding = 40
        self.bgcolor = "#F8FAFC"
        
        self.db = DBManager()
        
        self.tablas = {
            "proveedores": "Proveedores (NITs)",
            "cuentas_2335": "Cuentas 2335 (Gastos Operacionales)",
            "centros_costos": "Centros de Costos (Cajas)",
            "bancos": "Bancos y Cuentas"
        }
        self.tabla_actual = "centros_costos" # Empezamos por aquí para que lo pruebes
        
        self.import_picker = ft.FilePicker(on_result=self.on_import_result)
        self.page_ref.overlay.append(self.import_picker)

        self.build_ui()
        self.cargar_datos()

    def build_ui(self):
        header = ft.Column([
            ft.Text("Gestión de Bases Maestras", size=28, weight=ft.FontWeight.W_900, color=ft.colors.BLUE_900),
            ft.Text("Administra internamente Proveedores, Gastos y mapeo de Cajas.", size=15, color=ft.colors.GREY_700),
            ft.Divider(height=20, color=ft.colors.TRANSPARENT)
        ])

        self.dropdown_tablas = ft.Dropdown(
            label="Selecciona la Base de Datos a Gestionar",
            options=[ft.dropdown.Option(key=k, text=v) for k, v in self.tablas.items()],
            value=self.tabla_actual, width=400, on_change=self.cambiar_tabla, border_color=ft.colors.BLUE_400
        )

        btn_nuevo = ft.ElevatedButton("Nuevo Registro", icon=ft.icons.ADD, style=ft.ButtonStyle(bgcolor=ft.colors.BLUE_700, color=ft.colors.WHITE), on_click=self.abrir_dialogo_nuevo)
        btn_importar = ft.ElevatedButton("Importar Excel", icon=ft.icons.UPLOAD_FILE, style=ft.ButtonStyle(bgcolor=ft.colors.ORANGE_600, color=ft.colors.WHITE), on_click=lambda e: self.import_picker.pick_files(allowed_extensions=["xlsx", "xls", "csv"]))

        controles = ft.Row([self.dropdown_tablas, ft.Container(expand=True), btn_importar, btn_nuevo], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        self.data_table = ft.DataTable(columns=[], rows=[], width=float("inf"), heading_row_color=ft.colors.BLUE_50)

        tabla_container = ft.Container(
            content=ft.Column([self.data_table], scroll=ft.ScrollMode.ALWAYS),
            expand=True, bgcolor=ft.colors.WHITE, border_radius=10, border=ft.border.all(1, ft.colors.GREY_300), padding=10
        )

        self.content = ft.Column([header, controles, ft.Divider(height=20), tabla_container])

        # --- CAMPOS DINÁMICOS PARA EL DIÁLOGO ---
        self.input_codigo = ft.TextField(label="Código / NIT")
        self.input_nombre = ft.TextField(label="Nombre / Descripción")
        self.input_recauda = ft.TextField(label="Recauda Caja (Solo para CC)")
        self.input_docs = ft.TextField(label="Docs Egreso (Solo para CC)")
        
        self.dialogo_form = ft.AlertDialog(
            title=ft.Text("Registro"),
            content=ft.Column([self.input_codigo, self.input_nombre, self.input_recauda, self.input_docs], height=280, tight=True),
            actions=[
                ft.TextButton("Cancelar", on_click=self.cerrar_dialogo),
                ft.ElevatedButton("Guardar", on_click=self.guardar_registro, bgcolor=ft.colors.BLUE_700, color=ft.colors.WHITE)
            ]
        )
        self.page_ref.overlay.append(self.dialogo_form)

    def cambiar_tabla(self, e):
        self.tabla_actual = self.dropdown_tablas.value
        self.cargar_datos()

    def cargar_datos(self):
        registros = self.db.get_all(self.tabla_actual)
        
        if self.tabla_actual == "centros_costos":
            self.data_table.columns = [
                ft.DataColumn(ft.Text("Costo", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Nombre", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Recauda Caja", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Docs Egreso", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Acciones", weight=ft.FontWeight.BOLD)),
            ]
            self.input_recauda.visible = True
            self.input_docs.visible = True
        else:
            self.data_table.columns = [
                ft.DataColumn(ft.Text("Código / NIT", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Nombre / Descripción", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Acciones", weight=ft.FontWeight.BOLD)),
            ]
            self.input_recauda.visible = False
            self.input_docs.visible = False

        filas = []
        for reg in registros:
            if self.tabla_actual == "centros_costos":
                c, n, r, d = reg
                filas.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text(c)), ft.DataCell(ft.Text(n)), ft.DataCell(ft.Text(r)), ft.DataCell(ft.Text(d)),
                    ft.DataCell(ft.Row([
                        ft.IconButton(icon=ft.icons.EDIT, icon_color=ft.colors.BLUE_600, on_click=lambda e, c=c, n=n, r=r, d=d: self.abrir_dialogo_editar(c, n, r, d)),
                        ft.IconButton(icon=ft.icons.DELETE, icon_color=ft.colors.RED_600, on_click=lambda e, c=c: self.borrar_registro(c))
                    ]))
                ]))
            else:
                c, n = reg
                filas.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text(c)), ft.DataCell(ft.Text(n)),
                    ft.DataCell(ft.Row([
                        ft.IconButton(icon=ft.icons.EDIT, icon_color=ft.colors.BLUE_600, on_click=lambda e, c=c, n=n: self.abrir_dialogo_editar(c, n)),
                        ft.IconButton(icon=ft.icons.DELETE, icon_color=ft.colors.RED_600, on_click=lambda e, c=c: self.borrar_registro(c))
                    ]))
                ]))
        self.data_table.rows = filas
        self.page_ref.update()

    def abrir_dialogo_nuevo(self, e):
        self.input_codigo.value = ""
        self.input_codigo.disabled = False
        self.input_nombre.value = ""
        self.input_recauda.value = ""
        self.input_docs.value = ""
        self.dialogo_form.open = True
        self.page_ref.update()

    def abrir_dialogo_editar(self, codigo, nombre, recauda="", docs=""):
        self.input_codigo.value = codigo
        self.input_codigo.disabled = True
        self.input_nombre.value = nombre
        self.input_recauda.value = recauda
        self.input_docs.value = docs
        self.dialogo_form.open = True
        self.page_ref.update()

    def cerrar_dialogo(self, e):
        self.dialogo_form.open = False
        self.page_ref.update()

    def guardar_registro(self, e):
        cod = self.input_codigo.value.strip()
        nom = self.input_nombre.value.strip().upper()
        rec = self.input_recauda.value.strip().upper()
        doc = self.input_docs.value.strip().upper()
        
        if cod and nom:
            self.db.insert_or_update(self.tabla_actual, cod, nom, rec, doc)
            self.cerrar_dialogo(e)
            self.cargar_datos()
            self.mostrar_snack("✅ Guardado exitosamente", ft.colors.GREEN_700)
        else:
            self.mostrar_snack("⚠️ Debes llenar los campos principales", ft.colors.ORANGE_700)

    def borrar_registro(self, codigo):
        self.db.delete(self.tabla_actual, codigo)
        self.cargar_datos()
        self.mostrar_snack("🗑️ Registro eliminado", ft.colors.RED_700)

    def on_import_result(self, e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            ruta = e.files[0].path
            self.mostrar_snack("Procesando Excel, por favor espera...", ft.colors.BLUE_700)
            exito = self.db.importar_desde_excel(self.tabla_actual, ruta)
            if exito:
                self.cargar_datos()
                self.mostrar_snack("✅ Excel importado a la BD correctamente.", ft.colors.GREEN_700)
            else:
                self.mostrar_snack("❌ Error al importar el Excel.", ft.colors.RED_700)

    def mostrar_snack(self, mensaje, color):
        self.page_ref.snack_bar = ft.SnackBar(ft.Text(mensaje), bgcolor=color)
        self.page_ref.snack_bar.open = True
        self.page_ref.update()