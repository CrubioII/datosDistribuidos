# Schema y Descripción del Dataset

## Resumen General

El dataset está compuesto por **6 archivos CSV** que se relacionan entre sí para representar transacciones de 4 tiendas de supermercado.

| Archivo | Tipo | Filas | Descripción |
|---|---|---|---|
| `102_Tran.csv` | Transacciones tienda 102 | 314,286 | Histórico de compras |
| `103_Tran.csv` | Transacciones tienda 103 | 407,130 | Histórico de compras |
| `107_Tran.csv` | Transacciones tienda 107 | 254,633 | Histórico de compras |
| `110_Tran.csv` | Transacciones tienda 110 | 132,938 | Histórico de compras |
| `Categories.csv` | Catálogo de categorías | 50 | Tabla de referencia |
| `ProductCategory.csv` | Relación producto-categoría | 112,010 | Tabla de referencia |

**Total transacciones combinadas: 1,108,987**

---

## Archivos de Transacciones (`*_Tran.csv`)

### Formato
- Separador: `|` (pipe)
- Sin encabezado — las columnas deben asignarse manualmente
- Encoding: probablemente UTF-8 con CRLF (`\r\n`)

### Columnas

| # | Nombre sugerido | Tipo | Ejemplo | Descripción |
|---|---|---|---|---|
| 0 | `date` | string/date | `2013-01-01` | Fecha de la transacción (formato YYYY-MM-DD) |
| 1 | `store_id` | int | `102` | ID de la tienda (coincide con el nombre del archivo) |
| 2 | `customer_id` | int | `530` | ID del cliente |
| 3 | `products` | string | `20 3 1` | Lista de IDs de producto comprados, separados por espacio |

### Cómo leer correctamente

```python
import pandas as pd

df = pd.read_csv('102_Tran.csv', sep='|', header=None,
                 names=['date', 'store_id', 'customer_id', 'products'])
```

### Consideraciones importantes

- **La columna `products` es una cadena de IDs separados por espacio**, no una columna numérica. Requiere `str.split()` para trabajar con productos individuales.
- **No hay ID de transacción explícito** — se debe generar un índice al momento de cargar.
- **No hay columna de cantidad** — cada producto listado representa 1 unidad comprada. Para calcular "cantidad comprada", contar las ocurrencias de cada product_id en la lista.
- **No hay precios** — todos los análisis monetarios deben hacerse con métricas de volumen (unidades, frecuencia).
- El `store_id` en la columna siempre coincide con el número del archivo (redundante, útil para combinar archivos).

### Rango temporal

- **Inicio:** 2013-01-01
- **Fin:** 2013-06-30
- **Período:** 6 meses (primer semestre de 2013)

### Estadísticas por tienda

| Tienda | Transacciones | Clientes únicos |
|---|---|---|
| 102 | 314,286 | 44,593 |
| 103 | 407,130 | (por calcular) |
| 107 | 254,633 | (por calcular) |
| 110 | 132,938 | (por calcular) |

---

## Archivo `Categories.csv`

### Formato
- Separador: `|` (pipe)
- Sin encabezado

### Columnas

| # | Nombre sugerido | Tipo | Ejemplo | Descripción |
|---|---|---|---|---|
| 0 | `category_id` | int | `1` | ID numérico de la categoría |
| 1 | `category_name` | string | `GRUPO FRUVER-EXCEPCIONES` | Nombre descriptivo de la categoría |

### Cómo leer

```python
categories = pd.read_csv('Categories.csv', sep='|', header=None,
                         names=['category_id', 'category_name'])
```

### Estadísticas
- **Total categorías: 50**
- Nombres en español, en mayúsculas
- Ejemplos: `VERDURAS DE FRUTOS`, `PANES-TOSTADAS`, `QUESO`, `PASABOCAS`, `LECHE LIQUIDA`, `CUIDADO DE LA ROPA`

---

## Archivo `ProductCategory.csv`

### Formato
- Separador: `|` (pipe)
- **Tiene encabezado:** `v.Code_pr|v.code`

### Columnas

| Nombre original | Nombre sugerido | Tipo | Ejemplo | Descripción |
|---|---|---|---|---|
| `v.Code_pr` | `product_id` | int | `1007` | ID del producto |
| `v.code` | `category_id` | int | `1` | ID de categoría (FK → `Categories.category_id`) |

### Cómo leer

```python
product_category = pd.read_csv('ProductCategory.csv', sep='|')
product_category.columns = ['product_id', 'category_id']
```

### Estadísticas
- **Productos únicos: 69,891**
- **Categorías referenciadas: 50** (todas las categorías tienen al menos un producto)

---

## Modelo Relacional

```
*_Tran.csv
  └── products (split) → product_id
                              │
                    ProductCategory.csv
                      product_id → category_id
                                        │
                               Categories.csv
                                 category_id → category_name
```

---

## Transformaciones necesarias al cargar

1. **Combinar los 4 archivos de transacciones** con `pd.concat()` después de cargar cada uno.
2. **Generar `transaction_id`** con `reset_index()` o un contador.
3. **Explotar la columna `products`**: usar `str.split(' ')` + `explode()` para obtener una fila por producto.
4. **Parsear fechas**: `pd.to_datetime(df['date'])`.
5. **Unir con `ProductCategory`** y luego con `Categories` para obtener el nombre de categoría por transacción.

### Pipeline de carga sugerido

```python
import pandas as pd

stores = ['102', '103', '107', '110']
dfs = []
for s in stores:
    df = pd.read_csv(f'{s}_Tran.csv', sep='|', header=None,
                     names=['date', 'store_id', 'customer_id', 'products'])
    dfs.append(df)

transactions = pd.concat(dfs, ignore_index=True)
transactions['date'] = pd.to_datetime(transactions['date'])

# Explotar productos
transactions_exp = transactions.copy()
transactions_exp['product_id'] = transactions_exp['products'].str.split(' ')
transactions_exp = transactions_exp.explode('product_id')
transactions_exp['product_id'] = pd.to_numeric(transactions_exp['product_id'], errors='coerce')

# Unir categorías
categories = pd.read_csv('Categories.csv', sep='|', header=None,
                         names=['category_id', 'category_name'])
product_category = pd.read_csv('ProductCategory.csv', sep='|')
product_category.columns = ['product_id', 'category_id']

full = transactions_exp.merge(product_category, on='product_id', how='left') \
                       .merge(categories, on='category_id', how='left')
```

---

## Posibles problemas de calidad de datos

| Problema potencial | Descripción | Acción recomendada |
|---|---|---|
| Productos sin categoría | Algunos `product_id` pueden no estar en `ProductCategory` | Usar `merge(..., how='left')` y manejar NaN |
| Espacios extra en `products` | Cadenas como `" 3  1"` generan IDs vacíos al hacer split | Filtrar con `str.strip()` y descartar vacíos tras explode |
| Duplicados por cliente-fecha | Un cliente puede aparecer varias veces el mismo día | Decidir si se trata como una o varias visitas |
| Clientes entre tiendas | Un mismo `customer_id` puede existir en varias tiendas | Evaluar si el ID es global o local a cada tienda |
