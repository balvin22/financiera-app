# ui/views/flujo_view.py
import flet as ft
import threading
import time
import os
import sys
import subprocess
import pandas as pd
import polars as pl
import sqlite3
from src.core.db_manager import DBManager
from src.data_engine.reports.flujo_efectivo import GeneradorFlujoEfectivo
from src.utils.data_loader import DataLoader
from src.utils.file_loader import FileLoader
from src.ui.components.tarjeta_banco import TarjetaBanco
from src.utils.pdf_processor import PdfProcessor

class FlujoView(ft.Container):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True
        self.padding = 40
        self.bgcolor = "#F8FAFC" 
        
        self.tarjetas_bancos = {} 
        self.pdf_processor = PdfProcessor()
        self.db_manager = DBManager()

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
        self.aux_nomina_picker = ft.FilePicker(on_result=self.on_aux_nomina_result)
        self.page.overlay.append(self.aux_nomina_picker)
        self.caja_bancos_picker = ft.FilePicker(on_result=self.on_caja_bancos_result)
        self.page.overlay.append(self.caja_bancos_picker)

        self.acumulado_pdf_egresos = 0.0
        self.acumulado_pdf_ingresos = 0.0
        self.rutas_archivos = {
            "bancolombia": None, "davivienda": None, "occidente": None,
            "agrario": None, "alianza": None, "caja": None
        }
        self.banco_actual_picker = None
        self.tipo_cargue = "mensual"
        self.mes_mensual = None
        self.fechas_en_archivos = set()

        self.build_ui()

    def cambiar_tipo_cargue(self, tipo):
        self.tipo_cargue = tipo
        self.switch_mensual.value = (tipo == "mensual")
        self.switch_diario.value = (tipo == "diario")
        self.selector_mes.visible = (tipo == "mensual")
        if tipo == "mensual":
            meses = DBManager().get_meses_disponibles()
            self.selector_mes.options = [ft.dropdown.Option(m, m) for m in meses]
            if meses:
                self.mes_mensual = meses[-1]
                self.selector_mes.value = meses[-1]
        
        if tipo == "diario":
            # --- MODO DIARIO: Guardar en BD ---
            self.info_diario.visible = True
            
            # 1. MOSTRAR tarjetas de bancos
            self.paso1_container.visible = True
            self.mensaje_bd.visible = False
            
            # 2. OCULTAR auxiliares
            self.titulo_auxiliares.visible = False
            self.paso2_container.visible = False
            
            # 3. MOSTRAR ajustes de Alianza (PDFs/Manual) para la BD
            self.titulo_ajustes.visible = True
            self.paso3_container.visible = True
            
            self.boton_generar.text = "Guardar Flujo Diario"
            self.boton_generar.icon = ft.icons.SAVE
            self.boton_generar.style = ft.ButtonStyle(bgcolor=ft.colors.AMBER_600, color=ft.colors.WHITE)
            
        else:
            # --- MODO MENSUAL: Leer de BD y armar reporte ---
            self.info_diario.visible = False
            
            # 1. OCULTAR bancos (mostrar aviso de que lee de SQLite)
            self.paso1_container.visible = False
            self.mensaje_bd.visible = True
            
            # 2. MOSTRAR auxiliares
            self.titulo_auxiliares.visible = True
            self.paso2_container.visible = True
            
            # 3. OCULTAR ajustes de Alianza (ya están en la BD)
            self.titulo_ajustes.visible = False
            self.paso3_container.visible = False
            
            self.boton_generar.text = "Generar Reporte Excel"
            self.boton_generar.icon = ft.icons.PLAY_ARROW
            self.boton_generar.style = ft.ButtonStyle(bgcolor=ft.colors.BLUE_800, color=ft.colors.WHITE)
            
        self.page.update()

    def on_gastos_result(self, e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            exito = FileLoader.copy_to_cache(e.files[0].path, "gastos_2335.xlsx")
            if exito and self.mes_mensual:
                try:
                    df = pd.read_excel(e.files[0].path)
                    df.columns = df.columns.str.strip().str.upper()
                    if 'MCNTIPODOC' in df.columns and 'MCNNUMEDOC' in df.columns and 'MCNVALDEBI' in df.columns:
                        mapeo = DataLoader.load_cuentas_2335()
                        registros = []
                        for _, row in df.iterrows():
                            v = row.get('MCNVALDEBI')
                            v = float(v) if pd.notna(v) and v else 0.0
                            if v > 0:
                                num = str(row.get('MCNNUMEDOC', '')).strip().replace('.0','')
                                tipo = str(row.get('MCNTIPODOC', '')).strip()
                                cuenta = str(row.get('MCNCUENTA', '')).strip()
                                cat = mapeo.get(cuenta[:6] if len(cuenta)>=6 else cuenta, "Otros Gastos 2335")
                                registros.append({"tipo_doc":tipo,"num_doc":num,"cuenta":cuenta,"categoria":cat,"valor":v,"detalle":str(row.get('MCNDETALLE',''))[:200]})
                        DBManager().guardar_aux_gastos(self.mes_mensual, registros)
                except:
                    import traceback; traceback.print_exc()
            self._mostrar_snack("✅ Base 2335 (Gastos) cargada exitosamente." if exito else "❌ Error al cargar Base 2335", exito)

    def on_aux_prov_result(self, e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            exito = FileLoader.copy_to_cache(e.files[0].path, "aux_prov_2205.xlsx")
            self._mostrar_snack("✅ Auxiliar Proveedores (2205) cargado para Supply." if exito else "❌ Error al cargar Auxiliar 2205", exito)

    def on_aux_nomina_result(self, e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            exito = FileLoader.copy_to_cache(e.files[0].path, "aux_nomina_25.xlsx")
            if exito and self.mes_mensual:
                try:
                    df = pd.read_excel(e.files[0].path)
                    df.columns = df.columns.str.strip().str.upper()
                    registros = []
                    nomina_caja = {}
                    mapeo_cajas, _ = DataLoader.load_mapeos_caja()
                    for _, row in df.iterrows():
                        v = row.get('MCNVALDEBI')
                        v = float(v) if pd.notna(v) and v else 0.0
                        if v > 0:
                            num = str(row.get('MCNNUMEDOC', '')).strip().replace('.0','')
                            tipo = str(row.get('MCNTIPODOC', '')).strip()
                            cco = str(row.get('MCNCEDULA', '')).strip()
                            empleado = str(row.get('MCNTRABAJADOR', row.get('MCNDETALLE',''))).strip().title()[:100]
                            registros.append({"tipo_doc":tipo,"num_doc":num,"caja_codigo":cco,"caja_nombre":"","empleado":empleado,"valor":v,"detalle":str(row.get('MCNDETALLE',''))[:200]})
                            if empleado:
                                caja_nom = mapeo_cajas.get(cco[:5] if len(cco)>=5 else cco, "SIN CAJA")
                                key = caja_nom.upper()
                                if key not in nomina_caja: nomina_caja[key] = {"caja":key, "empleado":empleado, "valor":0}
                                nomina_caja[key]["valor"] += v
                    db = DBManager()
                    db.guardar_aux_nomina(self.mes_mensual, registros)
                    db.guardar_nomina_por_caja(self.mes_mensual, list(nomina_caja.values()))
                except:
                    import traceback; traceback.print_exc()
            self._mostrar_snack("✅ Auxiliar Nómina (25) cargado exitosamente." if exito else "❌ Error al cargar Auxiliar 25", exito)

    def on_caja_bancos_result(self, e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            exito = FileLoader.copy_to_cache(e.files[0].path, "caja_bancos.xlsx")
            self._mostrar_snack("✅ Aux. caja bancos cargado exitosamente." if exito else "❌ Error al cargar Aux. caja bancos", exito)

    def _mostrar_snack(self, mensaje: str, exitoso: bool):
        self.page.snack_bar = ft.SnackBar(ft.Text(mensaje), bgcolor=ft.colors.GREEN_700 if exitoso else ft.colors.RED_700)
        self.page.snack_bar.open = True
        self.page.update()

    def _abrir_archivo(self, ruta: str):
        try:
            if sys.platform == "win32": os.startfile(ruta)
            elif sys.platform == "darwin": subprocess.run(["open", ruta], check=True)
            else: subprocess.run(["xdg-open", ruta], check=True)
        except Exception as e:
            self._mostrar_snack(f"No se pudo abrir el archivo: {e}", False)

    def on_saldos_result(self, e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            ruta = e.files[0].path
            try:
                import pandas as pd
                df = pd.read_excel(ruta)
                
                col_banco = "Banco / Caja" if "Banco / Caja" in df.columns else "Origen"
                col_saldo = "Saldo Inicial"
                bancos_mapeados = 0
                if col_saldo not in df.columns:
                    self._mostrar_snack(f"❌ No se encontró la columna '{col_saldo}'", False)
                    return
                
                for index, row in df.iterrows():
                    nombre_banco_excel = str(row.get(col_banco, "")).strip().upper()
                    for b_id, tarjeta in self.tarjetas_bancos.items():
                        if b_id.upper() in nombre_banco_excel or nombre_banco_excel in b_id.upper():
                            tarjeta.set_saldo(float(row.get(col_saldo, 0.0)))
                            bancos_mapeados += 1
                            break
                self._mostrar_snack(f"✅ ¡Éxito! {bancos_mapeados} Saldos Iniciales extraídos.", True)
            except Exception as ex:
                self._mostrar_snack(f"❌ Error leyendo el archivo: {str(ex)}", False)

    def on_dialog_result(self, e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            ruta_seleccionada = e.files[0].path
            self.rutas_archivos[self.banco_actual_picker] = ruta_seleccionada
            self.tarjetas_bancos[self.banco_actual_picker].marcar_como_cargado()
            self._mostrar_snack(f"¡Extracto de {self.banco_actual_picker.upper()} cargado con éxito!", True)

    def abrir_selector(self, banco_id):
        self.banco_actual_picker = banco_id
        self.file_picker.pick_files(dialog_title=f"Selecciona el extracto de {banco_id.upper()}", allowed_extensions=["xlsx", "xls", "csv"])

    def abrir_selector_pdf(self, e):
        self.pdf_picker.pick_files(dialog_title="Selecciona los PDFs de Alianza", allowed_extensions=["pdf"], allow_multiple=True)
        
    def on_pdf_result(self, e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            es_perdida = self.switch_perdida.value
            self._mostrar_snack("Escaneando PDFs... por favor espera.", True)
            rutas = [archivo.path for archivo in e.files]
            resultado = self.pdf_processor.procesar_archivos(rutas, es_perdida)
            self.acumulado_pdf_ingresos = resultado["ingresos"]
            self.acumulado_pdf_egresos = resultado["egresos"]
            
            if resultado["archivos_procesados"] > 0:
                self.texto_pdf_resumen_ingresos.value = self.pdf_processor.formatear_dinero(self.acumulado_pdf_ingresos)
                self.texto_pdf_resumen_egresos.value = self.pdf_processor.formatear_dinero(self.acumulado_pdf_egresos)
                estado_msj = self.pdf_processor.get_estado_mensaje(es_perdida)
                self._mostrar_snack(f"✅ {resultado['archivos_procesados']} PDF(s) procesados. Valores {estado_msj} en memoria.", True)
            else:
                self._mostrar_snack("❌ Error leyendo los PDFs. Revisa la clave o el formato.", False)
            self.switch_perdida.value = False

    def limpiar_escaneo_pdf(self, e):
        self.acumulado_pdf_ingresos = 0.0
        self.acumulado_pdf_egresos = 0.0
        self.texto_pdf_resumen_ingresos.value = "$ 0.00"
        self.texto_pdf_resumen_egresos.value = "$ 0.00"
        self._mostrar_snack("🔄 Memoria del escáner reiniciada a cero.", True)

    def procesar_flujo(self, e):
        if self.tipo_cargue == "diario":
            self._procesar_flujo_diario()
        else:
            self._procesar_flujo_mensual(e)

    def _procesar_flujo_diario(self):
        manual_ingresos = float(self.input_ingresos.value.replace("$", "").replace(",", "").strip() or 0)
        manual_egresos = float(self.input_egresos.value.replace("$", "").replace(",", "").strip() or 0)
        
        archivos_cargados = [ruta for ruta in self.rutas_archivos.values() if ruta is not None]
        tiene_ajustes = (manual_ingresos > 0 or manual_egresos > 0 or self.acumulado_pdf_ingresos > 0 or self.acumulado_pdf_egresos > 0)

        if not archivos_cargados and not tiene_ajustes:
            self._mostrar_snack("⚠️ Carga al menos un archivo Excel o PDF primero", False)
            return

        from src.core.db_manager import DBManager as _DB
        tiene_saldo_inicial = _DB().tiene_saldos_diarios()

        if tiene_saldo_inicial:
            saldos_dict = {}
        else:
            saldos_dict = {}
            for banco_id, tarjeta in self.tarjetas_bancos.items():
                saldo = tarjeta.obtener_saldo()
                if saldo > 0:
                    saldos_dict[banco_id.upper()] = saldo
                    saldos_dict[banco_id.upper().replace("_", " ")] = saldo

        self._mostrar_snack("Calculando flujo diario...", True)
        self.boton_generar.disabled = True
        self.boton_generar.text = "Guardando..."
        self.page.update()

        def _ejecutar():
            try:
                ajustes = {
                    "ALIANZA": {
                        "ingresos": manual_ingresos + self.acumulado_pdf_ingresos,
                        "egresos": manual_egresos + self.acumulado_pdf_egresos
                    }
                }
                motor = GeneradorFlujoEfectivo(self.rutas_archivos, ajustes_manuales=ajustes, saldos_iniciales=saldos_dict)
                fechas_guardadas = motor.generar_y_guardar_flujo_diario()
                if self.page:
                    if fechas_guardadas > 0:
                        self._mostrar_snack(f"✅ Flujo diario guardado para {fechas_guardadas} fecha(s)", True)
                        self._resetear_formulario(skip_update=True)
                        self.limpiar_escaneo_pdf(None)
                    else:
                        self._mostrar_snack("❌ Los archivos no generaron datos válidos.", False)
            except Exception as ex:
                import traceback
                traceback.print_exc()
                if self.page:
                    self._mostrar_snack(f"Error: {str(ex)}", False)
            finally:
                self.boton_generar.disabled = False
                self.boton_generar.text = "Guardar Flujo Diario"
                if self.page:
                    self.page.update()

        threading.Thread(target=_ejecutar, daemon=True).start()

    def _resetear_formulario(self, skip_update=False):
        self.rutas_archivos = {k: None for k in self.rutas_archivos}
        for tarjeta in self.tarjetas_bancos.values():
            tarjeta.limpiar()
        if not skip_update and self.page:
            self.page.update()

    def _procesar_flujo_mensual(self, e):
        try:
            if not self.db_manager.tiene_movimientos():
                self._mostrar_snack("⚠️ La Base de Datos está vacía. Haz un Cargue Diario primero.", False)
                return
        except Exception:
            self._mostrar_snack("⚠️ Base de Datos no encontrada. Haz un Cargue Diario primero.", False)
            return

        self.save_picker.save_file(dialog_title="¿Dónde deseas guardar el reporte consolidado?", file_name="Reporte_Flujo_Mensual.xlsx", allowed_extensions=["xlsx"])

    def _restaurar_boton_generar(self):
        self.boton_generar.text = "Generar Reporte Excel"
        self.boton_generar.icon = ft.icons.PLAY_ARROW
        self.boton_generar.style = ft.ButtonStyle(bgcolor=ft.colors.BLUE_800, color=ft.colors.WHITE)
        self.boton_generar.disabled = False
        if self.page:
            self.page.update()

    def on_save_result(self, e: ft.FilePickerResultEvent):
        if not e.path: return
        self.boton_generar.text = "Calculando finanzas desde BD..."
        self.boton_generar.disabled = True
        self.page.update()
        
        ruta_excel = e.path if e.path.endswith(".xlsx") else e.path + ".xlsx"
        
        def _ejecutar_exportacion():
            try:
                motor = GeneradorFlujoEfectivo(self.rutas_archivos, ajustes_manuales={}, saldos_iniciales={})
                df_global, df_detallado, df_resumen = motor.generar_mensual_desde_bd(mes_filtro=self.mes_mensual)
                
                os.makedirs("local_cache", exist_ok=True)
                df_global.write_parquet("local_cache/base_global.parquet")
                df_detallado.write_parquet("local_cache/base_detallada.parquet")
                pl.from_pandas(df_resumen).write_parquet("local_cache/base_resumen.parquet")

                motor.exportar_a_excel(df_detallado, df_resumen, ruta_excel)
                
                self.boton_generar.text = "¡Reporte Generado con Éxito!"
                self.boton_generar.icon = ft.icons.CHECK_CIRCLE
                self.boton_generar.style = ft.ButtonStyle(bgcolor=ft.colors.GREEN_600, color=ft.colors.WHITE)
                if self.page:
                    self.page.update()
                
                self._abrir_archivo(ruta_excel)
                
                import threading
                threading.Timer(2.5, self._restaurar_boton_generar).start()
                
            except Exception as ex:
                import traceback
                traceback.print_exc()
                self._mostrar_snack(f"❌ Error interno: {str(ex)}", False)
                self._restaurar_boton_generar()
        
        threading.Thread(target=_ejecutar_exportacion, daemon=True).start()

    def build_ui(self):
        header = ft.Column([
            ft.Text("Consolidador de Flujo de Efectivo", size=28, weight=ft.FontWeight.W_900, color=ft.colors.BLUE_900),
            ft.Text("Automatiza la lectura de extractos y genera el reporte gerencial en segundos.", size=15, color=ft.colors.GREY_700),
            ft.Divider(height=20, color=ft.colors.TRANSPARENT)
        ])

        self.switch_mensual = ft.Switch(label="Cargue Mensual", value=self.tipo_cargue == "mensual", on_change=lambda e: self.cambiar_tipo_cargue("mensual"))
        self.switch_diario = ft.Switch(label="Cargue Diario", value=self.tipo_cargue == "diario", on_change=lambda e: self.cambiar_tipo_cargue("diario"))
        self.selector_mes = ft.Dropdown(
            label="Seleccionar mes", width=250, options=[], visible=self.tipo_cargue == "mensual",
            on_change=lambda e: setattr(self, 'mes_mensual', e.control.value)
        )
        selector_tipo = ft.Container(content=ft.Row([self.switch_mensual, self.switch_diario], spacing=40), padding=15, bgcolor=ft.colors.BLUE_50, border_radius=10, border=ft.border.all(1, ft.colors.BLUE_200))
        self.info_diario = ft.Container(content=ft.Text("Los datos diarios se guardarán directamente en la Base de Datos transaccional.", size=12, color=ft.colors.GREY_600), visible=False, padding=10, bgcolor=ft.colors.AMBER_50, border_radius=8)

        # --- SECCIÓN 1: BANCOS (Solo visible en Diario) ---
        boton_saldos = ft.ElevatedButton(
            "Extraer Saldos Iniciales", 
            icon=ft.icons.ACCOUNT_BALANCE, 
            style=ft.ButtonStyle(bgcolor=ft.colors.BLUE_50, color=ft.colors.BLUE_800), 
            on_click=lambda e: self.saldos_picker.pick_files(dialog_title="Selecciona el Excel con los saldos base", allowed_extensions=["xlsx", "xls"])
        )

        titulo_tarjetas = ft.Row([
            ft.Column([
                ft.Text("Paso 1: Extractos Bancarios y Cajas", size=18, weight=ft.FontWeight.W_800, color=ft.colors.BLUE_800),
                ft.Text("Carga el Excel de cada cuenta para inyectarlo a la Base de Datos.", size=13, color=ft.colors.GREY_600),
            ]),
            ft.Container(expand=True),
            boton_saldos
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        bancos_config = [
            {"id": "bancolombia", "nombre": "Bancolombia", "color": ft.colors.BLUE_700, "logo_path": "src/assets/logos/bancolombia.png", "icon": None},
            {"id": "davivienda", "nombre": "Davivienda", "color": ft.colors.RED_700, "logo_path": "src/assets/logos/davivienda.png", "icon": None},
            {"id": "occidente", "nombre": "Bco. Occidente", "color": ft.colors.BLUE_900, "logo_path": "src/assets/logos/occidente.png", "icon": None},
            {"id": "agrario", "nombre": "Banco Agrario", "color": ft.colors.GREEN_700, "logo_path": "src/assets/logos/agrario.svg", "icon": None},
            {"id": "alianza", "nombre": "Alianza Fid.", "color": ft.colors.TEAL_700, "logo_path": "src/assets/logos/alianza.jpeg", "icon": None},
            {"id": "caja", "nombre": "Caja General", "color": ft.colors.ORANGE_700, "logo_path": None, "icon": ft.icons.MONETIZATION_ON},
        ]

        lista_tarjetas = []
        for banco in bancos_config:
            tarjeta = TarjetaBanco(banco_id=banco["id"], nombre=banco["nombre"], color=banco["color"], on_cargar_click=self.abrir_selector, icono=banco["icon"], logo_path=banco["logo_path"])
            self.tarjetas_bancos[banco["id"]] = tarjeta
            lista_tarjetas.append(tarjeta)

        grid_bancos = ft.Row(lista_tarjetas, wrap=True, spacing=20, run_spacing=20)
        
        self.paso1_container = ft.Column([titulo_tarjetas, ft.Container(height=5), grid_bancos, ft.Divider(height=20, color=ft.colors.GREY_300)])
        
        self.mensaje_bd = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.STORAGE, color=ft.colors.BLUE_700, size=30),
                ft.Column([
                    ft.Text("Modo Mensual Activado", weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_900),
                    ft.Text("El sistema leerá las transacciones directamente de la Base de Datos (SQLite).", size=13, color=ft.colors.GREY_700)
                ])
            ]),
            padding=20, bgcolor=ft.colors.BLUE_50, border_radius=10, border=ft.border.all(1, ft.colors.BLUE_200), visible=False
        )

        # --- SECCIÓN 2: AUXILIARES (Solo visible en Mensual) ---
        self.titulo_auxiliares = ft.Column([
            ft.Text("Paso 2: Bases Auxiliares", size=18, weight=ft.FontWeight.W_800, color=ft.colors.BLUE_800),
            ft.Text("Sube aquí todos los libros auxiliares que alimentarán el desglose del reporte.", size=13, color=ft.colors.GREY_600),
        ])

        botones_auxiliares = ft.Row([
            ft.ElevatedButton("Gastos (2335)", icon=ft.icons.RECEIPT_LONG, style=ft.ButtonStyle(bgcolor=ft.colors.PURPLE_50, color=ft.colors.PURPLE_700), on_click=lambda e: self.gastos_picker.pick_files(dialog_title="Selecciona el Auxiliar 2335", allowed_extensions=["xlsx", "xls"])),
            ft.ElevatedButton("Supply (2205)", icon=ft.icons.LOCAL_SHIPPING, style=ft.ButtonStyle(bgcolor=ft.colors.TEAL_50, color=ft.colors.TEAL_700), on_click=lambda e: self.aux_prov_picker.pick_files(dialog_title="Selecciona el Auxiliar 2205", allowed_extensions=["xlsx", "xls"])),
            ft.ElevatedButton("Nómina (25)", icon=ft.icons.PEOPLE, style=ft.ButtonStyle(bgcolor=ft.colors.INDIGO_50, color=ft.colors.INDIGO_700), on_click=lambda e: self.aux_nomina_picker.pick_files(dialog_title="Selecciona el Auxiliar 25", allowed_extensions=["xlsx", "xls"])),
            ft.ElevatedButton("Aux. caja bancos", icon=ft.icons.ACCOUNT_BALANCE_WALLET, style=ft.ButtonStyle(bgcolor=ft.colors.DEEP_ORANGE_50, color=ft.colors.DEEP_ORANGE_700), on_click=lambda e: self.caja_bancos_picker.pick_files(dialog_title="Selecciona el Auxiliar caja bancos", allowed_extensions=["xlsx", "xls"]))
        ], wrap=True, spacing=15)

        self.paso2_container = ft.Container(content=botones_auxiliares, padding=20, bgcolor=ft.colors.WHITE, border_radius=10, border=ft.border.all(1, ft.colors.GREY_200))

        # --- SECCIÓN 3: AJUSTES ALIANZA (Ahora visible en DIARIO) ---
        self.titulo_ajustes = ft.Column([
            ft.Text("Paso 2: Conciliaciones Extras de Fin de Mes (Alianza)", size=18, weight=ft.FontWeight.W_800, color=ft.colors.BLUE_800),
            ft.Text("Solo para final de mes: inyecta a la BD los rendimientos e impuestos extraídos de los PDFs.", size=13, color=ft.colors.GREY_600),
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
                    ft.Text("Valores extraídos de PDFs (Listos para inyectarse a BD):", weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_900, size=13),
                    ft.Row([ft.Text("Ingresos:", size=14), self.texto_pdf_resumen_ingresos, ft.Text(" |  Egresos:", size=14), self.texto_pdf_resumen_egresos])
                ]),
                ft.Container(expand=True), boton_limpiar
            ])
        )

        self.paso3_container = ft.Container(
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
            ft.Text("Paso Final: Generación y Guardado", size=18, weight=ft.FontWeight.W_800, color=ft.colors.BLUE_800, text_align=ft.TextAlign.CENTER),
            ft.Container(height=5)
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        self.boton_generar = ft.ElevatedButton("...", height=60, width=400, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)), on_click=self.procesar_flujo)

        # Sincronizar UI con el modo actual
        self.cambiar_tipo_cargue(self.tipo_cargue)

        self.content = ft.Column([
            header, ft.Row([selector_tipo, ft.Container(width=15), self.selector_mes], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            self.info_diario, ft.Divider(height=15, color=ft.colors.TRANSPARENT),
            self.paso1_container, self.mensaje_bd,
            self.titulo_auxiliares, self.paso2_container, ft.Divider(height=20, color=ft.colors.TRANSPARENT),
            self.titulo_ajustes, self.paso3_container, ft.Divider(height=20, color=ft.colors.TRANSPARENT),
            ft.Column([titulo_generar, self.boton_generar], horizontal_alignment=ft.CrossAxisAlignment.CENTER), ft.Container(height=40)
        ], scroll=ft.ScrollMode.AUTO)