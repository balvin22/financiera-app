# src.data_engine/reports/calculadora_saldos.py
import polars as pl
from src.core.mapeos import ORDEN_BANCOS

def calcular_detallado(df_global: pl.DataFrame, saldos_iniciales: dict, ajustes: dict) -> pl.DataFrame:
    # 1. EXCLUIR CAJA_BANCOS: No es un banco real, es solo para el desglose del Resumen
    df_global = df_global.filter(pl.col("Origen") != "CAJA_BANCOS")
    
    df_global = df_global.with_columns(
        pl.when((pl.col("Origen") == "BANCOLOMBIA") & pl.col("Concepto").str.to_uppercase().str.contains("TRASL ENTRE FONDOS DE VALORES"))
        .then(pl.lit("Traslado_Salida"))
        .otherwise(pl.col("Categoria_Flujo"))
        .alias("Categoria_Flujo")
    )
    
    df_caja = df_global.filter(pl.col("Origen") == "CAJA")
    salidas_caja_cb = df_caja.filter(pl.col("Categoria_Flujo") == "Traslado_Salida")["Egreso"].sum()
    
    traslados_alianza = df_global.filter(
        (pl.col("Origen") == "ALIANZA") & 
        (pl.col("Categoria_Flujo") == "Traslado_Salida")
    )["Egreso"].sum()
    
    resumen = (
        df_global
        .group_by("Origen")
        .agg([
            pl.col("Ingreso").sum().alias("Ingresos_Brutos"),
            pl.col("Egreso").sum().alias("Egresos_Brutos"),
            
            pl.when(pl.col("Categoria_Flujo").str.contains("Traslado_Entrada|Ajuste_Don_Diego"))
            .then(pl.col("Ingreso")).otherwise(0.0).sum().alias("Ingresos_de_Traslados"),
            
            pl.when(pl.col("Categoria_Flujo").str.contains("Traslado_Salida"))
            .then(pl.col("Egreso"))
            .when(pl.col("Categoria_Flujo") == "Ajuste_Don_Diego")
            .then(pl.col("Ingreso"))
            .otherwise(0.0).sum().alias("Salidas_por_Traslados")
        ])
        .with_columns(
            (pl.col("Ingresos_Brutos") - pl.col("Ingresos_de_Traslados")).alias("Ingresos_Operativos"),
            (pl.col("Egresos_Brutos") - pl.col("Salidas_por_Traslados")).alias("Salidas_Operativas")
        )
    )
    
    traslados_a_bancolombia = salidas_caja_cb + traslados_alianza 
    
    resumen = resumen.with_columns(
        pl.when(pl.col("Origen") == "BANCOLOMBIA").then(pl.col("Ingresos_de_Traslados") + traslados_a_bancolombia).otherwise(pl.col("Ingresos_de_Traslados")).alias("Ingresos_de_Traslados")
    ).with_columns(
        pl.when(pl.col("Origen") == "BANCOLOMBIA").then(pl.col("Ingresos_Brutos") - pl.col("Ingresos_de_Traslados")).otherwise(pl.col("Ingresos_Operativos")).alias("Ingresos_Operativos")
    )
    
    ajuste_ing_alianza = ajustes.get("ALIANZA", {}).get("ingresos", 0.0)
    ajuste_egr_alianza = ajustes.get("ALIANZA", {}).get("egresos", 0.0)
    
    resumen = resumen.with_columns(
        pl.when(pl.col("Origen") == "ALIANZA").then(pl.col("Ingresos_Operativos") + ajuste_ing_alianza).otherwise(pl.col("Ingresos_Operativos")).alias("Ingresos_Operativos"),
        pl.when(pl.col("Origen") == "ALIANZA").then(pl.col("Salidas_Operativas") + ajuste_egr_alianza).otherwise(pl.col("Salidas_Operativas")).alias("Salidas_Operativas")
    )
    
    resumen_final = resumen.with_columns(pl.col("Origen").replace_strict(ORDEN_BANCOS, default=99).alias("orden_tmp")).sort("orden_tmp")
    
    resumen_final = resumen_final.with_columns(
        pl.col("Origen").replace_strict(saldos_iniciales, default=0.0).alias("Saldo_Inicial")
    ).with_columns(
        (pl.col("Saldo_Inicial") + pl.col("Ingresos_Operativos") + pl.col("Ingresos_de_Traslados") - pl.col("Salidas_Operativas") - pl.col("Salidas_por_Traslados")).alias("Saldo_Final")
    ).select([
        "Origen", "Saldo_Inicial", "Ingresos_Operativos", "Ingresos_de_Traslados", "Salidas_Operativas", "Salidas_por_Traslados", "Saldo_Final"
    ])

    df_bancos = resumen_final.filter(pl.col("Origen") != "CAJA")
    df_caja = resumen_final.filter(pl.col("Origen") == "CAJA")

    total_bancos = df_bancos.select([
        pl.lit("TOTAL BANCOS").alias("Origen"),
        pl.col("Saldo_Inicial").sum(),
        pl.col("Ingresos_Operativos").sum(),
        pl.col("Ingresos_de_Traslados").sum(),
        pl.col("Salidas_Operativas").sum(),
        pl.col("Salidas_por_Traslados").sum(),
        pl.col("Saldo_Final").sum()
    ])

    total_general = resumen_final.select([
        pl.lit("BANCO + CAJA").alias("Origen"),
        pl.col("Saldo_Inicial").sum(),
        pl.col("Ingresos_Operativos").sum(),
        pl.col("Ingresos_de_Traslados").sum(),
        pl.col("Salidas_Operativas").sum(),
        pl.col("Salidas_por_Traslados").sum(),
        pl.col("Saldo_Final").sum()
    ])

    resumen_completo = pl.concat([df_bancos, total_bancos, df_caja, total_general])
    return resumen_completo