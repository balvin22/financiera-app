# src.data_engine/extractors/alianza_pdf.py
import pdfplumber
import re

class AlianzaPdfExtractor:
    def __init__(self, filepath: str, clave: str):
        self.filepath = filepath
        self.clave = clave

    def extraer_valores(self) -> dict:
        """
        Escanea el PDF de Alianza buscando Rentención, Rendimientos y GMF.
        Retorna un diccionario con los Ingresos (Rendimientos) y Egresos (GMF + Retención).
        """
        valores = {"ingresos": 0.0, "egresos": 0.0}
        try:
            # 1. Abrimos el candado del PDF
            with pdfplumber.open(self.filepath, password=self.clave) as pdf:
                texto_completo = ""
                for pagina in pdf.pages:
                    texto_completo += pagina.extract_text() + "\n"

                # 2. Expresiones regulares con soporte para números negativos: (-\s*)?
                patron_retencion = re.search(r"Rentención en la fuente.*?(-\s*)?([\d\.]+,\d{2})", texto_completo, re.IGNORECASE)
                patron_rendimientos = re.search(r"Rendimientos después de gastos.*?(-\s*)?([\d\.]+,\d{2})", texto_completo, re.IGNORECASE)
                patron_gmf = re.search(r"GMF.*?(-\s*)?([\d\.]+,\d{2})", texto_completo, re.IGNORECASE)

                # 3. Limpiador inteligente de números
                def limpiar_numero(match):
                    if match:
                        signo = match.group(1) # Atrapa el signo menos si existe
                        texto_numero = match.group(2) # Atrapa el valor (ej: 5.596.595,18)
                        
                        # Convertimos a formato Python (quitamos puntos de miles, coma por punto)
                        numero_limpio = float(texto_numero.replace(".", "").replace(",", "."))
                        
                        # Si el PDF traía un signo negativo explícito, lo volvemos matemático
                        if signo and "-" in signo:
                            return numero_limpio * -1
                        return numero_limpio
                    return 0.0

                # 4. Ejecutamos la limpieza
                retencion = limpiar_numero(patron_retencion)
                rendimientos = limpiar_numero(patron_rendimientos)
                gmf = limpiar_numero(patron_gmf)

                # 5. Lógica de negocio
                # Los rendimientos son Ingresos. GMF y Retención son Egresos (Salidas)
                valores["ingresos"] = rendimientos
                valores["egresos"] = gmf + retencion
                # 
                
                return valores
                
        except Exception as e:
            print(f"❌ Error leyendo PDF de Alianza ({self.filepath}): {e}")
            return None

# ==========================================
# ZONA DE PRUEBAS (Solo se ejecuta si corres este archivo directamente)
# ==========================================
if __name__ == "__main__":
    # Puedes usar esta zona para probar tus PDFs uno por uno en la consola
    # Cambia la ruta y la clave para hacer la prueba
    ruta_prueba = r"c:/Users/usuario/Desktop/Financiera/Extracto 1155 Alianza ARP Diciembre 2025.pdf"
    clave_prueba = "900333755" # Pon el NIT real aquí
    
    extractor = AlianzaPdfExtractor(ruta_prueba, clave_prueba)
    resultado = extractor.extraer_valores()
    
    if resultado:
        print("\n--- RESULTADO ESCÁNER ---")
        print(f"Ingresos a sumar: $ {resultado['ingresos']:,.2f}")
        print(f"Egresos a sumar:  $ {resultado['egresos']:,.2f}")