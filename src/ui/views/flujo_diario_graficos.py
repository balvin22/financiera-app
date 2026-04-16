# src/ui/views/flujo_diario_graficos.py
import flet as ft
from src.core.db_manager import DBManager
from src.data_engine.transformers.rules_flujo_diario import procesar_datos_flujo_diario

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

    def build_ui(self):
        # Delegamos todo el cálculo matemático y de BD al transformer
        fechas, saldo_inicial, ingresos, egresos = procesar_datos_flujo_diario(self.banco_seleccionado)
        
        bancos = self.db_manager.get_bancos_disponibles()
        opciones_bancos = [ft.dropdown.Option("TODOS", "Todos los bancos")] + [
            ft.dropdown.Option(b, b.replace("_", " ").title()) for b in bancos
        ]

        header = ft.Column([
            ft.Text("Flujo de Efectivo Diario", size=28, weight=ft.FontWeight.W_900, color=ft.colors.BLUE_900),
            ft.Text("Visualiza la tendencia de ingresos y egresos por día con saldos arrastrados", size=15, color=ft.colors.GREY_700),
            ft.Divider(height=20, color=ft.colors.TRANSPARENT)
        ])

        selector_banco = ft.Dropdown(
            label="Filtrar por banco", width=250, options=opciones_bancos,
            value=self.banco_seleccionado, on_change=lambda e: self.cambiar_banco(e.control.value)
        )

        # Cálculos para los KPIs
        total_saldo_inicial_kpi = saldo_inicial[0] if saldo_inicial else 0.0
        total_ingresos_kpi = sum(ingresos)
        total_egresos_kpi = sum(egresos)
        total_disponible_kpi = total_saldo_inicial_kpi + total_ingresos_kpi
        saldo_neto_kpi = total_disponible_kpi - total_egresos_kpi

        # 3 Tarjetas (Ingresos Unificados, Egresos, Saldo Final)
        kpis = ft.Row([
            self._crear_kpi_ingresos(total_disponible_kpi, total_saldo_inicial_kpi, total_ingresos_kpi),
            self._crear_kpi("Total Egresos", f"$ {total_egresos_kpi:,.0f}", ft.colors.RED_700, ft.icons.TRENDING_DOWN),
            self._crear_kpi("Saldo Final Actual", f"$ {saldo_neto_kpi:,.0f}", ft.colors.PURPLE_700 if saldo_neto_kpi >= 0 else ft.colors.ORANGE_700, ft.icons.ACCOUNT_BALANCE_WALLET),
        ], spacing=15)

        if not fechas:
            contenido_principal = ft.Column([
                ft.Icon(ft.icons.CALENDAR_TODAY, size=80, color=ft.colors.BLUE_200),
                ft.Text("No hay datos diarios registrados", size=20, color=ft.colors.GREY_600),
                ft.Text("Ve al Generador, activa 'Cargue Diario' y dale Guardar", size=14, color=ft.colors.GREY_500)
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        else:
            grafico_barras = self._crear_grafico_flet(fechas, saldo_inicial, ingresos, egresos)
            tabla = self._crear_tabla(fechas, saldo_inicial, ingresos, egresos)
            
            contenido_principal = ft.Column([
                kpis,
                ft.Container(height=20),
                ft.Text("Evolución del Flujo Diario", size=18, weight=ft.FontWeight.W_800, color=ft.colors.BLUE_800),
                ft.Container(height=10),
                ft.Container(content=grafico_barras, height=450, bgcolor=ft.colors.WHITE, border_radius=12, border=ft.border.all(1, ft.colors.GREY_200), padding=20),
                ft.Container(height=30),
                ft.Text("Detalle del Flujo por Fecha", size=18, weight=ft.FontWeight.W_800, color=ft.colors.BLUE_800),
                ft.Container(height=10),
                ft.Container(
                    content=ft.Column([tabla], scroll=ft.ScrollMode.AUTO, expand=True), 
                    height=300, 
                    bgcolor=ft.colors.WHITE, 
                    border_radius=12, 
                    border=ft.border.all(1, ft.colors.GREY_200), 
                    padding=10
                ),
            ], spacing=0)

        self.content = ft.Column([header, selector_banco, ft.Container(height=15), contenido_principal], scroll=ft.ScrollMode.AUTO)

    def _crear_kpi_ingresos(self, total, saldo_ini, ingresos_op):
        return ft.Container(
            content=ft.Column([
                ft.Icon(ft.icons.ACCOUNT_BALANCE, color=ft.colors.GREEN_700, size=24),
                ft.Text(f"$ {total:,.0f}", size=20, weight=ft.FontWeight.BOLD, color=ft.colors.GREEN_700),
                ft.Text("Total Disponible (Mes)", size=12, color=ft.colors.GREY_600),
                ft.Container(height=2),
                ft.Row([
                    ft.Text("Saldo Inicial:", size=10, color=ft.colors.GREY_500),
                    ft.Text(f"$ {saldo_ini:,.0f}", size=10, weight=ft.FontWeight.W_600, color=ft.colors.BLUE_700)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([
                    ft.Text("Ingresos:", size=10, color=ft.colors.GREY_500),
                    ft.Text(f"$ {ingresos_op:,.0f}", size=10, weight=ft.FontWeight.W_600, color=ft.colors.GREEN_700)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ], spacing=2, alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=ft.colors.WHITE, border_radius=12, padding=ft.padding.only(left=20, right=20, top=15, bottom=10),
            border=ft.border.all(1, ft.colors.GREY_200), expand=True
        )

    def _crear_kpi(self, titulo, valor, color, icono):
        return ft.Container(
            content=ft.Column([
                ft.Icon(icono, color=color, size=24),
                ft.Text(valor, size=20, weight=ft.FontWeight.BOLD, color=color),
                ft.Text(titulo, size=12, color=ft.colors.GREY_600),
                ft.Container(height=18) 
            ], spacing=2, alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=ft.colors.WHITE, border_radius=12, padding=ft.padding.only(left=20, right=20, top=15, bottom=10), 
            border=ft.border.all(1, ft.colors.GREY_200), expand=True
        )

    def _crear_grafico_flet(self, fechas, saldo_inicial, ingresos, egresos):
        bar_groups = []
        labels_bottom = []
        max_y = 0
        min_y = 0
        
        for i, fecha in enumerate(fechas):
            si = saldo_inicial[i]
            ing = ingresos[i]
            egr = egresos[i]
            sf = si + ing - egr
            
            dia_max = max(ing, egr, sf)
            dia_min = min(0, sf)
            if dia_max > max_y: max_y = dia_max
            if dia_min < min_y: min_y = dia_min
                
            labels_bottom.append(
                ft.ChartAxisLabel(
                    value=i,
                    label=ft.Text(fecha[-5:], size=11, color=ft.colors.GREY_700, weight=ft.FontWeight.BOLD)
                )
            )
            
            tooltip = f"📅 Fecha: {fecha}\n\n💼 Saldo Inicial: ${si:,.0f}\n🟢 Ingresos: ${ing:,.0f}\n🔴 Egresos: ${egr:,.0f}\n\n➡️ Saldo Final: ${sf:,.0f}"
            
            bar_groups.append(
                ft.BarChartGroup(
                    x=i,
                    bar_rods=[
                        ft.BarChartRod(from_y=0, to_y=ing, color=ft.colors.GREEN_400, width=14, tooltip=tooltip, border_radius=4),
                        ft.BarChartRod(from_y=0, to_y=egr, color=ft.colors.RED_400, width=14, tooltip=tooltip, border_radius=4),
                        ft.BarChartRod(from_y=0, to_y=sf, color=ft.colors.PURPLE_500, width=18, tooltip=tooltip, border_radius=4),
                    ]
                )
            )
            
        left_labels = []
        if max_y > 0:
            step = max_y / 4
            for j in range(5):
                val = j * step
                label_str = f"${val/1_000_000:.1f}M" if val >= 1_000_000 else (f"${val/1000:.0f}k" if val >= 1000 else f"${val:.0f}")
                left_labels.append(ft.ChartAxisLabel(value=val, label=ft.Text(label_str, size=11, color=ft.colors.GREY_500, weight=ft.FontWeight.BOLD)))
                
        chart = ft.BarChart(
            bar_groups=bar_groups,
            bottom_axis=ft.ChartAxis(labels=labels_bottom, labels_size=32),
            left_axis=ft.ChartAxis(labels=left_labels, labels_size=60),
            horizontal_grid_lines=ft.ChartGridLines(color=ft.colors.GREY_200, width=1, dash_pattern=[4, 4]),
            tooltip_bgcolor=ft.colors.BLUE_GREY_900,
            max_y=max_y * 1.1 if max_y > 0 else 100,
            min_y=min_y * 1.1 if min_y < 0 else 0,
            interactive=True,
            expand=True
        )
        
        leyenda = ft.Row([
            ft.Container(width=14, height=14, bgcolor=ft.colors.GREEN_400, border_radius=3),
            ft.Text("Ingresos", size=13, color=ft.colors.GREY_800, weight=ft.FontWeight.W_600),
            ft.Container(width=15),
            ft.Container(width=14, height=14, bgcolor=ft.colors.RED_400, border_radius=3),
            ft.Text("Egresos", size=13, color=ft.colors.GREY_800, weight=ft.FontWeight.W_600),
            ft.Container(width=15),
            ft.Container(width=18, height=14, bgcolor=ft.colors.PURPLE_500, border_radius=4),
            ft.Text("Saldo Final (Acumulado)", size=13, color=ft.colors.GREY_800, weight=ft.FontWeight.W_600),
        ], alignment=ft.MainAxisAlignment.CENTER)
        
        chart_width = max(800, len(fechas) * 90)
        
        return ft.Column([
            leyenda,
            ft.Container(height=15),
            ft.Row([
                ft.Container(content=chart, width=chart_width, height=350, padding=ft.padding.only(right=20, top=10))
            ], scroll=ft.ScrollMode.AUTO, expand=True)
        ], expand=True)

    def _crear_tabla(self, fechas, saldo_inicial, ingresos, egresos):
        rows = []
        for i in range(len(fechas)):
            si = saldo_inicial[i]
            ing = ingresos[i]
            egr = egresos[i]
            sf = si + ing - egr
            
            rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(str(fechas[i]))),
                ft.DataCell(ft.Text(f"$ {si:,.0f}", color=ft.colors.BLUE_700)),
                ft.DataCell(ft.Text(f"$ {ing:,.0f}", color=ft.colors.GREEN_700)),
                ft.DataCell(ft.Text(f"$ {egr:,.0f}", color=ft.colors.RED_700)),
                ft.DataCell(ft.Text(f"$ {sf:,.0f}", color=ft.colors.PURPLE_700 if sf >= 0 else ft.colors.ORANGE_700, weight=ft.FontWeight.W_600)),
            ]))

        return ft.DataTable(
            heading_row_color=ft.colors.BLUE_800,
            heading_text_style=ft.TextStyle(color=ft.colors.WHITE, weight=ft.FontWeight.BOLD),
            columns=[
                ft.DataColumn(ft.Text("Fecha")),
                ft.DataColumn(ft.Text("Saldo Inicial"), numeric=True),
                ft.DataColumn(ft.Text("Ingresos"), numeric=True),
                ft.DataColumn(ft.Text("Egresos"), numeric=True),
                ft.DataColumn(ft.Text("Saldo Final"), numeric=True),
            ],
            rows=rows
        )