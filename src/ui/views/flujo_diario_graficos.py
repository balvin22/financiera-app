# src/ui/views/flujo_diario_graficos.py
import flet as ft
from src.core.db_manager import DBManager

class FlujoDiarioGraficos(ft.Container):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True
        self.padding = 30
        self.bgcolor = "#F8FAFC"
        
        self.db_manager = DBManager()
        self.banco_seleccionado = "TODOS"
        self.build_ui()

    def cambiar_banco(self, banco):
        self.banco_seleccionado = banco
        self.build_ui()
        self.page.update()

    def get_data_grafico(self):
        if self.banco_seleccionado == "TODOS":
            datos = self.db_manager.get_totales_por_fecha()
        else:
            datos = self.db_manager.get_flujos_diarios(banco=self.banco_seleccionado)
        
        fechas = []
        ingresos = []
        egresos = []
        
        if self.banco_seleccionado == "TODOS":
            for row in datos:
                fechas.append(str(row[0]))
                ingresos.append(float(row[1]) if row[1] else 0.0)
                egresos.append(float(row[2]) if row[2] else 0.0)
        else:
            from collections import defaultdict
            temp = defaultdict(lambda: [0.0, 0.0])
            for row in datos:
                temp[row[0]] = [
                    temp[row[0]][0] + (float(row[2]) if row[2] else 0.0),
                    temp[row[0]][1] + (float(row[3]) if row[3] else 0.0)
                ]
            for fecha in sorted(temp.keys()):
                fechas.append(fecha)
                ingresos.append(temp[fecha][0])
                egresos.append(temp[fecha][1])
        
        return fechas, ingresos, egresos

    def get_data_tabla(self):
        if self.banco_seleccionado == "TODOS":
            datos = self.db_manager.get_totales_por_fecha()
        else:
            datos = self.db_manager.get_flujos_diarios(banco=self.banco_seleccionado)
        
        if self.banco_seleccionado == "TODOS":
            return [(str(row[0]), row[1] or 0, row[2] or 0) for row in datos]
        else:
            from collections import defaultdict
            temp = defaultdict(lambda: [0.0, 0.0])
            for row in datos:
                temp[row[0]] = [
                    temp[row[0]][0] + (float(row[2]) if row[2] else 0.0),
                    temp[row[0]][1] + (float(row[3]) if row[3] else 0.0)
                ]
            return [(fecha, vals[0], vals[1]) for fecha, vals in sorted(temp.items())]

    def build_ui(self):
        fechas, ingresos, egresos = self.get_data_grafico()
        datos_tabla = self.get_data_tabla()
        
        bancos = self.db_manager.get_bancos_disponibles()
        opciones_bancos = [ft.dropdown.Option("TODOS", "Todos los bancos")] + [
            ft.dropdown.Option(b, b.replace("_", " ").title()) for b in bancos
        ]

        header = ft.Column([
            ft.Text("Flujo de Efectivo Diario", size=28, weight=ft.FontWeight.W_900, color=ft.colors.BLUE_900),
            ft.Text("Visualiza la tendencia de ingresos y egresos por día", size=15, color=ft.colors.GREY_700),
            ft.Divider(height=20, color=ft.colors.TRANSPARENT)
        ])

        selector_banco = ft.Dropdown(
            label="Filtrar por banco",
            width=250,
            options=opciones_bancos,
            value=self.banco_seleccionado,
            on_change=lambda e: self.cambiar_banco(e.control.value)
        )

        total_ingresos = sum(ingresos)
        total_egresos = sum(egresos)
        saldo_neto = total_ingresos - total_egresos

        kpis = ft.Row([
            self._crear_kpi("Total Ingresos", f"$ {total_ingresos:,.0f}", ft.colors.GREEN_700, ft.icons.TRENDING_UP),
            self._crear_kpi("Total Egresos", f"$ {total_egresos:,.0f}", ft.colors.RED_700, ft.icons.TRENDING_DOWN),
            self._crear_kpi("Saldo Neto", f"$ {saldo_neto:,.0f}", ft.colors.BLUE_700 if saldo_neto >= 0 else ft.colors.ORANGE_700, ft.icons.ACCOUNT_BALANCE_WALLET),
            self._crear_kpi("Días Registrados", str(len(fechas)), ft.colors.PURPLE_700, ft.icons.CALENDAR_MONTH),
        ], spacing=15)

        if not fechas:
            contenido_principal = ft.Column([
                ft.Icon(ft.icons.CALENDAR_TODAY, size=80, color=ft.colors.BLUE_200),
                ft.Text("No hay datos diarios registrados", size=20, color=ft.colors.GREY_600),
                ft.Text("Usa el switch 'Cargue Diario' en el Generador para cargar extractos", size=14, color=ft.colors.GREY_500)
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        else:
            barras = self._crear_barras(fechas, ingresos, egresos)
            tabla = self._crear_tabla(datos_tabla)
            
            contenido_principal = ft.Column([
                kpis,
                ft.Container(height=20),
                ft.Text("Tendencia Diaria (Ingresos vs Egresos)", size=18, weight=ft.FontWeight.W_800, color=ft.colors.BLUE_800),
                ft.Container(height=10),
                ft.Container(content=barras, height=350, bgcolor=ft.colors.WHITE, border_radius=12, border=ft.border.all(1, ft.colors.GREY_200), padding=15),
                ft.Container(height=30),
                ft.Text("Detalle por Fecha", size=18, weight=ft.FontWeight.W_800, color=ft.colors.BLUE_800),
                ft.Container(height=10),
                ft.Container(content=tabla, height=300, bgcolor=ft.colors.WHITE, border_radius=12, border=ft.border.all(1, ft.colors.GREY_200), padding=10),
            ], spacing=0)

        self.content = ft.Column([
            header,
            selector_banco,
            ft.Container(height=15),
            contenido_principal
        ], scroll=ft.ScrollMode.AUTO)

    def _crear_kpi(self, titulo, valor, color, icono):
        return ft.Container(
            content=ft.Column([
                ft.Icon(icono, color=color, size=24),
                ft.Text(valor, size=20, weight=ft.FontWeight.BOLD, color=color),
                ft.Text(titulo, size=12, color=ft.colors.GREY_600)
            ], spacing=5, alignment=ft.MainAxisAlignment.CENTER),
            bgcolor=ft.colors.WHITE, border_radius=12, padding=20,
            border=ft.border.all(1, ft.colors.GREY_200), expand=True
        )

    def _crear_barras(self, fechas, ingresos, egresos):
        maximo = max(max(ingresos) if ingresos else 0, max(egresos) if egresos else 0)
        if maximo == 0:
            maximo = 1

        barra_max_height = 280
        items = []

        for i, fecha in enumerate(fechas):
            fecha_corta = fecha[-5:]
            ing = ingresos[i] if i < len(ingresos) else 0
            egr = egresos[i] if i < len(egresos) else 0

            h_ing = (ing / maximo) * barra_max_height if ing > 0 else 0
            h_egr = (egr / maximo) * barra_max_height if egr > 0 else 0

            columna = ft.Column([
                ft.Text(f"$ {int(ing):,}", size=9, color=ft.colors.GREEN_700),
                ft.Container(
                    width=25, height=h_ing, bgcolor=ft.colors.GREEN_500, border_radius=4
                ),
                ft.Container(
                    width=25, height=h_egr, bgcolor=ft.colors.RED_500, border_radius=4
                ),
                ft.Text(f"$ {int(egr):,}", size=9, color=ft.colors.RED_700),
                ft.Text(fecha_corta, size=10, color=ft.colors.GREY_600)
            ], spacing=2, alignment=ft.MainAxisAlignment.END)

            items.append(columna)

        return ft.Row(items, scroll=ft.ScrollMode.AUTO, spacing=10, alignment=ft.MainAxisAlignment.START)

    def _crear_tabla(self, datos):
        return ft.DataTable(
            heading_row_color=ft.colors.BLUE_800,
            heading_text_style=ft.TextStyle(color=ft.colors.WHITE, weight=ft.FontWeight.BOLD),
            columns=[
                ft.DataColumn(ft.Text("Fecha")),
                ft.DataColumn(ft.Text("Ingresos"), numeric=True),
                ft.DataColumn(ft.Text("Egresos"), numeric=True),
                ft.DataColumn(ft.Text("Neto"), numeric=True),
            ],
            rows=[
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(str(f))),
                        ft.DataCell(ft.Text(f"$ {i:,.0f}", color=ft.colors.GREEN_700)),
                        ft.DataCell(ft.Text(f"$ {e:,.0f}", color=ft.colors.RED_700)),
                        ft.DataCell(ft.Text(f"$ {i-e:,.0f}", color=ft.colors.BLUE_700 if i >= e else ft.colors.ORANGE_700)),
                    ]
                )
                for f, i, e in datos
            ]
        )