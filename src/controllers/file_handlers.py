# src/controllers/file_handlers.py
import polars as pl
from typing import Dict, List, Optional, Callable
from src.utils.file_loader import FileLoader
from src.utils.pdf_processor import PdfProcessor
from src.ui.components.tarjeta_banco import TarjetaBanco

class FileHandlers:
    """Controlador para manejar la carga de archivos y процессamiento de datos."""
    
    def __init__(self, page, tarjetas_bancos: Dict[str, 'TarjetaBanco']):
        self.page = page
        self.tarjetas_bancos = tarjetas_bancos
        self.pdf_processor = PdfProcessor()
        
        self.rutas_archivos = {
            "bancolombia": None, "davivienda": None, "occidente": None,
            "agrario": None, "alianza": None, "caja": None, "caja_bancos": None
        }
        
        self.acumulado_pdf_ingresos = 0.0
        self.acumulado_pdf_egresos = 0.0
    
    def cargar_gastos_2335(self, origen: str) -> bool:
        return FileLoader.copy_to_cache(origen, "gastos_2335.xlsx")
    
    def cargar_aux_proveedores(self, origen: str) -> bool:
        return FileLoader.copy_to_cache(origen, "aux_prov_2205.xlsx")
    
    def cargar_aux_nomina(self, origen: str) -> bool:
        return FileLoader.copy_to_cache(origen, "aux_nomina_25.xlsx")
    
    def cargar_saldo_inicial(self, origen: str) -> Optional[Dict[str, float]]:
        try:
            df = pl.read_excel(origen)
            col_banco = "Banco / Caja" if "Banco / Caja" in df.columns else "Origen"
            col_saldo = "Saldo Inicial"
            
            if col_saldo not in df.columns:
                return None
            
            saldos = {}
            for row in df.iter_rows(named=True):
                nombre_banco = str(row.get(col_banco, "")).strip().upper()
                for b_id, tarjeta in self.tarjetas_bancos.items():
                    if b_id.upper() in nombre_banco or nombre_banco in b_id.upper():
                        saldos[b_id.upper()] = float(row.get(col_saldo, 0.0))
                        break
            return saldos
        except Exception:
            return None
    
    def procesar_pdf(self, rutas: List[str], es_perdida: bool) -> Dict:
        self.pdf_processor.reset()
        resultado = self.pdf_processor.procesar_archivos(rutas, es_perdida)
        self.acumulado_pdf_ingresos = resultado["ingresos"]
        self.acumulado_pdf_egresos = resultado["egresos"]
        return resultado
    
    def limpiar_pdf(self):
        self.acumulado_pdf_ingresos = 0.0
        self.acumulado_pdf_egresos = 0.0
        self.pdf_processor.reset()
    
    def get_ajustes_alianza(self, manual_ingresos: float, manual_egresos: float) -> Dict:
        return {
            "ALIANZA": {
                "ingresos": manual_ingresos + self.acumulado_pdf_ingresos,
                "egresos": manual_egresos + self.acumulado_pdf_egresos
            }
        }
    
    def get_saldos_tarjetas(self) -> Dict[str, float]:
        return {
            banco_id.upper(): tarjeta.obtener_saldo()
            for banco_id, tarjeta in self.tarjetas_bancos.items()
        }
    
    def marcar_banco_cargado(self, banco_id: str):
        if banco_id in self.tarjetas_bancos:
            self.tarjetas_bancos[banco_id].marcar_como_cargado()
    
    def verificar_archivos_requeridos(self) -> List[str]:
        return [b for b, ruta in self.rutas_archivos.items() if ruta is None]
    
    def set_ruta(self, banco_id: str, ruta: str):
        self.rutas_archivos[banco_id] = ruta
        self.marcar_banco_cargado(banco_id)