# src/ui/views/flujo_diario_graficos.py
import flet as ft
import calendar
import threading
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
        self.on_rebuild = None
        self.banco_seleccionado = "TODOS"
        self.mes_calendario = None
        self.fecha_seleccionada = None
        self.mostrar_calendario = False
        self.excluir_traslados = True
        self.excluir_anulados = True
        self.excluir_ajuste_dd = True
        self.excluir_caja_bancos = True

        self._data_cache = None
        self._data_key = None
        self._tabla_contenedor = ft.Container(height=350)
        self._grafico_contenedor = ft.Container(height=450)
        self._calendario_contenedor = ft.Container(height=0)
        self._info_seleccion = ft.Container(height=0)
        self._cargado = False
        self.build_ui()

    def _get_data_key(self):
        return (self.banco_seleccionado, self.mes_calendario, self.excluir_traslados,
                self.excluir_anulados, self.excluir_ajuste_dd, self.excluir_caja_bancos)

    def _load_data(self):
        key = self._get_data_key()
        if self._data_cache is not None and self._data_key == key:
            return self._data_cache

        dias_disponibles = []
        if self.mes_calendario:
            dias_disponibles = self.db_manager.get_dias_disponibles(self.mes_calendario, self.banco_seleccionado)

        filtro_mes = None
        filtro_fecha = None
        if self.fecha_seleccionada:
            filtro_fecha = self.fecha_seleccionada
        elif self.mes_calendario:
            filtro_mes = self.mes_calendario

        fechas, saldos_ini, ing_op, ing_tr, egr_op, egr_tr, saldos_fin, ing_neto = procesar_datos_flujo_diario(
            self.banco_seleccionado, mes_filtro=filtro_mes, fecha_exacta=filtro_fecha,
            excluir_traslados=self.excluir_traslados, excluir_anulados=self.excluir_anulados,
            excluir_ajuste_dd=self.excluir_ajuste_dd, excluir_caja_bancos=self.excluir_caja_bancos
        )

        self._data_cache = (dias_disponibles, fechas, saldos_ini, ing_op, ing_tr, egr_op, egr_tr, saldos_fin, ing_neto)
        self._data_key = key
        return self._data_cache

    def _invalidar_cache(self):
        self._data_cache = None
        self._data_key = None

    def seleccionar_fecha(self, fecha):
        if self.fecha_seleccionada == fecha:
            self.fecha_seleccionada = None
        else:
            self.fecha_seleccionada = fecha
        self._actualizar_calendario_y_seleccion()

    def cerrar_calendario(self):
        self.mostrar_calendario = False
        self._actualizar_calendario_y_seleccion()

    def _actualizar_calendario_y_seleccion(self):
        if self.mes_calendario and self.mostrar_calendario:
            dias = self._data_cache[0] if self._data_cache else []
            self._calendario_contenedor.content = self._crear_calendario(self.mes_calendario, dias)
            self._calendario_contenedor.height = None
        else:
            self._calendario_contenedor.content = None
            self._calendario_contenedor.height = 0

        if self.fecha_seleccionada:
            self._info_seleccion.content = ft.Row([
                ft.Icon(ft.icons.CALENDAR_MONTH, size=18, color=ft.colors.BLUE_800),
                ft.Text(f"Mostrando detalle del día: {self.fecha_seleccionada}",
                        size=14, weight=ft.FontWeight.W_700, color=ft.colors.BLUE_800),
                ft.Container(width=10),
                ft.IconButton(
                    icon=ft.icons.CLOSE, icon_size=16, icon_color=ft.colors.GREY_500,
                    tooltip="Quitar filtro de fecha",
                    on_click=lambda e: self.seleccionar_fecha(self.fecha_seleccionada),
                    width=28, height=28
                )
            ])
            self._info_seleccion.height = None
        else:
            self._info_seleccion.content = None
            self._info_seleccion.height = 0

        try:
            self.update()
        except:
            pass

    def _formatear_mes(self, yyyy_mm):
        anio, mes_num = yyyy_mm.split("-")
        nombre = calendar.month_name[int(mes_num)]
        return f"{nombre.capitalize()} {anio}"

    def _crear_calendario(self, mes, dias_disponibles):
        anio, mes_num = map(int, mes.split("-"))
        _, ultimo_dia = calendar.monthrange(anio, mes_num)
        primer_dia_semana = calendar.weekday(anio, mes_num, 1)

        dias_set = set(dias_disponibles)
        celdas = []
        for _ in range(primer_dia_semana):
            celdas.append(ft.Container(width=38, height=38))

        for dia in range(1, ultimo_dia + 1):
            fecha_str = f"{mes}-{dia:02d}"
            disponible = fecha_str in dias_set
            seleccionado = fecha_str == self.fecha_seleccionada

            if disponible:
                celdas.append(
                    ft.Container(
                        content=ft.Text(str(dia), size=13, weight=ft.FontWeight.BOLD,
                                        color=ft.colors.WHITE if seleccionado else ft.colors.BLUE_800),
                        width=38, height=38,
                        alignment=ft.alignment.center,
                        bgcolor=ft.colors.BLUE_800 if seleccionado else ft.colors.BLUE_50,
                        border_radius=8,
                        ink=True,
                        on_click=lambda e, f=fecha_str: self.seleccionar_fecha(f),
                    )
                )
            else:
                celdas.append(
                    ft.Container(
                        content=ft.Text(str(dia), size=13, color=ft.colors.GREY_300),
                        width=38, height=38,
                        alignment=ft.alignment.center,
                    )
                )

        dias_semana = ft.Row(
            [ft.Container(content=ft.Text(d, size=12, weight=ft.FontWeight.BOLD, color=ft.colors.GREY_500),
                          width=38, height=30, alignment=ft.alignment.center)
             for d in ["L", "M", "M", "J", "V", "S", "D"]],
            spacing=2
        )
        grid_filas = []
        for i in range(0, len(celdas), 7):
            fila = celdas[i:i + 7]
            grid_filas.append(ft.Row(fila, spacing=2))

        encabezado = ft.Row([
            ft.Container(expand=True),
            ft.Text(self._formatear_mes(mes), size=16, weight=ft.FontWeight.W_800, color=ft.colors.BLUE_800),
            ft.Container(expand=True),
            ft.IconButton(
                icon=ft.icons.CLOSE, icon_size=18, icon_color=ft.colors.GREY_500,
                tooltip="Cerrar calendario",
                on_click=lambda e: self.cerrar_calendario(),
                width=30, height=30,
            ),
        ])

        return ft.Container(
            content=ft.Column([encabezado, ft.Container(height=5), dias_semana, *grid_filas], spacing=1),
            padding=12, bgcolor=ft.colors.WHITE, border_radius=12,
            border=ft.border.all(1, ft.colors.GREY_200),
            width=330
        )

    def build_ui(self, banco="TODOS", mes=None):
        self.banco_seleccionado = banco
        if mes is not None:
            if mes != self.mes_calendario:
                self.fecha_seleccionada = None
            self.mes_calendario = mes

        dias_disponibles, fechas, saldos_ini, ing_op, ing_tr, egr_op, egr_tr, saldos_fin, ing_neto = self._load_data()

        # KPIs
        total_saldo_inicial_kpi = saldos_ini[0] if saldos_ini else 0.0
        total_ingresos_kpi = sum(ing_neto)
        total_egresos_kpi = sum(egr_op)
        total_disponible_kpi = total_saldo_inicial_kpi + total_ingresos_kpi
        saldo_neto_kpi = saldos_fin[-1] if saldos_fin else 0.0

        # Calendario
        if self.mes_calendario and self.mostrar_calendario:
            self._calendario_contenedor.content = self._crear_calendario(self.mes_calendario, dias_disponibles)
            self._calendario_contenedor.height = None
        else:
            self._calendario_contenedor.content = None
            self._calendario_contenedor.height = 0

        # Indicador de seleccion
        if self.fecha_seleccionada:
            self._info_seleccion.content = ft.Row([
                ft.Icon(ft.icons.CALENDAR_MONTH, size=18, color=ft.colors.BLUE_800),
                ft.Text(f"Mostrando detalle del día: {self.fecha_seleccionada}",
                        size=14, weight=ft.FontWeight.W_700, color=ft.colors.BLUE_800),
                ft.Container(width=10),
                ft.IconButton(
                    icon=ft.icons.CLOSE, icon_size=16, icon_color=ft.colors.GREY_500,
                    tooltip="Quitar filtro de fecha",
                    on_click=lambda e: self.seleccionar_fecha(self.fecha_seleccionada),
                    width=28, height=28
                )
            ])
            self._info_seleccion.height = None
        else:
            self._info_seleccion.content = None
            self._info_seleccion.height = 0

        # Cuerpo: grafico + tabla
        if not fechas:
            body = ft.Column([
                ft.Icon(ft.icons.CALENDAR_TODAY, size=80, color=ft.colors.BLUE_200),
                ft.Text("No hay datos diarios registrados", size=20, color=ft.colors.GREY_600),
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
            self.content = ft.Column([
                self._calendario_contenedor,
                ft.Container(height=10),
                self._info_seleccion,
                ft.Divider(height=10, color=ft.colors.TRANSPARENT),
                body,
            ], scroll=ft.ScrollMode.AUTO)
        else:
            total_ingresos_arr = [o + t for o, t in zip(ing_op, ing_tr)]
            total_egresos_arr = [o + t for o, t in zip(egr_op, egr_tr)]

            grafico_barras = self._crear_grafico_flet(fechas, saldos_ini, total_ingresos_arr, total_egresos_arr, saldos_fin)
            tabla_personalizada = self._crear_tabla(fechas, saldos_ini, ing_op, ing_tr, egr_op, egr_tr, saldos_fin)

            self._grafico_contenedor.content = ft.Container(
                content=grafico_barras, height=450,
                bgcolor=ft.colors.WHITE, border_radius=12,
                border=ft.border.all(1, ft.colors.GREY_200), padding=20
            )
            self._tabla_contenedor.content = tabla_personalizada

            self.content = ft.Column([
                self._calendario_contenedor,
                ft.Container(height=10),
                self._info_seleccion,
                ft.Divider(height=10, color=ft.colors.TRANSPARENT),
                ft.Column([
                    ft.Text("Evolución del Flujo Diario", size=18, weight=ft.FontWeight.W_800, color=ft.colors.BLUE_800),
                    ft.Container(height=10),
                    self._grafico_contenedor,
                    ft.Container(height=30),
                    ft.Text("Detalle del Flujo por Fecha", size=18, weight=ft.FontWeight.W_800, color=ft.colors.BLUE_800),
                    ft.Container(height=10),
                    self._tabla_contenedor,
                ], spacing=0),
            ], scroll=ft.ScrollMode.AUTO)

        self._cargado = True

    def _crear_grafico_flet(self, fechas, saldo_inicial, ingresos, egresos, saldo_final):
        bar_groups = []
        labels_bottom = []
        max_y = 0
        min_y = 0

        for i, fecha in enumerate(fechas):
            si = saldo_inicial[i]
            ing = ingresos[i]
            egr = egresos[i]
            sf = saldo_final[i]

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

    def _crear_tabla(self, fechas, saldos_ini, ing_op, ing_tr, egr_op, egr_tr, saldos_fin):
        def _celda(texto, color, es_numero=True, bold=False):
            return ft.Container(
                content=ft.Text(texto, color=color, weight=ft.FontWeight.BOLD if bold else ft.FontWeight.NORMAL, size=13),
                expand=2 if es_numero else 1.5,
                alignment=ft.alignment.center_right if es_numero else ft.alignment.center_left,
                padding=ft.padding.symmetric(horizontal=5)
            )

        header_row = ft.Row([
            _celda("Fecha", ft.colors.WHITE, False, True),
            _celda("Saldo Inicial", ft.colors.WHITE, True, True),
            _celda("Ingresos Op.", ft.colors.WHITE, True, True),
            _celda("Ingr. Traslado", ft.colors.WHITE, True, True),
            _celda("Egresos Op.", ft.colors.WHITE, True, True),
            _celda("Egr. Traslado", ft.colors.WHITE, True, True),
            _celda("Saldo Final", ft.colors.WHITE, True, True),
        ])
        header_container = ft.Container(
            content=header_row, bgcolor=ft.colors.BLUE_800,
            padding=ft.padding.symmetric(horizontal=15, vertical=12),
            border_radius=ft.border_radius.only(top_left=8, top_right=8)
        )

        filas = []
        for i in range(len(fechas)):
            row = ft.Container(
                content=ft.Row([
                    _celda(str(fechas[i]), ft.colors.BLACK87, False),
                    _celda(f"$ {saldos_ini[i]:,.0f}", ft.colors.BLUE_700, True),
                    _celda(f"$ {ing_op[i]:,.0f}", ft.colors.GREEN_700, True),
                    _celda(f"$ {ing_tr[i]:,.0f}", ft.colors.TEAL_700, True),
                    _celda(f"$ {egr_op[i]:,.0f}", ft.colors.RED_700, True),
                    _celda(f"$ {egr_tr[i]:,.0f}", ft.colors.DEEP_ORANGE_700, True),
                    _celda(f"$ {saldos_fin[i]:,.0f}", ft.colors.PURPLE_700 if saldos_fin[i] >= 0 else ft.colors.RED_900, True, True),
                ]),
                padding=ft.padding.symmetric(horizontal=15, vertical=12),
                border=ft.border.only(bottom=ft.border.BorderSide(1, ft.colors.GREY_200))
            )
            filas.append(row)

        body_scroll = ft.Column(filas, scroll=ft.ScrollMode.AUTO, expand=True)

        tot_ini = saldos_ini[0] if saldos_ini else 0.0
        tot_ing_op = sum(ing_op)
        tot_ing_tr = sum(ing_tr)
        tot_egr_op = sum(egr_op)
        tot_egr_tr = sum(egr_tr)
        tot_fin = saldos_fin[-1] if saldos_fin else 0.0

        footer_row = ft.Row([
            _celda("TOTALES", ft.colors.WHITE, False, True),
            _celda(f"$ {tot_ini:,.0f}", ft.colors.WHITE, True, True),
            _celda(f"$ {tot_ing_op:,.0f}", ft.colors.WHITE, True, True),
            _celda(f"$ {tot_ing_tr:,.0f}", ft.colors.WHITE, True, True),
            _celda(f"$ {tot_egr_op:,.0f}", ft.colors.WHITE, True, True),
            _celda(f"$ {tot_egr_tr:,.0f}", ft.colors.WHITE, True, True),
            _celda(f"$ {tot_fin:,.0f}", ft.colors.WHITE, True, True),
        ])
        footer_container = ft.Container(
            content=footer_row, bgcolor=ft.colors.BLUE_900,
            padding=ft.padding.symmetric(horizontal=15, vertical=12),
            border_radius=ft.border_radius.only(bottom_left=8, bottom_right=8)
        )

        return ft.Container(
            content=ft.Column([
                header_container,
                ft.Container(content=body_scroll, expand=True, bgcolor=ft.colors.WHITE),
                footer_container
            ], spacing=0, expand=True),
            height=350,
            border_radius=8,
            border=ft.border.all(1, ft.colors.GREY_300),
            clip_behavior=ft.ClipBehavior.HARD_EDGE
        )
