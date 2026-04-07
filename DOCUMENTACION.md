# Documentación Técnica - Financiera App

## Descripción General del Proyecto

Aplicación de escritorio para gestión financiera que consolida información de múltiples bancos y cajas, generando reportes de flujo de efectivo y resumen gerencial.

---

## 1. Archivos de Entrada (Datos Fuente)

### 1.1 Extractos Bancarios (Excel)

| Banco | Archivo Fuente | Hoja | Descripción |
|-------|---------------|------|-------------|
| **Bancolombia** | Excel (.xlsx) | `Mov` | Movimientos con formato condicional (colores) |
| **Davivienda** | Excel (.xlsx/.xls) | `Mov` | Movimientos con skiprows=2 |
| **Occidente** | Excel (.xlsx) | `Hoja1` | Skiprows=26 |
| **Agrario** | Excel (.xlsx) | `Pag` | Skiprows=10 |
| **Alianza** | Excel (.xlsx) | `Pag (2)` o `Pag` | Skiprows=5 si es "Pag" |
| **Caja** | Excel (.xlsx) | `Mov` | Movimientos contables |
| **Caja Bancos** | Excel o CSV | `Mov` | Pagos a proveedores por banco |

### 1.2 PDFs de Alianza

- **AlianzaPdfExtractor** (`src/data_engine/extractors/alianza_pdf.py`)
- Proceso: Extrae valores mediante expresiones regulares
- Datos extraídos:
  - `Rendimientos después de gastos` → Ingresos
  - `GMF` + `Retención en la fuente` → Egresos
- Requiere clave/password (default: `900333755`)

### 1.3 Archivos Auxiliares

| Archivo | Ubicación Original | Destino (Cache) | Contenido |
|---------|-------------------|-----------------|------------|
| Gastos 2335 | Excel | `local_cache/gastos_2335.xlsx` | Gastos operacionales del mes |
| Auxiliar Proveedores 2205 | Excel | `local_cache/aux_prov_2205.xlsx` | Credits Supply |
| Auxiliar Nómina 25 | Excel | `local_cache/aux_nomina_25.xlsx` | Total nómina pagada |
| Saldo Inicial | Excel | memoria | Saldos iniciales por banco |
| Proveedores | Excel | `local_cache/proveedores.xlsx` | Lista de proveedores |
| Maestros BD | SQLite | `local_cache/maestros.db` | Proveedores, cuentas, centros de costo |

---

## 2. Extracción de Datos por Archivo

### 2.1 BancolombiaExtractor (`bancolombia.py`)

**Archivo de entrada:** Excel (.xlsx) - Hoja: `Mov`

**Columnas origen:**
| Columna Origen | Tipo | Descripción |
|---------------|------|-------------|
| `FECHA` | Date/String | Fecha del movimiento (formato YYYYMMDD) |
| `CONCEPTO` | String | Descripción del movimiento |
| `VALOR` | Numeric | Valor positivo o negativo (con formato condicional) |

**Procesamiento:**
1. Lee con `openpyxl` para detectar color de celda (rojo = egreso)
2. Detecta valores negativos matemáticamente
3. Clasifica conceptos que contienen "TRASL ENTRE FONDOS DE VALORES" como traslado
4. Convierte fecha de `YYYYMMDD` a Date

**Normalización al esquema:**
| Campo Salida | Transformación |
|--------------|----------------|
| `Fecha` | `str.to_date("%Y%m%d")` |
| `Concepto` | Igual al origen |
| `Documento_Referencia` |固定值 `"N/A"` |
| `Ingreso` | Si valor >= 0 y no es rojo: `abs(valor)`, sino `0.0` |
| `Egreso` | Si valor < 0 o es rojo: `abs(valor)`, sino `0.0` |
| `Origen` |固定值 `"BANCOLOMBIA"` |
| `Categoria_Flujo` | `"Traslado_Salida"` si contiene "TRASL ENTRE FONDOS", sino `"Operacion_Normal"` |

---

### 2.2 DaviviendaExtractor (`davivienda.py`)

**Archivo de entrada:** Excel (.xlsx/.xls) - Hoja: `Mov`, skiprows=2

**Columnas origen:**
| Columna Origen | Tipo | Descripción |
|---------------|------|-------------|
| `Fecha` | String | Fecha (formato YYYY-MM-DD) |
| `Tran` | String | Código de transacción |
| `Desc Mot.` | String | Descripción del movimiento |
| `Doc.` | String | Número de documento |
| `Ingreso` | Numeric | Valor ingreso |
| `Egreso` | Numeric | Valor egreso |

**Procesamiento:**
1. Convierte Ingreso/Egreso a numeric, reemplaza null por 0.0
2. Convierte columnas de texto a string
3. Extrae fecha con slice(0,10) para obtener YYYY-MM-DD

**Normalización al esquema:**
| Campo Salida | Transformación |
|--------------|----------------|
| `Fecha` | `str.slice(0,10).str.to_date("%Y-%m-%d")` |
| `Concepto` | `str.strip_chars()` de `Desc Mot.` |
| `Documento_Referencia` | Valor de `Doc.` |
| `Ingreso` | Valor numérico de `Ingreso` |
| `Egreso` | Valor numérico de `Egreso` |
| `Origen` |固定值 `"DAVIVIENDA"` |
| `Categoria_Flujo` | `"Traslado_Salida"` si concepto contiene "Dcto por Transferencia de Fondos", sino `"Operacion_Normal"` |

---

### 2.3 OccidenteExtractor (`occidente.py`)

**Archivo de entrada:** Excel (.xlsx) - Hoja: `Hoja1`, skiprows=26

**Columnas origen:**
| Columna Origen | Tipo | Descripción |
|---------------|------|-------------|
| `Fecha` | Date/String | Fecha del movimiento |
| `Transacción` | String | Descripción del movimiento |
| `Nro. Documento` | String | Número de documento |
| `Créditos` | Numeric | Valor ingreso |
| `Débitos` | Numeric | Valor egreso |

**Procesamiento:**
1. Fuerza columnas conflictivas a string (Nro. Documento, Transacción)
2. Convierte fecha con máscara `%Y/%m/%d`
3. Convierte Créditos/Débitos a Float64 con fill_null(0.0)

**Normalización al esquema:**
| Campo Salida | Transformación |
|--------------|----------------|
| `Fecha` | `cast(Utf8).str.to_date("%Y/%m/%d")` |
| `Concepto` | `cast(Utf8)` de Transacción |
| `Documento_Referencia` | `cast(Utf8)` de Nro. Documento |
| `Ingreso` | `cast(Float64).fill_null(0.0)` de Créditos |
| `Egreso` | `cast(Float64).fill_null(0.0)` de Débitos |
| `Origen` |固定值 `"OCCIDENTE"` |
| `Categoria_Flujo` | `"Traslado_Salida"` si concepto == "TRASLADO FONDOS SC", sino `"Operacion_Normal"` |

---

### 2.4 AgrarioExtractor (`agrario.py`)

**Archivo de entrada:** Excel (.xlsx) - Hoja: `Pag`, skiprows=10

**Columnas origen:**
| Columna Origen | Tipo | Descripción |
|---------------|------|-------------|
| `Fecha` | String | Fecha (formato DD/MM/YYYY) |
| `Transacción` | String | Descripción del movimiento |
| `Débito` | Numeric | Valordebito |
| `Crédito` | Numeric | Valor crédito |
| `Impuesto GMF` | Numeric | Gravamen movimientos financieros |

**Procesamiento:**
1. Lee Débito, Crédito, GMF como numeric
2. Convierte Transacción a string
3. Formato fecha DD/MM/YYYY con slice(0,10)
4. Calcula Egreso = Débito + GMF

**Normalización al esquema:**
| Campo Salida | Transformación |
|--------------|----------------|
| `Fecha` | `str.slice(0,10).str.to_date("%d/%m/%Y")` |
| `Concepto` | `str.strip_chars()` de Transacción |
| `Documento_Referencia` |固定值 `"N/A"` |
| `Ingreso` | Valor de Crédito |
| `Egreso` | `Débito + Impuesto GMF` |
| `Origen` |固定值 `"AGRARIO"` |
| `Categoria_Flujo` | `"Traslado_Salida"` si concepto contiene "INTERNET TRANSFERENCIAS ENTRE TERCEROS", sino `"Operacion_Normal"` |

---

### 2.5 AlianzaExtractor (`alianza.py`)

**Archivo de entrada:** Excel (.xlsx) - Hoja: `Pag (2)` o `Pag` (skiprows=5 si es Pag)

**Columnas origen:**
| Columna Origen | Tipo | Descripción |
|---------------|------|-------------|
| `Fecha Transacción` | String | Fecha (formato YYYY-MM-DD) |
| `Concepto` | String | Descripción del movimiento |
| `Beneficiario` | String | Beneficiario del movimiento |
| `Ingreso` | Numeric | Valor ingreso |
| `Egreso` | Numeric | Valor egreso |

**Procesamiento:**
1. Detecta si existe hoja "Pag (2)" para leer sin skiprows
2. Concatena Concepto + Beneficiario para contexto completo
3. Extrae fecha con slice(0,10)

**Normalización al esquema:**
| Campo Salida | Transformación |
|--------------|----------------|
| `Fecha` | `str.slice(0,10).str.to_date("%Y-%m-%d")` |
| `Concepto` | `concat_str([Concepto, " - ", Beneficiario])` |
| `Documento_Referencia` |固定值 `"N/A"` |
| `Ingreso` | Valor de Ingreso |
| `Egreso` | Valor de Egreso |
| `Origen` |固定值 `"ALIANZA"` |
| `Categoria_Flujo` | `"Traslado_Salida"` si concepto contiene "ARPESOD" y Egreso > 0, sino `"Operacion_Normal"` |

---

### 2.6 CajaExtractor (`caja.py`)

**Archivo de entrada:** Excel (.xlsx) - Hoja: `Mov`

**Columnas origen:**
| Columna Origen | Tipo | Descripción |
|---------------|------|-------------|
| `FECHA` | Date | Fecha del movimiento |
| `TIPO` | String | Tipo de documento (CB, RD, EB, etc.) |
| `NUMERO` | String/Numeric | Número de documento |
| `DETALLE` | String | Descripción del movimiento |
| `DEBITO` | Numeric | Valor débito (entrada) |
| `CREDITO` | Numeric | Valor crédito (salida) |
| `NOMBRE` | String | Nombre del tercero |
| `CCOSTO` | String | Centro de costo |

**Procesamiento:**
1. Filtra tipos: elimina tipos que empiezan con C (excepto CB), J, RP, PC
2. Limpia columna NUMERO (remueve ".0")
3. Convierte DEBITO/CREDITO a Float64

**Normalización al esquema:**
| Campo Salida | Transformación |
|--------------|----------------|
| `Fecha` | `cast(Date)` de FECHA |
| `Concepto` | `cast(Utf8)` de DETALLE |
| `Documento_Referencia` | `cast(Utf8)` de TIPO |
| `Ingreso` | `cast(Float64).fill_null(0.0)` de DEBITO |
| `Egreso` | `cast(Float64).fill_null(0.0)` de CREDITO |
| `Origen` |固定值 `"CAJA"` |
| `Categoria_Flujo` | `"Traslado_Salida"` si TIPO starts_with("CB"), `"Ajuste_Don_Diego"` si TIPO starts_with("RD") y concepto contiene "DIEGO", sino `"Operacion_Normal"` |
| `Tercero` | `fill_null("SIN TERCERO")` de NOMBRE |
| `NOMBRE_CCO` | `fill_null("N/A")` de CCOSTO |
| `Numero_Doc` | `fill_null("")` de NUMERO |

---

### 2.7 CajaBancosExtractor (`caja_bancos.py`)

**Archivo de entrada:** Excel (.xlsx) - Hoja: `Mov` O CSV (separador automático)

**Columnas origen:**
| Columna Origen | Tipo | Descripción |
|---------------|------|-------------|
| `MCNTIPODOC` | String | Tipo de documento |
| `VINNOMBRE` | String | Nombre del proveedor |
| `MCNVALCRED` | Numeric | Valor crédito |

**Procesamiento:**
1. Detecta extensión .csv para usar separador automático
2. Filtra solo documentos tipo EB09
3. Filtra solo proveedores permitidos (carga desde `local_cache/proveedores.xlsx`)
4. Lee con encoding latin1 si es CSV

**Normalización al esquema:**
| Campo Salida | Transformación |
|--------------|----------------|
| `Tercero` | `cast(Utf8)` de VINNOMBRE |
| `Egreso` | `cast(Float64).fill_null(0.0)` de MCNVALCRED |
| `Origen` |固定值 `"CAJA_BANCOS"` |
| `Categoria_Flujo` |固定值 `"Pagos_Por_Bancos"` |

**Nota:** Este extractor no genera las columnas estándar de flujo (Fecha, Concepto, etc.), solo se usa para desglose de proveedores en el resumen.

---

### 2.8 AlianzaPdfExtractor (`alianza_pdf.py`)

**Archivo de entrada:** PDF (password protected)

**Extracción mediante expresiones regulares (pdfplumber):**

| Patrón Regex | Descripción |
|--------------|-------------|
| `Rentención en la fuente.*?([\d\.]+,\d{2})` | Valor de retención |
| `Rendimientos después de gastos.*?([\d\.]+,\d{2})` | Valor de rendimientos |
| `GMF.*?([\d\.]+,\d{2})` | Valor GMF |

**Normalización:**
| Campo Salida | Transformación |
|--------------|----------------|
| `ingresos` | Valor de "Rendimientos después de gastos" |
| `egresos` | GMF + Retención |

**Procesamiento de números:**
1. Elimina puntos de miles
2. Reemplaza coma decimal por punto
3. Convierte a float
4. Aplica signo negativo si existe

---

### 2.9 Archivos Auxiliares

#### 2.9.1 Gastos 2335 (`gastos_2335.xlsx`)

**Columnas origen:**
| Columna Origen | Tipo | Descripción |
|---------------|------|-------------|
| `MCNCUENTA` | String | Código de cuenta contable |
| `MCNVALDEBI` | Numeric | Valor débito |
| `MCNTIPODOC` | String | Tipo de documento (opcional) |
| `CTANOMBRE` o `MCNDETALLE` | String | Nombre de cuenta o detalle |

**Procesamiento:**
1. Filtra valores donde MCNVALDEBI > 0
2. Mapea código de cuenta a categoría usando BD o keywords
3. Clasifica por palabras clave en detalle (NOMIN, EPS, ARRIENDO, etc.)

**Categorías generadas:**
- Nomina Administrativa y Ventas
- Seguridad Social
- Arrendamientos (Incluye Renting)
- Servicios
- Seguros
- Honorarios
- Comisiones y Gastos Bancarios
- Obligaciones financieras
- Otros Proveedores / Gastos

---

#### 2.9.2 Auxiliar Proveedores 2205 (`aux_prov_2205.xlsx`)

**Columnas origen:**
| Columna Origen | Tipo | Descripción |
|---------------|------|-------------|
| `MCNDETALLE` | String | Descripción del movimiento |
| `MCNVALDEBI` | Numeric | Valor débito |

**Procesamiento:**
1. Filtra filas donde MCNDETALLE contiene "SUPPLY"
2. Suma MCNVALDEBI de esas filas

**Resultado:** Total de Créditos Supply

---

#### 2.9.3 Auxiliar Nómina 25 (`aux_nomina_25.xlsx`)

**Columnas origen:**
| Columna Origen | Tipo | Descripción |
|---------------|------|-------------|
| `MCNVALDEBI` | Numeric | Valor débito |

**Procesamiento:**
1. Suma todos los valores de MCNVALDEBI

**Resultado:** Total de nómina pagada en el período

---

## 3. Proceso de Extracción (ETL)

### 3.1 Pipeline de Extracción

```
┌─────────────────────────────────────────────────────────────────────┐
│                    FLUJO DE DATOS                                  │
└─────────────────────────────────────────────────────────────────────┘

  Archivos Excel/PDF          Extractores              Transformación
  ─────────────────          ───────────              ───────────────
  
  bancolombia.xlsx    ──►  BancolombiaExtractor   ──►  + Clasificación 
  davivienda.xls     ──►  DaviviendaExtractor         de Traslados
  occident.xlsx      ──►  OccidenteExtractor      ──►  + Normalización
  agrario.xlsx       ──►  AgrarioExtractor           de Esquema
  alianza.xlsx       ──►  AlianzaExtractor        ──►  + Mapeo C.Costos
  caja.xlsx          ──►  CajaExtractor
  caja_bancos.csv    ──►  CajaBancosExtractor
  alianza.pdf        ──►  AlianzaPdfExtractor
```

### 3.2 Esquema de Datos Estandarizado

Todos los extractores generan un DataFrame con el siguiente esquema:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `Fecha` | Date | Fecha de la transacción |
| `Concepto` | String | Descripción/Detalle |
| `Documento_Referencia` | String | Número de documento |
| `Ingreso` | Float64 | Valor ingreso |
| `Egreso` | Float64 | Valor egreso |
| `Origen` | String | Nombre del banco/caja |
| `Categoria_Flujo` | String | Clasificación (Operacion_Normal/Traslado_Salida/Ajuste) |

### 3.3 Reglas de Negocio Aplicadas

#### Bancolombia
- Detecta colores de celdas (rojo = egreso)
- Detecta valores negativos
- Clasifica "TRASL ENTRE FONDOS DE VALORES" como traslado

#### Davivienda
- Detecta "Dcto por Transferencia de Fondos" como traslado

#### Occidente
- Detecta "TRASLADO FONDOS SC" como traslado

#### Agrario
- Suma Débito + GMF para obtener egreso
- Detecta "INTERNET TRANSFERENCIAS ENTRE TERCEROS" como traslado

#### Alianza
- Une Concepto + Beneficiario
- Detecta "ARPESOD" como traslado de salida

#### Caja
- Filtra tipos: CB (traslado), RD (ajuste Don Diego), EB (proveedor)
- Detecta "DIEGO" en conceptos para ajuste

---

## 3. Transformación y Consolidación

### 3.4 Consolidador Principal

**GeneradorFlujoEfectivo** (`src/data_engine/reports/flujo_efectivo.py`)

```python
df_global = pl.concat(dataframes, how="diagonal")
```

- Une todos los DataFrames en uno solo
- Aplica mapeo de centros de costo usando regex `(\d{5})`
- Reemplaza códigos con nombres de la BD

### 3.5 Calculadora de Saldos

**calcular_detallado** (`src/data_engine/reports/calculadora_saldos.py`)

Para cada banco/caja calcula:
- Saldo Inicial
- Ingresos Operativos
- Ingresos por Traslados
- Salidas Operativas
- Salidas por Traslados
- Saldo Final

### 3.3 Constructor de Resumen

**armar_resumen_gerencial** (`src/data_engine/reports/constructor_resumen.py`)

#### Fuentes de datos adicionales:
1. **Gastos 2335** (`local_cache/gastos_2335.xlsx`)
   - Mapea códigos de cuenta a categorías
   - Agrupa por: Nómina, Seguridad Social, Arriendos, Servicios, etc.

2. **Auxiliar Proveedores 2205** (`local_cache/aux_prov_2205.xlsx`)
   - Filtra detalles que contengan "SUPPLY"
   - Suma valores → Crédito Supply

3. **Auxiliar Nómina 25** (`local_cache/aux_nomina_25.xlsx`)
   - Suma todo MCNVALDEBI → Total nómina pagada

4. **Base de Datos SQLite** (`local_cache/maestros.db`)
   - Tabla `proveedores`: nombres para clasificar pagos
   - Tabla `cuentas_2335`: mapeo código → nombre
   - Tabla `centros_costos`: mapeo código → caja que recauda

#### Estructura del Resumen Generado:
```
├── DETALLE DE INGRESOS BANCARIOS
│   └── (Ingresos por banco)
├── Total Ingresos x Bancos
├── DETALLE DE INGRESOS POR CAJA
│   └── (Ingresos por centro de costo)
├── Total Ingresos x Caja
├── Total Ingresos del mes
├── Saldo inicial del mes anterior
├── Total Disponible
├── DETALLE DE SALIDAS BANCARIAS
│   └── (Salidas por banco)
├── Total Salidas x Bancos
├── DETALLE DE SALIDAS POR CAJA
│   └── (Salidas por centro de costo)
├── Total Salidas x Caja
├── Total salidas del mes
├── PROVEEDORES
│   ├── Pagos por Caja
│   ├── Pagos por Bancos
│   ├── Créditos Supply
│   ├── Total Abonos
│   └── DESGLOSE (por proveedor)
├── PAGO DE NÓMINA Y PRESTACIONES (AUX 25)
└── SALIDAS POR GASTOS OPERACIONALES
    └── (Desglose por categoría)
```

---

## 4. Componentes del Sistema

### 4.1 Módulos de Extracción (`src/data_engine/extractors/`)

| Módulo | Clase | Función |
|--------|-------|---------|
| `base.py` | BaseExtractor | Clase base abstracta |
| `bancolombia.py` | BancolombiaExtractor | Lee Excel con colores |
| `davivienda.py` | DaviviendaExtractor | Lee hoja Mov skiprows=2 |
| `occidente.py` | OccidenteExtractor | Lee Hoja1 skiprows=26 |
| `agrario.py` | AgrarioExtractor | Lee Pag skiprows=10 |
| `alianza.py` | AlianzaExtractor | Lee Pag o Pag(2) |
| `caja.py` | CajaExtractor | Lee Mov, filtra tipos |
| `caja_bancos.py` | CajaBancosExtractor | Lee CSV/Excel, filtra EB09 |
| `alianza_pdf.py` | AlianzaPdfExtractor | Extrae de PDFs con regex |

### 4.2 Módulos de Reportes (`src/data_engine/reports/`)

| Módulo | Función |
|--------|---------|
| `flujo_efectivo.py` | Consolida datos, genera Excel con formato |
| `calculadora_saldos.py` | Calcula saldo por banco |
| `constructor_resumen.py` | Arma reporte gerencial |

### 4.3 Utilidades (`src/utils/`)

| Módulo | Función |
|--------|---------|
| `file_loader.py` | Copia archivos a `local_cache/` |
| `data_loader.py` | Carga Parquet, Excel, SQLite |
| `pdf_processor.py` | Procesa múltiples PDFs |
| `metrics_calculator.py` | Cálculos de métricas |
| `pdf_processor.py` | Processor de PDFs |

### 4.4 Controladores (`src/controllers/`)

| Módulo | Función |
|--------|---------|
| `file_handlers.py` | Manejo de carga de archivos |
| `report_controller.py` | Control de generación de reportes |

### 4.5 UI (`src/ui/`)

- **main_window.py**: Ventana principal Flet
- **views/**: Dashboard, Flujo, Maestros
- **components/**: Gráficos, KPIs, tarjetas de banco

---

## 5. Flujo de Ejecución Completo

```
1. MAIN.PY
   └── build_main_window() [Flet]

2. CARGA DE ARCHIVOS
   ├── FileHandlers.cargar_gastos_2335() → local_cache/gastos_2335.xlsx
   ├── FileHandlers.cargar_aux_proveedores() → local_cache/aux_prov_2205.xlsx
   ├── FileHandlers.cargar_aux_nomina() → local_cache/aux_nomina_25.xlsx
   └── FileHandlers.procesar_pdf() → PdfProcessor

3. EXTRACCIÓN
   ├── BancolombiaExtractor.process()
   ├── DaviviendaExtractor.process()
   ├── OccidenteExtractor.process()
   ├── AgrarioExtractor.process()
   ├── CajaExtractor.process()
   ├── CajaBancosExtractor.process()
   └── AlianzaExtractor.process()

4. CONSOLIDACIÓN
   └── GeneradorFlujoEfectivo.generar_base_consolidada()
       └── pl.concat(dataframes, how="diagonal")

5. CÁLCULO DE SALDOS
   └── calcular_detallado(df_global, saldos_iniciales, ajustes)

6. CONSTRUCCIÓN DE RESUMEN
   └── armada_resumen_gerencial(df_global, df_detallado, ajustes)
       ├── Carga gastos_2335.xlsx
       ├── Carga aux_prov_2205.xlsx
       ├── Carga aux_nomina_25.xlsx
       ├── Carga maestros.db
       └── Ensambla estructura final

7. EXPORTACIÓN
   └── generar_reporte_excel()
       └── Archivo .xlsx con hojas "Detallado" y "Resumen"
```

---

## 6. Archivos de Salida

### 6.1 Archivos en `local_cache/`

| Archivo | Descripción |
|---------|-------------|
| `base_global.parquet` | DataFrame consolidado de todos los bancos |
| `base_detallada.parquet` | Datos por banco con saldo calculado |
| `base_resumen.parquet` | Reporte resumen en formato tabular |
| `maestros.db` | SQLite con catálogos |

### 6.2 Reporte Excel

Generado por el usuario (típicamente en Documents/Reportes):
- **Hoja "Detallado"**: Saldo inicial, ingresos, egresos por banco
- **Hoja "Resumen"**: Resumen gerencial completo

---

## 7. Dependencias Principales

```
polars        # Dataframes de alto rendimiento
pandas        # Manipulación de datos
openpyxl      # Lectura de Excel con estilos
pdfplumber    # Extracción de PDFs
xlsxwriter    # Exportación con formato
flet          # Interfaz gráfica
sqlite3       # Base de datos local
```

---

## 8. Estructura de Archivos del Proyecto

```
financiera-app/
├── main.py                          # Punto de entrada
├── requirements.txt                 # Dependencias
├── local_cache/                     # Datos procesados
│   ├── *.parquet                    # DataFrames
│   ├── *.xlsx                       # Auxiliares
│   └── maestros.db                 # SQLite
├── src/
│   ├── core/                        # Config, DB, logger
│   ├── data_engine/
│   │   ├── extractors/              # Lectura de archivos fuente
│   │   ├── transformers/            # Reglas de negocio
│   │   └── reports/                # Generación de reportes
│   ├── controllers/                 # Lógica de control
│   ├── utils/                      # Utilidades
│   └── ui/                         # Interfaz gráfica
└── logs/                           # Registros
```