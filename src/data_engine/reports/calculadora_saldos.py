# src/data_engine/reports/calculadora_saldos.py
import polars as pl
from src.core.mapeos import ORDEN_BANCOS

def calcular_detallado(movimientos_db, saldos_iniciales: dict, ajustes: dict) -> pl.DataFrame:
    if isinstance(movimientos_db, pl.DataFrame):
        if movimientos_db.is_empty():
            return pl.DataFrame({"Origen": pl.Utf8, "Saldo_Inicial": pl.Float64, "Ingresos_Operativos": pl.Float64, "Anulada": pl.Float64, "Ingresos_de_Traslados": pl.Float64, "Salidas_Operativas": pl.Float64, "Salidas_por_Traslados": pl.Float64, "Saldo_Final": pl.Float64})
        df_global = movimientos_db
    else:
        if not movimientos_db:
            return pl.DataFrame({"Origen": pl.Utf8, "Saldo_Inicial": pl.Float64, "Ingresos_Operativos": pl.Float64, "Anulada": pl.Float64, "Ingresos_de_Traslados": pl.Float64, "Salidas_Operativas": pl.Float64, "Salidas_por_Traslados": pl.Float64, "Saldo_Final": pl.Float64})
        
        df_global = pl.DataFrame(movimientos_db).rename({
            "origen": "Origen", "concepto": "Concepto", "ingreso": "Ingreso", "egreso": "Egreso", "categoria_flujo": "Categoria_Flujo"
        })

    df_global = df_global.filter(pl.col("Origen") != "CAJA_BANCOS")
    
    df_global = df_global.with_columns(
        pl.when((pl.col("Origen") == "BANCOLOMBIA") & pl.col("Concepto").fill_null("").str.to_uppercase().str.contains("TRASL ENTRE FONDOS DE VALORES"))
        .then(pl.lit("Traslado_Salida"))
        .otherwise(pl.col("Categoria_Flujo"))
        .alias("Categoria_Flujo")
    )
    
    df_caja = df_global.filter(pl.col("Origen") == "CAJA")
    salidas_caja_cb = df_caja.filter(pl.col("Categoria_Flujo") == "Traslado_Salida")["Egreso"].sum()
    
    df_alianza_traslados = df_global.filter(
        (pl.col("Origen") == "ALIANZA") & 
        (pl.col("Categoria_Flujo") == "Traslado_Salida")
    )
    
    traslados_alianza_occidente = df_alianza_traslados.filter(
        pl.col("Concepto").fill_null("").str.to_uppercase().str.contains("OCCIDENTE")
    )["Egreso"].sum()
    
    traslados_alianza_bancolombia = df_alianza_traslados["Egreso"].sum() - traslados_alianza_occidente
    
    # =========================================================================
    # 5. AGRUPACIÓN Y CÁLCULO DE MACROS (EXTRACCIÓN BLINDADA ING/EGR)
    # =========================================================================
    resumen = (
        df_global
        .group_by("Origen")
        .agg([
            pl.col("Ingreso").fill_null(0.0).sum().alias("Ingresos_Brutos"),
            pl.col("Egreso").fill_null(0.0).sum().alias("Egresos_Brutos"),
            
            # Buscamos anuladas en INGRESOS
            # pl.when(pl.col("Categoria_Flujo").fill_null("").str.to_uppercase().str.contains("ANULA"))
            # .then(pl.col("Egreso")).otherwise(0.0).sum().alias("Anuladas_Ingreso"),
            
            # Buscamos anuladas en EGRESOS
            pl.when(pl.col("Categoria_Flujo").fill_null("").str.to_uppercase().str.contains("ANULA"))
            .then(pl.col("Egreso")).otherwise(0.0).sum().alias("Anuladas_Egreso"),
            
            pl.when(pl.col("Categoria_Flujo").fill_null("").str.contains("Traslado_Entrada|Ajuste_Don_Diego"))
            .then(pl.col("Ingreso")).otherwise(0.0).sum().alias("Ingresos_de_Traslados"),
            
            pl.when(pl.col("Categoria_Flujo").fill_null("").str.contains("Traslado_Salida"))
            .then(pl.col("Egreso"))
            .when(pl.col("Categoria_Flujo").fill_null("") == "Ajuste_Don_Diego")
            .then(pl.col("Ingreso"))
            .otherwise(0.0).sum().alias("Salidas_por_Traslados")
        ])
        .with_columns(
            # Restamos las anuladas del lado correcto para limpiar las operaciones
            (pl.col("Ingresos_Brutos") - pl.col("Ingresos_de_Traslados") - pl.col("Anuladas_Egreso")).alias("Ingresos_Operativos"),
            (pl.col("Egresos_Brutos") - pl.col("Salidas_por_Traslados") - pl.col("Anuladas_Egreso")).alias("Salidas_Operativas"),
            # Unimos ambas anuladas para la columna del Excel
            (pl.col("Anuladas_Egreso")).alias("Anulada")
        )
    )
    
    traslados_a_bancolombia = salidas_caja_cb + traslados_alianza_bancolombia 
    traslados_a_occidente = traslados_alianza_occidente
    
    resumen = resumen.with_columns(
        pl.when(pl.col("Origen") == "BANCOLOMBIA").then(pl.lit(traslados_a_bancolombia)).otherwise(pl.col("Ingresos_de_Traslados")).alias("Ingresos_de_Traslados")
    ).with_columns(
        pl.when(pl.col("Origen") == "BANCOLOMBIA").then(pl.col("Ingresos_Brutos") - pl.col("Ingresos_de_Traslados") ).otherwise(pl.col("Ingresos_Operativos")).alias("Ingresos_Operativos")
    )
    
    resumen = resumen.with_columns(
        pl.when(pl.col("Origen") == "OCCIDENTE").then(pl.col("Ingresos_de_Traslados") + traslados_a_occidente).otherwise(pl.col("Ingresos_de_Traslados")).alias("Ingresos_de_Traslados")
    ).with_columns(
        pl.when(pl.col("Origen") == "OCCIDENTE").then(pl.col("Ingresos_Brutos") - pl.col("Ingresos_de_Traslados") 
                                                      
                                                      ).otherwise(pl.col("Ingresos_Operativos")).alias("Ingresos_Operativos")
    )
    
    resumen_final = resumen.with_columns(pl.col("Origen").replace_strict(ORDEN_BANCOS, default=99).alias("orden_tmp")).sort("orden_tmp")
    
    resumen_final = resumen_final.with_columns(pl.col("Origen").replace_strict(saldos_iniciales, default=0.0).alias("Saldo_Inicial")).with_columns(
        # La ecuación de Saldo Final cuadra sumando y restando las anuladas de vuelta
        (pl.col("Saldo_Inicial") + pl.col("Ingresos_Operativos") + pl.col("Ingresos_de_Traslados") - pl.col("Salidas_Operativas") - pl.col("Salidas_por_Traslados")).alias("Saldo_Final")
    ).select([
        "Origen", "Saldo_Inicial", "Ingresos_Operativos", "Anulada", "Ingresos_de_Traslados", "Salidas_Operativas", "Salidas_por_Traslados", "Saldo_Final"
    ])

    df_bancos = resumen_final.filter(pl.col("Origen") != "CAJA")
    df_caja = resumen_final.filter(pl.col("Origen") == "CAJA")

    total_bancos = df_bancos.select([
        pl.lit("TOTAL BANCOS").alias("Origen"), pl.col("Saldo_Inicial").sum(), pl.col("Ingresos_Operativos").sum(),
        pl.col("Anulada").sum(), pl.col("Ingresos_de_Traslados").sum(), pl.col("Salidas_Operativas").sum(),
        pl.col("Salidas_por_Traslados").sum(), pl.col("Saldo_Final").sum()
    ])

    total_general = resumen_final.select([
        pl.lit("BANCO + CAJA").alias("Origen"), pl.col("Saldo_Inicial").sum(), pl.col("Ingresos_Operativos").sum(),
        pl.col("Anulada").sum(), pl.col("Ingresos_de_Traslados").sum(), pl.col("Salidas_Operativas").sum(),
        pl.col("Salidas_por_Traslados").sum(), pl.col("Saldo_Final").sum()
    ])

    return pl.concat([df_bancos, total_bancos, df_caja, total_general])