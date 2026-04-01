# src/utils/pdf_processor.py
from typing import Dict, List, Optional
from src.data_engine.extractors.alianza_pdf import AlianzaPdfExtractor

class PdfProcessor:
    """Procesador de PDFs de Alianza Fiduciaria."""
    
    CLAVE_PDF_DEFAULT = "900333755"
    
    def __init__(self, clave: str = CLAVE_PDF_DEFAULT):
        self.clave = clave
        self.acumulado_ingresos = 0.0
        self.acumulado_egresos = 0.0
    
    def reset(self):
        self.acumulado_ingresos = 0.0
        self.acumulado_egresos = 0.0
    
    def procesar_archivos(self, rutas: List[str], es_perdida: bool = False) -> Dict[str, float]:
        """Procesa una lista de rutas de PDFs y retorna los acumulados."""
        archivos_exitosos = 0
        
        for ruta in rutas:
            extractor_pdf = AlianzaPdfExtractor(ruta, self.clave)
            valores = extractor_pdf.extraer_valores()
            if valores:
                if es_perdida:
                    self.acumulado_ingresos -= valores['ingresos']
                else:
                    self.acumulado_ingresos += valores['ingresos']
                self.acumulado_egresos += valores['egresos']
                archivos_exitosos += 1
        
        return {
            "ingresos": self.acumulado_ingresos,
            "egresos": self.acumulado_egresos,
            "archivos_procesados": archivos_exitosos
        }
    
    def formatear_dinero(self, valor: float) -> str:
        return f"$ {valor:,.2f}"
    
    @staticmethod
    def get_estado_mensaje(es_perdida: bool) -> str:
        return "RESTADOS (Pérdida)" if es_perdida else "SUMADOS (Ganancia)"