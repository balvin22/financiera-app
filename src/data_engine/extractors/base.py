# src.data_engine/extractors/base.py
import polars as pl
from typing import Optional

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