# Análisis y Modelado Analítico de Transacciones de Supermercado

## Objetivo General

Diseñar y desarrollar una solución tecnológica integral que permita analizar y visualizar el comportamiento de las transacciones de un supermercado, con el fin de generar valor a partir de los datos disponibles mediante **analítica descriptiva y diagnóstica**.

> **Nota:** La solución no se puede quedar sólo en los resultados por consola o un notebook. Debe ser completamente funcional.

---

## Contexto

Se cuenta con un dataset de transacciones de supermercado que contiene información como:

- ID de transacción
- Fecha y hora de la compra
- ID de cliente
- ID de producto
- Categoría del producto
- Cantidad comprada
- Tienda o punto de venta

> **Nota:** No se dispone de precios ni montos de pago. Los estudiantes deberán generar indicadores y métricas relativas (por ejemplo, volumen de compras, frecuencia, diversidad de productos, etc.) que permitan realizar los análisis solicitados.

---

## Entrega Esperada

Los estudiantes deben presentar una solución tecnológica funcional que cumpla con los siguientes componentes:

---

### 1. Resumen Ejecutivo

Debe incluir visualizaciones y métricas que respondan a las siguientes preguntas:

| Indicador | Descripción | Visualización sugerida |
|---|---|---|
| Total de ventas | Total de unidades vendidas (suma de cantidades) | Indicador numérico o gráfico de barra |
| Número de transacciones | Conteo total de transacciones registradas | Indicador numérico |
| Top 10 productos | Productos más comprados según volumen o frecuencia | Gráfico de barras horizontales |
| Top 10 clientes | Clientes con mayor número de compras | Gráfico de barras horizontales |
| Días pico de compra | Días con mayor número de transacciones | Serie de tiempo o heatmap diario |
| Categorías más rentables | Inferir rentabilidad según volumen o frecuencia relativa | Gráfico de pastel o barras |

---

### 2. Visualizaciones Analíticas

Deben crearse las siguientes visualizaciones, con el objetivo de explorar la estructura y el comportamiento de los datos:

| Tipo | Descripción | Objetivo |
|---|---|---|
| Serie de tiempo | Ventas por día o semana | Identificar tendencias y estacionalidad |
| Boxplot | Distribución de totales por cliente o categoría | Detectar outliers o comportamientos atípicos |
| Heatmap | Correlación entre variables numéricas (frecuencia, cantidad promedio, diversidad de productos) | Explorar relaciones entre variables |

---

### 3. Análisis Avanzado

Los resultados deben estar acompañados de su interpretación.

#### A. Segmentación de Clientes

Aplicar **K-Means** para segmentar clientes según su comportamiento de compra:

- **Variables sugeridas:** frecuencia, número de productos distintos, volumen total, diversidad de categorías.
- **Entregables:** visualización del clustering, descripción de cada grupo.

#### B. Recomendador de Productos

Desarrollar un modelo básico de recomendación usando **filtrado colaborativo** o **reglas de asociación**:

- **Dado un cliente:** sugerir productos complementarios o similares a los que ha comprado.
- **Dado un producto:** recomendar otros productos que suelen comprarse junto a él.

#### C. Generación de Nuevos Resultados

Implementar el sistema de tal manera que al **incorporar nuevos datos** como fuente de información se generen automáticamente los resultados de análisis requeridos.

---

## Entregables y Fechas

| # | Fecha | Entregable |
|---|---|---|
| 1 | Mayo 22 de 2026 | Presentación de la propuesta de arquitectura |
| 2 | Mayo 29 de 2026 | Presentación funcional: Resumen Ejecutivo y Visualizaciones Analíticas |
| 3 | Junio 5 de 2026 (hasta las 12:00) | Código fuente ejecutable + Informe técnico (PDF o Markdown) |
| 4 | Junio 9 y 10 de 2026 | Presentación funcional: Análisis Avanzado (segmentación, recomendaciones, nuevos datos) |
| 5 | Junio 9 y 10 de 2026 | Presentación final (10-15 min): resumen de resultados clave y demostración funcional |

### Informe Técnico debe incluir:

1. Descripción de los datos.
2. Metodología de análisis.
3. Principales hallazgos visuales.
4. Resultados del modelo de segmentación y recomendación.
5. Conclusiones y posibles aplicaciones empresariales.

---

## Criterios de Evaluación

| Criterio | Porcentaje |
|---|---|
| Diseño de la arquitectura completo y claridad en su descripción | 15% |
| Resumen Ejecutivo y Visualizaciones Analíticas — Claridad y calidad de visualizaciones | 15% |
| Entrega del código fuente | 10% |
| Informe Técnico — Profundidad del análisis descriptivo | 15% |
| Correcta implementación de análisis avanzado (segmentación y recomendaciones) | 20% |
| Incorporación de nuevos datos | 10% |
| Sustentación | 15% |

**Total: 100%**

---

## Notas Generales

- Trabajo **individual o máximo dos personas**.
- La solución debe ser completamente funcional (no solo notebooks o consola).
- Todos los análisis avanzados deben incluir interpretación de resultados.
