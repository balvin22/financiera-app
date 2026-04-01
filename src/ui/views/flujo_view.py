# ui/views/flujo_view.py
import flet as ft
import time
import os
import shutil
import polars as pl  
from src.data_engine.reports.flujo_efectivo import GeneradorFlujoEfectivo
from src.data_engine.extractors.alianza_pdf import AlianzaPdfExtractor
from src.ui.components.tarjeta_banco import TarjetaBanco

class FlujoView(ft.Container):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True
        self.padding = 40
        self.bgcolor = "#F8FAFC" 
        
        self.rutas_archivos = {
            "bancolombia": None, "davivienda": None, "occidente": None,
            "agrario": None, "alianza": None, "caja": None, "caja_bancos": None
        }
        self.banco_actual_picker = None
        self.tarjetas_bancos = {} 

        self.acumulado_pdf_ingresos = 0.0
        self.acumulado_pdf_egresos = 0.0

        # Pickers
        self.file_picker = ft.FilePicker(on_result=self.on_dialog_result)
        self.page.overlay.append(self.file_picker)

        self.save_picker = ft.FilePicker(on_result=self.on_save_result)
        self.page.overlay.append(self.save_picker)
        
        self.pdf_picker = ft.FilePicker(on_result=self.on_pdf_result)
        self.page.overlay.append(self.pdf_picker)

        self.saldos_picker = ft.FilePicker(on_result=self.on_saldos_result)
        self.page.overlay.append(self.saldos_picker)

        self.gastos_picker = ft.FilePicker(on_result=self.on_gastos_result)
        self.page.overlay.append(self.gastos_picker)

        self.aux_prov_picker = ft.FilePicker(on_result=self.on_aux_prov_result)
        self.page.overlay.append(self.aux_prov_picker)
        
        # --- NUEVO PICKER: Auxiliar Nómina 25 ---
        self.aux_nomina_picker = ft.FilePicker(on_result=self.on_aux_nomina_result)
        self.page.overlay.append(self.aux_nomina_picker)

        self.build_ui()

    # ==========================================
    # LÓGICA: CARGAR GASTOS 2335
    # ==========================================
    def on_gastos_result(self, e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            ruta_origen = e.files[0].path
            os.makedirs("local_cache", exist_ok=True)
            ruta_destino = "local_cache/gastos_2335.xlsx"
            try:
                shutil.copy(ruta_origen, ruta_destino)
                self.page.snack_bar = ft.SnackBar(ft.Text("✅ Base 2335 (Gastos) cargada exitosamente."), bgcolor=ft.colors.GREEN_700)
            except Exception as ex:
                self.page.snack_bar = ft.SnackBar(ft.Text(f"❌ Error al cargar Base 2335: {str(ex)}"), bgcolor=ft.colors.RED_700)
            self.page.snack_bar.open = True
            self.page.update()

    # ==========================================
    # LÓGICA: CARGAR AUXILIAR PROVEEDORES 2205 (SUPPLY)
    # ==========================================
    def on_aux_prov_result(self, e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            ruta_origen = e.files[0].path
            os.makedirs("local_cache", exist_ok=True)
            ruta_destino = "local_cache/aux_prov_2205.xlsx"
            try:
                shutil.copy(ruta_origen, ruta_destino)
                self.page.snack_bar = ft.SnackBar(ft.Text("✅ Auxiliar Proveedores (2205) cargado para Supply."), bgcolor=ft.colors.GREEN_700)
            except Exception as ex:
                self.page.snack_bar = ft.SnackBar(ft.Text(f"❌ Error al cargar Auxiliar 2205: {str(ex)}"), bgcolor=ft.colors.RED_700)
            self.page.snack_bar.open = True
            self.page.update()

    # ==========================================
    # LÓGICA: CARGAR AUXILIAR NÓMINA 25 (NUEVO)
    # ==========================================
    def on_aux_nomina_result(self, e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            ruta_origen = e.files[0].path
            os.makedirs("local_cache", exist_ok=True)
            ruta_destino = "local_cache/aux_nomina_25.xlsx"
            try:
                shutil.copy(ruta_origen, ruta_destino)
                self.page.snack_bar = ft.SnackBar(ft.Text("✅ Auxiliar Nómina (25) cargado exitosamente."), bgcolor=ft.colors.GREEN_700)
            except Exception as ex:
                self.page.snack_bar = ft.SnackBar(ft.Text(f"❌ Error al cargar Auxiliar 25: {str(ex)}"), bgcolor=ft.colors.RED_700)
            self.page.snack_bar.open = True
            self.page.update()

    # ==========================================
    # LÓGICA DE AUTO-COMPLETADO DE SALDOS
    # ==========================================
    def on_saldos_result(self, e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            ruta = e.files[0].path
            try:
                df = pl.read_excel(ruta)
                col_banco = "Banco / Caja" if "Banco / Caja" in df.columns else "Origen"
                col_saldo = "Saldo Inicial"
                bancos_mapeados = 0
                if col_saldo not in df.columns:
                    self.page.snack_bar = ft.SnackBar(ft.Text(f"❌ No se encontró la columna '{col_saldo}' en el archivo."), bgcolor=ft.colors.RED_700)
                    self.page.snack_bar.open = True
                    self.page.update()
                    return
                for row in df.iter_rows(named=True):
                    nombre_banco_excel = str(row.get(col_banco, "")).strip().upper()
                    for b_id, tarjeta in self.tarjetas_bancos.items():
                        if b_id.upper() in nombre_banco_excel or nombre_banco_excel in b_id.upper():
                            saldo_encontrado = float(row.get(col_saldo, 0.0))
                            tarjeta.set_saldo(saldo_encontrado)
                            bancos_mapeados += 1
                            break
                self.page.snack_bar = ft.SnackBar(ft.Text(f"✅ ¡Éxito! {bancos_mapeados} Saldos Iniciales extraídos correctamente."), bgcolor=ft.colors.GREEN_700)
            except Exception as ex:
                self.page.snack_bar = ft.SnackBar(ft.Text(f"❌ Error leyendo el archivo: {str(ex)}"), bgcolor=ft.colors.RED_700)
            self.page.snack_bar.open = True
            self.page.update()

    # ==========================================
    # LÓGICA EXISTENTE DE ARCHIVOS
    # ==========================================
    def on_dialog_result(self, e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            ruta_seleccionada = e.files[0].path
            self.rutas_archivos[self.banco_actual_picker] = ruta_seleccionada
            self.tarjetas_bancos[self.banco_actual_picker].marcar_como_cargado()
            self.page.snack_bar = ft.SnackBar(ft.Text(f"¡Extracto de {self.banco_actual_picker.upper()} cargado con éxito!"), bgcolor=ft.colors.GREEN_700)
            self.page.snack_bar.open = True
            self.page.update()

    def abrir_selector(self, banco_id):
        self.banco_actual_picker = banco_id
        self.file_picker.pick_files(dialog_title=f"Selecciona el extracto de {banco_id.upper()}", allowed_extensions=["xlsx", "xls", "csv"])

    def abrir_selector_pdf(self, e):
        self.pdf_picker.pick_files(dialog_title="Selecciona los PDFs de Alianza", allowed_extensions=["pdf"], allow_multiple=True)
        
    def on_pdf_result(self, e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            clave_pdf = "900333755" 
            es_perdida = self.switch_perdida.value
            archivos_exitosos = 0
            
            self.page.snack_bar = ft.SnackBar(ft.Text("Escaneando PDFs... por favor espera."), bgcolor=ft.colors.BLUE_700)
            self.page.snack_bar.open = True
            self.page.update()
            
            for archivo in e.files:
                extractor_pdf = AlianzaPdfExtractor(archivo.path, clave_pdf)
                valores = extractor_pdf.extraer_valores()
                if valores:
                    if es_perdida: self.acumulado_pdf_ingresos -= valores['ingresos']
                    else: self.acumulado_pdf_ingresos += valores['ingresos']
                    self.acumulado_pdf_egresos += valores['egresos']
                    archivos_exitosos += 1

            if archivos_exitosos > 0:
                self.texto_pdf_resumen_ingresos.value = f"$ {self.acumulado_pdf_ingresos:,.2f}"
                self.texto_pdf_resumen_egresos.value = f"$ {self.acumulado_pdf_egresos:,.2f}"
                estado_msj = "RESTADOS (Pérdida)" if es_perdida else "SUMADOS (Ganancia)"
                self.page.snack_bar = ft.SnackBar(ft.Text(f"✅ {archivos_exitosos} PDF(s) procesados. Valores {estado_msj} en memoria."), bgcolor=ft.colors.GREEN_700)
            else:
                self.page.snack_bar = ft.SnackBar(ft.Text("❌ Error leyendo los PDFs. Revisa la clave o el formato."), bgcolor=ft.colors.RED_700)
            
            self.switch_perdida.value = False
            self.page.snack_bar.open = True
            self.page.update()

    def limpiar_escaneo_pdf(self, e):
        self.acumulado_pdf_ingresos = 0.0
        self.acumulado_pdf_egresos = 0.0
        self.texto_pdf_resumen_ingresos.value = "$ 0.00"
        self.texto_pdf_resumen_egresos.value = "$ 0.00"
        self.page.snack_bar = ft.SnackBar(ft.Text("🔄 Memoria del escáner reiniciada a cero."), bgcolor=ft.colors.BLUE_700)
        self.page.snack_bar.open = True
        self.page.update()

    def procesar_flujo(self, e):
        faltantes = [b for b, ruta in self.rutas_archivos.items() if ruta is None]
        if faltantes:
            self.page.snack_bar = ft.SnackBar(ft.Text(f"⚠️ Faltan archivos por cargar: {', '.join(faltantes).upper()}"), bgcolor=ft.colors.ORANGE_800)
            self.page.snack_bar.open = True
            self.page.update()
            return
            
        self.save_picker.save_file(dialog_title="¿Dónde deseas guardar el reporte consolidado?", file_name="Reporte_Flujo_Mensual.xlsx", allowed_extensions=["xlsx"])

    def on_save_result(self, e: ft.FilePickerResultEvent):
        if not e.path: return
            
        self.boton_generar.text = "Calculando finanzas..."
        self.boton_generar.disabled = True
        self.page.update()
        
        try:
            manual_ingresos = float(self.input_ingresos.value.replace("$", "").replace(",", "").strip() or 0)
            manual_egresos = float(self.input_egresos.value.replace("$", "").replace(",", "").strip() or 0)

            total_ingresos_alianza = manual_ingresos + self.acumulado_pdf_ingresos
            total_egresos_alianza = manual_egresos + self.acumulado_pdf_egresos

            ajustes = {
                "ALIANZA": {
                    "ingresos": total_ingresos_alianza,
                    "egresos": total_egresos_alianza
                }
            }
            
            saldos = {}
            for banco_id, tarjeta in self.tarjetas_bancos.items():
                saldos[banco_id.upper()] = tarjeta.obtener_saldo()

            motor = GeneradorFlujoEfectivo(self.rutas_archivos, ajustes_manuales=ajustes, saldos_iniciales=saldos)
            df_global = motor.generar_base_consolidada()
            df_detallado = motor.generar_reporte_detallado(df_global)
            df_resumen = motor.generar_resumen_gerencial(df_global, df_detallado)
            
            os.makedirs("local_cache", exist_ok=True)
            df_global.write_parquet("local_cache/base_global.parquet")
            df_detallado.write_parquet("local_cache/base_detallada.parquet")
            df_resumen_pl = pl.from_pandas(df_resumen)
            df_resumen_pl.write_parquet("local_cache/base_resumen.parquet")

            ruta_excel = e.path if e.path.endswith(".xlsx") else e.path + ".xlsx"
            motor.exportar_a_excel(df_detallado, df_resumen, ruta_excel)
            
            self.boton_generar.text = "¡Reporte Generado con Éxito!"
            self.boton_generar.icon = ft.icons.CHECK_CIRCLE
            self.boton_generar.style = ft.ButtonStyle(bgcolor=ft.colors.GREEN_600, color=ft.colors.WHITE)
            self.page.update()
            
            os.startfile(ruta_excel)
            
            time.sleep(2.5) 
            self.boton_generar.text = "Generar Reporte Excel"
            self.boton_generar.icon = ft.icons.PLAY_ARROW
            self.boton_generar.style = ft.ButtonStyle(bgcolor=ft.colors.BLUE_800, color=ft.colors.WHITE)
            self.boton_generar.disabled = False 
            self.page.update()
            
        except Exception as ex:
            self.page.snack_bar = ft.SnackBar(ft.Text(f"❌ Error interno: {str(ex)}"), bgcolor=ft.colors.RED_800)
            self.page.snack_bar.open = True
            self.boton_generar.text = "Generar Reporte Excel"
            self.boton_generar.disabled = False
            self.boton_generar.style = ft.ButtonStyle(bgcolor=ft.colors.BLUE_800, color=ft.colors.WHITE)
            self.page.update()

    def build_ui(self):
        header = ft.Column([
            ft.Text("Consolidador de Flujo de Efectivo", size=28, weight=ft.FontWeight.W_900, color=ft.colors.BLUE_900),
            ft.Text("Automatiza la lectura de extractos y genera el reporte gerencial en segundos.", size=15, color=ft.colors.GREY_700),
            ft.Divider(height=20, color=ft.colors.TRANSPARENT)
        ])

        # ==========================================
        # PASO 1: BANCOS PRINCIPALES
        # ==========================================
        titulo_tarjetas = ft.Column([
            ft.Text("Paso 1: Extractos Bancarios y Cajas", size=18, weight=ft.FontWeight.W_800, color=ft.colors.BLUE_800),
            ft.Text("Carga obligatoriamente el Excel de cada cuenta principal.", size=13, color=ft.colors.GREY_600),
        ])

        bancos_config = [
            {"id": "bancolombia", "nombre": "Bancolombia", "color": ft.colors.BLUE_700, "logo_path": "src/assets/logos/bancolombia.png", "icon": None},
            {"id": "davivienda", "nombre": "Davivienda", "color": ft.colors.RED_700, "logo_path": "src/assets/logos/davivienda.png", "icon": None},
            {"id": "occidente", "nombre": "Bco. Occidente", "color": ft.colors.BLUE_900, "logo_path": "src/assets/logos/occidente.png", "icon": None},
            {"id": "agrario", "nombre": "Banco Agrario", "color": ft.colors.GREEN_700, "logo_path": "src/assets/logos/agrario.svg", "icon": None},
            {"id": "alianza", "nombre": "Alianza Fid.", "color": ft.colors.TEAL_700, "logo_path": "src/assets/logos/alianza.jpeg", "icon": None},
            {"id": "caja", "nombre": "Caja General", "color": ft.colors.ORANGE_700, "logo_path": None, "icon": ft.icons.MONETIZATION_ON},
            {"id": "caja_bancos", "nombre": "Mov. Bancos (Prov)", "color": ft.colors.PURPLE_700, "logo_path": None, "icon": ft.icons.RECEIPT_LONG}
        ]

        lista_tarjetas = []
        for banco in bancos_config:
            tarjeta = TarjetaBanco(
                banco_id=banco["id"], nombre=banco["nombre"], color=banco["color"], 
                on_cargar_click=self.abrir_selector, icono=banco["icon"], logo_path=banco["logo_path"] 
            )
            self.tarjetas_bancos[banco["id"]] = tarjeta
            lista_tarjetas.append(tarjeta)

        grid_bancos = ft.Row(lista_tarjetas, wrap=True, spacing=20, run_spacing=20)

        # ==========================================
        # PASO 2: BASES AUXILIARES (CON NÓMINA)
        # ==========================================
        titulo_auxiliares = ft.Column([
            ft.Text("Paso 2: Bases Auxiliares y Saldos (Opcional pero Recomendado)", size=18, weight=ft.FontWeight.W_800, color=ft.colors.BLUE_800),
            ft.Text("Sube aquí todos los libros auxiliares que alimentarán el desglose del reporte.", size=13, color=ft.colors.GREY_600),
        ])

        botones_auxiliares = ft.Row([
            ft.ElevatedButton("Extraer Saldos Ant.", icon=ft.icons.AUTO_AWESOME, style=ft.ButtonStyle(bgcolor=ft.colors.BLUE_50, color=ft.colors.BLUE_700), on_click=lambda e: self.saldos_picker.pick_files(dialog_title="Selecciona el reporte del mes anterior", allowed_extensions=["xlsx"])),
            ft.ElevatedButton("Gastos (2335)", icon=ft.icons.RECEIPT_LONG, style=ft.ButtonStyle(bgcolor=ft.colors.PURPLE_50, color=ft.colors.PURPLE_700), on_click=lambda e: self.gastos_picker.pick_files(dialog_title="Selecciona el Auxiliar 2335", allowed_extensions=["xlsx", "xls"])),
            ft.ElevatedButton("Supply (2205)", icon=ft.icons.LOCAL_SHIPPING, style=ft.ButtonStyle(bgcolor=ft.colors.TEAL_50, color=ft.colors.TEAL_700), on_click=lambda e: self.aux_prov_picker.pick_files(dialog_title="Selecciona el Auxiliar 2205", allowed_extensions=["xlsx", "xls"])),
            ft.ElevatedButton("Nómina (25)", icon=ft.icons.PEOPLE, style=ft.ButtonStyle(bgcolor=ft.colors.INDIGO_50, color=ft.colors.INDIGO_700), on_click=lambda e: self.aux_nomina_picker.pick_files(dialog_title="Selecciona el Auxiliar 25", allowed_extensions=["xlsx", "xls"]))
        ], wrap=True, spacing=15)

        panel_auxiliares = ft.Container(
            content=botones_auxiliares, padding=20, bgcolor=ft.colors.WHITE, border_radius=10,
            border=ft.border.all(1, ft.colors.GREY_200)
        )

        # ==========================================
        # PASO 3: CONCILIACIONES EXTRAS
        # ==========================================
        titulo_ajustes = ft.Column([
            ft.Text("Paso 3: Conciliaciones Extras (Alianza Fiduciaria)", size=18, weight=ft.FontWeight.W_800, color=ft.colors.BLUE_800),
            ft.Text("El sistema sumará inteligentemente lo que digites a mano MÁS lo que extraiga de los PDFs.", size=13, color=ft.colors.GREY_600),
        ])

        self.input_ingresos = ft.TextField(label="Ingresos Extras ($)", value="", hint_text="0.00", width=240, height=48, dense=True, content_padding=ft.padding.symmetric(horizontal=10, vertical=10), prefix_text="$ ", text_align=ft.TextAlign.RIGHT, border_color=ft.colors.BLUE_200, focused_border_color=ft.colors.BLUE_600)
        self.input_egresos = ft.TextField(label="Egresos Extras ($)", value="", hint_text="0.00", width=240, height=48, dense=True, content_padding=ft.padding.symmetric(horizontal=10, vertical=10), prefix_text="$ ", text_align=ft.TextAlign.RIGHT, border_color=ft.colors.BLUE_200, focused_border_color=ft.colors.BLUE_600)
        self.switch_perdida = ft.Switch(label="Restar Valores (Fondo en Pérdida)", value=False, active_color=ft.colors.RED_600)
        
        boton_pdf = ft.ElevatedButton("Escanear Extractos PDF", icon=ft.icons.DOCUMENT_SCANNER, on_click=self.abrir_selector_pdf, style=ft.ButtonStyle(bgcolor=ft.colors.BLUE_700, color=ft.colors.WHITE))
        boton_limpiar = ft.IconButton(icon=ft.icons.REFRESH, icon_color=ft.colors.GREY_500, on_click=self.limpiar_escaneo_pdf)
        
        self.texto_pdf_resumen_ingresos = ft.Text("$ 0.00", size=16, weight=ft.FontWeight.BOLD, color=ft.colors.GREEN_700)
        self.texto_pdf_resumen_egresos = ft.Text("$ 0.00", size=16, weight=ft.FontWeight.BOLD, color=ft.colors.RED_700)
        
        panel_memoria = ft.Container(
            padding=15, bgcolor=ft.colors.BLUE_50, border_radius=8, border=ft.border.all(1, ft.colors.BLUE_100),
            content=ft.Row([
                ft.Icon(ft.icons.MEMORY, color=ft.colors.BLUE_700),
                ft.Column([
                    ft.Text("Valores extraídos de PDFs (Listos para sumarse):", weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_900, size=13),
                    ft.Row([ft.Text("Ingresos:", size=14), self.texto_pdf_resumen_ingresos, ft.Text(" |  Egresos:", size=14), self.texto_pdf_resumen_egresos])
                ]),
                ft.Container(expand=True), boton_limpiar
            ])
        )

        panel_ajustes = ft.Container(
            bgcolor=ft.colors.WHITE, border_radius=15, padding=25, margin=ft.margin.only(top=10, bottom=30),
            border=ft.border.all(1, ft.colors.GREY_200), shadow=ft.BoxShadow(blur_radius=15, color=ft.colors.BLACK12, offset=ft.Offset(0, 5)),
            content=ft.Column([
                ft.Row([
                    ft.Column([ft.Text("1. Valores Manuales", weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_900), ft.Row([self.input_ingresos, self.input_egresos])]),
                    ft.VerticalDivider(width=40, color=ft.colors.GREY_300),
                    ft.Column([ft.Text("2. Escáner Inteligente", weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_900), ft.Row([boton_pdf, self.switch_perdida])])
                ], vertical_alignment=ft.CrossAxisAlignment.START),
                ft.Divider(height=25, color=ft.colors.TRANSPARENT),
                panel_memoria
            ])
        )

        titulo_generar = ft.Column([
            ft.Text("Paso 4: Generación del Reporte", size=18, weight=ft.FontWeight.W_800, color=ft.colors.BLUE_800, text_align=ft.TextAlign.CENTER),
            ft.Container(height=5)
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        self.boton_generar = ft.ElevatedButton("Generar Reporte Excel", icon=ft.icons.PLAY_ARROW, height=60, width=400, style=ft.ButtonStyle(bgcolor=ft.colors.BLUE_800, color=ft.colors.WHITE, shape=ft.RoundedRectangleBorder(radius=10)), on_click=self.procesar_flujo)

        self.content = ft.Column([
            header, 
            titulo_tarjetas, ft.Container(height=5), grid_bancos, ft.Divider(height=20, color=ft.colors.GREY_300),
            titulo_auxiliares, panel_auxiliares, ft.Divider(height=20, color=ft.colors.GREY_300),
            titulo_ajustes, panel_ajustes, ft.Divider(height=20, color=ft.colors.TRANSPARENT),
            ft.Column([titulo_generar, self.boton_generar], horizontal_alignment=ft.CrossAxisAlignment.CENTER), ft.Container(height=40)
        ], scroll=ft.ScrollMode.AUTO)