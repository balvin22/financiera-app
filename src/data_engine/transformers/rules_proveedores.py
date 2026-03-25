# src/data_engine/transformers/rules_proveedores.py
import pandas as pd
import os

def cargar_diccionario_proveedores(ruta_csv="PROVEEDORES.csv"):
    """
    Lee el archivo CSV de proveedores y retorna una lista de NITs y Nombres 
    para buscar coincidencias.
    """
    if not os.path.exists(ruta_csv):
        return []

    try:
        # Leemos el CSV saltándonos las filas de encabezado (el tuyo empieza en la fila 8 aprox)
        # Ajustaremos el 'skiprows' dependiendo de cómo guardes el archivo final
        df_prov = pd.read_csv(ruta_csv, skiprows=8, names=["Codigo", "Nombre"], dtype=str)
        df_prov = df_prov.dropna(subset=["Nombre"])
        
        # Guardamos los nombres en una lista en mayúsculas y sin espacios extra
        proveedores = df_prov["Nombre"].str.strip().str.upper().tolist()
        return proveedores
    except Exception as e:
        print(f"Error cargando proveedores: {e}")
        return []

def clasificar_salidas_proveedores(df_global, ruta_csv="PROVEEDORES.csv"):
    """
    Recibe el DataFrame global, busca coincidencias con la lista de proveedores
    y crea una nueva columna 'Clasificacion_Egreso'.
    """
    proveedores = cargar_diccionario_proveedores(ruta_csv)
    
    # Creamos la columna por defecto
    df_global['Clasificacion_Egreso'] = 'OTROS GASTOS'

    if not proveedores:
        return df_global

    # Función interna para verificar si el nombre de la transacción está en la lista
    def es_proveedor(descripcion):
        if not isinstance(descripcion, str): return False
        desc_upper = descripcion.upper()
        for prov in proveedores:
            # Si el nombre del proveedor está dentro de la descripción del pago
            if prov in desc_upper:
                return True
        return False

    # Aplicamos la regla solo a los Egresos (Salidas)
    mascara_salidas = df_global['Egreso'] > 0
    df_global.loc[mascara_salidas, 'Es_Proveedor'] = df_global.loc[mascara_salidas, 'Descripcion'].apply(es_proveedor)
    
    # Clasificamos
    df_global.loc[mascara_salidas & (df_global['Es_Proveedor'] == True), 'Clasificacion_Egreso'] = 'PAGO PROVEEDOR'
    df_global.loc[mascara_salidas & (df_global['Es_Proveedor'] == False), 'Clasificacion_Egreso'] = 'GASTO OPERACIONAL'

    # Limpiamos columna temporal
    df_global = df_global.drop(columns=['Es_Proveedor'])

    return df_global