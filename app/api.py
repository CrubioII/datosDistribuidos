"""
api.py — Backend REST API para ShopLens

Expone endpoints con métricas pre-calculadas para que el frontend
nunca acceda directamente a la capa de datos.

Ejecutar: uvicorn app.api:app --reload --port 8000
"""

import sys
from pathlib import Path

# Agregar app/ al path para imports locales
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from typing import Optional
import pandas as pd
import numpy as np
import json
import math

from data_loader import build_full_dataset

# ── Inicialización ──
app = FastAPI(
    title="ShopLens API",
    description="API de analítica de transacciones de supermercado",
    version="1.0.0",
)

# Servir archivos estáticos
static_path = Path(__file__).resolve().parent / "static"
static_path.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

@app.get("/")
def read_index():
    return FileResponse(static_path / "index.html")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Carga de datos al iniciar ──
_transactions, _exploded, _categories = build_full_dataset()


def _filter_stores(stores: Optional[str]):
    """Filtra DataFrames por tiendas. stores es string '102,103'."""
    if not stores:
        return _transactions, _exploded
    store_list = [int(s.strip()) for s in stores.split(",")]
    txn = _transactions[_transactions["store_id"].isin(store_list)]
    exp = _exploded[_exploded["store_id"].isin(store_list)]
    return txn, exp


# ═══════════════════════════════════════════════
# ENDPOINTS: Metadata
# ═══════════════════════════════════════════════


@app.get("/api/stores")
def get_stores():
    """Retorna las tiendas disponibles."""
    stores = sorted(_exploded["store_id"].unique().tolist())
    return {"stores": [int(s) for s in stores]}


@app.get("/api/categories")
def get_categories():
    """Retorna el catálogo de categorías."""
    cats = _categories.to_dict(orient="records")
    return {"categories": cats}


# ═══════════════════════════════════════════════
# ENDPOINTS: Resumen Ejecutivo
# ═══════════════════════════════════════════════


@app.get("/api/resumen/kpis")
def get_kpis(stores: Optional[str] = Query(None, description="IDs de tienda separados por coma")):
    """KPIs principales."""
    txn, exp = _filter_stores(stores)
    total_units = len(exp)
    total_txn = int(txn["transaction_id"].nunique())
    unique_customers = int(exp["customer_id"].nunique())
    unique_products = int(exp["product_id"].nunique())
    num_stores = int(exp["store_id"].nunique())
    avg_per_txn = round(total_units / total_txn, 1) if total_txn > 0 else 0

    return {
        "total_unidades": total_units,
        "total_transacciones": total_txn,
        "clientes_unicos": unique_customers,
        "productos_distintos": unique_products,
        "tiendas": num_stores,
        "promedio_productos_por_transaccion": avg_per_txn,
    }


@app.get("/api/resumen/top-productos")
def get_top_productos(
    stores: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
):
    """Top N productos más comprados por volumen."""
    _, exp = _filter_stores(stores)
    top = (
        exp.groupby("product_id")
        .agg(unidades=("product_id", "size"), transacciones=("transaction_id", "nunique"))
        .sort_values("unidades", ascending=False)
        .head(limit)
        .reset_index()
    )
    cat_map = exp.drop_duplicates("product_id")[["product_id", "category_name"]].dropna()
    top = top.merge(cat_map, on="product_id", how="left")
    top["category_name"] = top["category_name"].fillna("Sin categoría")
    top["product_id"] = top["product_id"].astype(int)
    top["transacciones"] = top["transacciones"].astype(int)
    return {"data": top.to_dict(orient="records")}


@app.get("/api/resumen/top-clientes")
def get_top_clientes(
    stores: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
):
    """Top N clientes con más compras."""
    _, exp = _filter_stores(stores)
    top = (
        exp.groupby("customer_id")
        .agg(
            unidades=("product_id", "size"),
            transacciones=("transaction_id", "nunique"),
            productos_distintos=("product_id", "nunique"),
        )
        .sort_values("transacciones", ascending=False)
        .head(limit)
        .reset_index()
    )
    top["customer_id"] = top["customer_id"].astype(int)
    top["transacciones"] = top["transacciones"].astype(int)
    top["productos_distintos"] = top["productos_distintos"].astype(int)
    return {"data": top.to_dict(orient="records")}


@app.get("/api/resumen/dias-pico")
def get_dias_pico(stores: Optional[str] = Query(None)):
    """Transacciones por día (serie de tiempo)."""
    txn, _ = _filter_stores(stores)
    daily = txn.groupby(txn["date"].dt.date).size().reset_index(name="transacciones")
    daily.columns = ["fecha", "transacciones"]
    daily["fecha"] = daily["fecha"].astype(str)
    daily["transacciones"] = daily["transacciones"].astype(int)
    return {"data": daily.to_dict(orient="records")}


@app.get("/api/resumen/dias-pico-heatmap")
def get_dias_pico_heatmap(stores: Optional[str] = Query(None)):
    """Heatmap: día de la semana x semana del año."""
    txn, _ = _filter_stores(stores)
    txn_c = txn.copy()
    txn_c["day_of_week"] = txn_c["date"].dt.dayofweek
    txn_c["week"] = txn_c["date"].dt.isocalendar().week.astype(int)
    heatmap = txn_c.groupby(["week", "day_of_week"]).size().reset_index(name="transacciones")
    day_names = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    heatmap["dia"] = heatmap["day_of_week"].map(lambda x: day_names[x])
    heatmap["transacciones"] = heatmap["transacciones"].astype(int)
    heatmap["week"] = heatmap["week"].astype(int)
    return {
        "data": heatmap[["week", "dia", "transacciones"]].to_dict(orient="records"),
        "day_order": day_names,
    }


@app.get("/api/resumen/categorias")
def get_categorias_volumen(stores: Optional[str] = Query(None)):
    """Categorías ordenadas por volumen de ventas."""
    _, exp = _filter_stores(stores)
    cat_vol = (
        exp.dropna(subset=["category_name"])
        .groupby("category_name")
        .agg(
            unidades=("product_id", "size"),
            productos_distintos=("product_id", "nunique"),
            transacciones=("transaction_id", "nunique"),
        )
        .sort_values("unidades", ascending=False)
        .reset_index()
    )
    cat_vol["transacciones"] = cat_vol["transacciones"].astype(int)
    cat_vol["productos_distintos"] = cat_vol["productos_distintos"].astype(int)
    no_cat = int(exp["category_name"].isna().sum())
    total = len(exp)
    return {
        "data": cat_vol.to_dict(orient="records"),
        "sin_categoria": no_cat,
        "total_unidades": total,
        "porcentaje_sin_categoria": round(no_cat / total * 100, 1) if total > 0 else 0,
    }


# ═══════════════════════════════════════════════
# ENDPOINTS: Visualizaciones Analíticas
# ═══════════════════════════════════════════════


@app.get("/api/viz/serie-tiempo")
def get_serie_tiempo(
    stores: Optional[str] = Query(None),
    agrupacion: str = Query("dia", pattern="^(dia|semana|mes)$"),
    metrica: str = Query("transacciones", pattern="^(transacciones|unidades)$"),
):
    """Serie de tiempo con agrupación y métrica configurable."""
    txn, exp = _filter_stores(stores)
    source = txn if metrica == "transacciones" else exp
    source_c = source.copy()

    if agrupacion == "dia":
        source_c["periodo"] = source_c["date"].dt.date
    elif agrupacion == "semana":
        source_c["periodo"] = source_c["date"].dt.to_period("W").apply(lambda r: r.start_time)
    else:
        source_c["periodo"] = source_c["date"].dt.to_period("M").apply(lambda r: r.start_time)

    ts = source_c.groupby("periodo").size().reset_index(name="valor")
    ts["periodo"] = pd.to_datetime(ts["periodo"]).dt.strftime("%Y-%m-%d")
    ts["valor"] = ts["valor"].astype(int)

    result = ts.to_dict(orient="records")
    media_movil = None
    if agrupacion == "dia" and len(ts) > 7:
        mm = ts.copy()
        mm["media_movil"] = mm["valor"].rolling(window=7, center=True).mean()
        mm = mm.dropna(subset=["media_movil"])
        mm["media_movil"] = mm["media_movil"].round(1)
        media_movil = mm[["periodo", "media_movil"]].to_dict(orient="records")

    return {"data": result, "media_movil": media_movil}


@app.get("/api/viz/serie-tiempo-por-tienda")
def get_serie_tiempo_por_tienda(
    stores: Optional[str] = Query(None),
    metrica: str = Query("transacciones", pattern="^(transacciones|unidades)$"),
):
    """Serie de tiempo semanal desglosada por tienda."""
    txn, exp = _filter_stores(stores)
    source = txn.copy() if metrica == "transacciones" else exp.copy()
    source["periodo"] = source["date"].dt.to_period("W").apply(lambda r: r.start_time)
    ts = source.groupby(["periodo", "store_id"]).size().reset_index(name="valor")
    ts["periodo"] = pd.to_datetime(ts["periodo"]).dt.strftime("%Y-%m-%d")
    ts["store_id"] = ts["store_id"].astype(int)
    ts["valor"] = ts["valor"].astype(int)
    return {"data": ts.to_dict(orient="records")}


@app.get("/api/viz/boxplot-categorias")
def get_boxplot_categorias(stores: Optional[str] = Query(None), limit: int = Query(12)):
    """Distribución de unidades por transacción, agrupada por categoría (top N)."""
    _, exp = _filter_stores(stores)
    units_per_txn = (
        exp.dropna(subset=["category_name"])
        .groupby(["transaction_id", "category_name"])
        .size()
        .reset_index(name="unidades")
    )
    top_cats = (
        units_per_txn.groupby("category_name")["unidades"]
        .sum()
        .nlargest(limit)
        .index.tolist()
    )
    filtered = units_per_txn[units_per_txn["category_name"].isin(top_cats)]
    stats = []
    for cat in top_cats:
        cat_data = filtered[filtered["category_name"] == cat]["unidades"]
        q1 = float(cat_data.quantile(0.25))
        median = float(cat_data.median())
        q3 = float(cat_data.quantile(0.75))
        iqr = q3 - q1
        whisker_low = float(max(cat_data.min(), q1 - 1.5 * iqr))
        whisker_high = float(min(cat_data.max(), q3 + 1.5 * iqr))
        outliers = [int(x) for x in cat_data[(cat_data < whisker_low) | (cat_data > whisker_high)].tolist()[:100]]
        stats.append({
            "category_name": cat, "min": whisker_low, "q1": q1,
            "median": median, "q3": q3, "max": whisker_high,
            "outliers": outliers, "count": int(len(cat_data)),
        })
    return {"data": stats}


@app.get("/api/viz/boxplot-clientes")
def get_boxplot_clientes(stores: Optional[str] = Query(None)):
    """Distribución de transacciones por cliente, agrupada por tienda."""
    _, exp = _filter_stores(stores)
    txn_per_cust = (
        exp.groupby(["customer_id", "store_id"])["transaction_id"]
        .nunique()
        .reset_index(name="transacciones")
    )
    stats = []
    for store in sorted(txn_per_cust["store_id"].unique()):
        store_data = txn_per_cust[txn_per_cust["store_id"] == store]["transacciones"]
        q1 = float(store_data.quantile(0.25))
        median = float(store_data.median())
        q3 = float(store_data.quantile(0.75))
        iqr = q3 - q1
        whisker_low = float(max(store_data.min(), q1 - 1.5 * iqr))
        whisker_high = float(min(store_data.max(), q3 + 1.5 * iqr))
        outliers = [int(x) for x in store_data[(store_data < whisker_low) | (store_data > whisker_high)].tolist()[:100]]
        stats.append({
            "store_id": int(store), "min": whisker_low, "q1": q1,
            "median": median, "q3": q3, "max": whisker_high,
            "outliers": outliers, "count": int(len(store_data)),
        })
    return {"data": stats}


@app.get("/api/viz/correlacion")
def get_correlacion(stores: Optional[str] = Query(None)):
    """Matriz de correlación entre variables de comportamiento por cliente."""
    from fastapi.responses import Response

    _, exp = _filter_stores(stores)

    cust = exp.groupby("customer_id").agg(
        frecuencia=("transaction_id", "nunique"),
        volumen_total=("product_id", "size"),
        productos_distintos=("product_id", "nunique"),
        categorias_distintas=("category_name", lambda x: x.dropna().nunique()),
        tiendas_visitadas=("store_id", "nunique"),
    ).reset_index()

    cust["promedio_unidades_por_visita"] = (
        cust["volumen_total"] / cust["frecuencia"]
    ).round(2)

    all_cols = [
        "frecuencia", "volumen_total", "productos_distintos",
        "categorias_distintas", "tiendas_visitadas", "promedio_unidades_por_visita",
    ]
    all_labels = {
        "frecuencia": "Frecuencia",
        "volumen_total": "Volumen Total",
        "productos_distintos": "Productos Distintos",
        "categorias_distintas": "Categorías Distintas",
        "tiendas_visitadas": "Tiendas Visitadas",
        "promedio_unidades_por_visita": "Prom. Unid./Visita",
    }

    # Excluir columnas constantes (varianza 0) para evitar NaN en correlación
    cols = [c for c in all_cols if cust[c].nunique() > 1]
    labels = {k: v for k, v in all_labels.items() if k in cols}

    corr = cust[cols].corr().round(4).fillna(0)
    corr_renamed = corr.rename(index=labels, columns=labels)

    # Muestra para scatter plot
    sample = cust[cols].sample(n=min(5000, len(cust)), random_state=42)

    # Convertir todo a Python nativo float para evitar numpy NaN/Inf en JSON
    corr_values = []
    for row in corr_renamed.values:
        corr_values.append([0.0 if (pd.isna(v) or np.isinf(v)) else round(float(v), 4) for v in row])

    sample_records = []
    for _, row in sample.iterrows():
        record = {}
        for c in cols:
            v = row[c]
            if pd.isna(v) or (isinstance(v, float) and np.isinf(v)):
                record[c] = 0.0
            else:
                record[c] = round(float(v), 2)
        sample_records.append(record)

    result = {
        "matrix": {
            "labels": list(corr_renamed.columns),
            "values": corr_values,
        },
        "scatter_sample": sample_records,
        "scatter_columns": cols,
        "scatter_labels": labels,
        "total_clientes": int(len(cust)),
    }

    # Usar Response directa con json.dumps para evitar re-serialización de FastAPI
    return Response(
        content=json.dumps(result, ensure_ascii=False),
        media_type="application/json",
    )


# ═══════════════════════════════════════════════
# Health check
# ═══════════════════════════════════════════════


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "transacciones": len(_transactions),
        "unidades": len(_exploded),
        "categorias": len(_categories),
    }
