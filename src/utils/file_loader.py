# src/utils/file_loader.py
import os
import shutil
from typing import Optional, Callable

class FileLoader:
    """Utilidad para cargar y copiar archivos a la caché local."""
    
    CACHE_DIR = "local_cache"
    
    @staticmethod
    def ensure_cache_dir():
        os.makedirs(FileLoader.CACHE_DIR, exist_ok=True)
    
    @staticmethod
    def copy_to_cache(origen: str, nombre_destino: str) -> bool:
        try:
            FileLoader.ensure_cache_dir()
            destino = os.path.join(FileLoader.CACHE_DIR, nombre_destino)
            shutil.copy(origen, destino)
            return True
        except Exception:
            return False
    
    @staticmethod
    def get_cache_path(nombre_archivo: str) -> str:
        return os.path.join(FileLoader.CACHE_DIR, nombre_archivo)
    
    @staticmethod
    def file_exists(nombre_archivo: str) -> bool:
        ruta = os.path.join(FileLoader.CACHE_DIR, nombre_archivo)
        return os.path.exists(ruta)
    
    @staticmethod
    def clear_cache():
        for filename in os.listdir(FileLoader.CACHE_DIR):
            ruta = os.path.join(FileLoader.CACHE_DIR, filename)
            if os.path.isfile(ruta):
                os.remove(ruta)