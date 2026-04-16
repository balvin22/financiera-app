# src.data_engine/extractors/base.py
import polars as pl
from typing import Optional, List

class BaseExtractor:
    def __init__(self, filepath: str):
        self.filepath = filepath

    def process(self) -> pl.DataFrame:
        """
        Método que ejecuta la lectura y estandarización.
        Debe retornar un DataFrame con este esquema exacto:
        - Fecha (Date)
        - Concepto (Utf8/String)
        - Documento_Referencia (Utf8)
        - Ingreso (Float64)
        - Egreso (Float64)
        - Origen (Utf8)
        """
        raise NotImplementedError("El método process() debe ser implementado por la clase hija")

    def get_fechas_unicas(self) -> List[str]:
        """
        Retorna lista de fechas únicas en formato YYYY-MM-DD del archivo.
        """
        try:
            df = self.process()
            if df is None or len(df) == 0:
                return []
            if "Fecha" not in df.columns:
                return []
            
            fechas_set = set()
            for row in df.iter_rows():
                fecha_val = row[0]
                if fecha_val is not None:
                    if hasattr(fecha_val, 'strftime'):
                        fechas_set.add(fecha_val.strftime("%Y-%m-%d"))
                    else:
                        fechas_set.add(str(fecha_val))
            
            return sorted(list(fechas_set))
        except Exception as e:
            print(f"Error get_fechas_unicas: {e}")
            return []