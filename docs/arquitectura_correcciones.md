# Correcciones a la Arquitectura — ShopLens

## Diagrama Original

```
Azure Blob Storage → Databricks (Orquestador) → Databricks Spark → SQL Resultados → Azure Function → Azure App Service
```

## Problemas Identificados

### 1. Azure Function innecesaria
- **Problema:** Azure Function actúa como middleware entre los resultados y la app de visualización, pero no hay lógica event-driven ni transformación en tiempo real que lo justifique.
- **Impacto:** Complejidad adicional, latencia extra, punto de fallo innecesario.
- **Corrección:** Eliminada del flujo. La app lee directamente los datos procesados.

### 2. Almacenamiento de resultados ambiguo
- **Problema:** "SQL Resultados" no especifica el tipo de almacenamiento (Azure SQL DB, Delta Tables, etc.).
- **Corrección:** Los resultados procesados se almacenan como archivos Parquet en Azure Blob Storage (o Delta Tables si se usa Databricks SQL). Esto es más eficiente y económico para datos analíticos de solo lectura.

### 3. Flujo de datos simplificado
- **Problema:** El flujo original tiene 5 saltos; se puede reducir a 3.
- **Corrección:** Ver arquitectura corregida abajo.

### 4. Frontend acoplado a la capa de datos (NUEVA CORRECCIÓN)
- **Problema:** En la primera versión, Streamlit accedía directamente a los archivos CSV y DataFrames. Esto viola el principio de separación de responsabilidades y hace imposible escalar o cambiar la fuente de datos sin modificar el frontend.
- **Corrección:** Se introdujo una **API REST (FastAPI)** como capa intermedia. El frontend solo consume endpoints HTTP; nunca toca datos directamente.

## Arquitectura Corregida

```
┌─────────────────────┐     ┌──────────────────────────┐     ┌─────────────────────┐
│  Azure Blob Storage  │────▶│   Databricks (Spark)     │────▶│  Azure Blob Storage  │
│  (Datos Crudos)      │     │   ETL + Procesamiento    │     │  (Resultados)        │
│                      │     │   - Limpieza             │     │  - Parquet/CSV       │
│  - 102_Tran.csv      │     │   - Explosión productos  │     │  - Métricas pre-     │
│  - 103_Tran.csv      │     │   - Unión categorías     │     │    calculadas        │
│  - 107_Tran.csv      │     │   - Cálculo métricas     │     │                      │
│  - 110_Tran.csv      │     │                          │     └──────────┬────────────┘
│  - Categories.csv    │     └──────────────────────────┘                │
│  - ProductCategory   │                                                 │
│  - nuevaData.zip     │                                                 ▼
└─────────────────────┘                                     ┌─────────────────────┐
                                                            │  Backend (FastAPI)   │
                                                            │  app/api.py          │
                                                            │  Puerto: 8000        │
                                                            │                      │
                                                            │  - Carga datos       │
                                                            │  - Calcula métricas  │
                                                            │  - Expone REST API   │
                                                            └──────────┬────────────┘
                                                                       │ HTTP/JSON
                                                                       ▼
                                                            ┌─────────────────────┐
                                                            │  Frontend (Streamlit)│
                                                            │  frontend/app.py     │
                                                            │  Puerto: 8501        │
                                                            │                      │
                                                            │  - Resumen Ejecutivo │
                                                            │  - Visualizaciones   │
                                                            │  - Análisis Avanzado │
                                                            └─────────────────────┘
```

## Estructura del Proyecto

```
ShopLens/
├── app/                        # BACKEND
│   ├── api.py                  # API REST (FastAPI) — todos los endpoints
│   ├── data_loader.py          # ETL: carga CSVs, transforma, une categorías
│   └── main.py                 # Entry point del backend
│
├── frontend/                   # FRONTEND
│   ├── app.py                  # Entry point Streamlit (sidebar, routing)
│   ├── api_client.py           # Cliente HTTP — única interfaz con el backend
│   └── pages/
│       ├── resumen_ejecutivo.py    # Módulo 1: KPIs y resumen
│       └── visualizaciones.py      # Módulo 2: Gráficos analíticos
│
├── DataSet (1)/                # Datos crudos
├── docs/                       # Documentación
├── requirements.txt            # Dependencias
└── CLAUDE.md                   # Especificación del proyecto
```

## Principios de Diseño

| Principio | Implementación |
|---|---|
| Separación frontend/backend | Frontend solo consume API REST, nunca accede a datos |
| Single Responsibility | Cada módulo tiene una responsabilidad clara |
| API como contrato | `api_client.py` abstrae toda comunicación HTTP |
| Escalabilidad | El backend puede cambiar de CSV a base de datos sin tocar el frontend |
| Filtrado centralizado | Las tiendas se filtran en el backend, no en el frontend |

## Endpoints de la API

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/stores` | Lista de tiendas disponibles |
| GET | `/api/resumen/kpis` | KPIs principales |
| GET | `/api/resumen/top-productos` | Top N productos por volumen |
| GET | `/api/resumen/top-clientes` | Top N clientes por frecuencia |
| GET | `/api/resumen/dias-pico` | Transacciones por día |
| GET | `/api/resumen/dias-pico-heatmap` | Heatmap día×semana |
| GET | `/api/resumen/categorias` | Categorías por volumen |
| GET | `/api/viz/serie-tiempo` | Serie de tiempo configurable |
| GET | `/api/viz/serie-tiempo-por-tienda` | Serie desglosada por tienda |
| GET | `/api/viz/boxplot-categorias` | Stats de boxplot por categoría |
| GET | `/api/viz/boxplot-clientes` | Stats de boxplot por tienda |
| GET | `/api/viz/correlacion` | Matriz de correlación + muestra scatter |

Todos los endpoints aceptan `?stores=102,103` para filtrar por tienda.

## Cómo Ejecutar

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Iniciar backend (terminal 1)
cd ShopLens
uvicorn app.api:app --reload --port 8000

# 3. Iniciar frontend (terminal 2)
cd ShopLens
streamlit run frontend/app.py --server.port 8501
```

## Flujo de Datos para Nuevos Datos

1. Se sube `nuevaData.zip` a Azure Blob Storage
2. Databricks detecta el archivo nuevo (trigger o ejecución programada)
3. Spark procesa y actualiza los resultados en Blob Storage
4. El backend recarga datos al reiniciar (o se implementa hot-reload)
5. El frontend ve los datos actualizados al refrescar

## Stack Tecnológico

| Capa | Tecnología | Justificación |
|---|---|---|
| Backend API | FastAPI | Rápido, async, auto-documenta con Swagger |
| ETL local | Pandas | Suficiente para 1.1M filas; mismo código adaptable a PySpark |
| Frontend | Streamlit | Rápido de construir, interactivo, ideal para presentación |
| Gráficos | Plotly | Interactivos, profesionales, integración nativa con Streamlit |
| ETL distribuido | Databricks Spark | Para producción con datos grandes (maneja tu compañero) |
| Almacenamiento | Azure Blob Storage | Económico, escalable |
