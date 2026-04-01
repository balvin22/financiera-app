# src/utils/metrics_calculator.py
import polars as pl
from typing import Dict, List, Optional

class MetricsCalculator:
    """Calculadora de métricas para tendencias y gráficos."""
    
    @staticmethod
    def calcular_totales_diarios(datos_diarios: Dict) -> Dict:
        """Calcula total, promedio, máximo y mayor categoría."""
        totales_dias = [d["total"] for d in datos_diarios.values() if d["total"] > 0]
        total_sum = sum(totales_dias)
        promedio = total_sum / len(totales_dias) if totales_dias else 0
        maximo = max(totales_dias) if totales_dias else 0
        
        return {
            "total": total_sum,
            "promedio": promedio,
            "maximo": maximo
        }
    
    @staticmethod
    def encontrar_mayor_categoria(categorias: List[str], datos_diarios: Dict) -> str:
        """Encuentra la categoría con mayor gasto total."""
        if not categorias or not datos_diarios:
            return "–"
        
        sumas_cat = {c: sum(d["valores"].get(c, 0) for d in datos_diarios.values()) for c in categorias}
        mayor = max(sumas_cat, key=sumas_cat.get) if sumas_cat else "–"
        return mayor[:15].title()
    
    @staticmethod
    def formatear_moneda(valor: float) -> str:
        return f"$ {valor:,.2f}"
    
    @staticmethod
    def calcular_porcentajes(datos: Dict[str, float]) -> Dict[str, float]:
        """Calcula porcentajes dado un diccionario de valores."""
        total = sum(datos.values())
        if total == 0:
            return {k: 0.0 for k in datos}
        return {k: (v / total) * 100 for k, v in datos.items()}
    
    @staticmethod
    def agrupar_por_origen(df: pl.DataFrame) -> Dict[str, Dict]:
        """Agrupa datos por origen (banco/caja)."""
        if df.is_empty():
            return {}
        
        return {
            str(row["Origen"]): {
                "ingresos": row["Ingresos_Operativos"] + row["Ingresos_de_Traslados"],
                "egresos": row["Salidas_Operativas"] + row["Salidas_por_Traslados"],
                "saldo_final": row["Saldo_Final"]
            }
            for row in df.iter_rows(named=True)
        }
    
    @staticmethod
    def calcular_tendencia(datos: List[float], periodos: int = 7) -> str:
        """Calcula tendencia simple (subiendo/bajando/estable)."""
        if len(datos) < 2:
            return "estable"
        
        recientes = datos[-periodos:]
        anterior = datos[-periodos*2:-periodos] if len(datos) >= periodos*2 else recientes
        
        promedio_reciente = sum(recientes) / len(recientes)
        promedio_anterior = sum(anterior) / len(anterior)
        
        diferencia = promedio_reciente - promedio_anterior
        porcentaje = abs(diferencia) / promedio_anterior * 100 if promedio_anterior > 0 else 0
        
        if porcentaje < 5:
            return "estable"
        elif diferencia > 0:
            return "subiendo"
        else:
            return "bajando"