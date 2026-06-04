"""
api.py — Backend REST API para ShopLens.

Estrategia:
- Usa los datos locales (pandas) como fuente principal -> permite filtrado por tienda y análisis avanzado.
- Si hay precalculados (Azure / local), se usan como atajo solo cuando NO hay filtro y para los KPIs globales.
- Todos los endpoints son tolerantes a respuestas vacías.
"""

import sys
import json
from pathlib import Path
from typing import Optional, List

import pandas as pd
import numpy as np
from fastapi import FastAPI, Query, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response

# Agregar app/ al path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from data_loader import build_full_dataset, reload_dataset

# ════════════════════════════════════════════════════════════
#  Inicialización
# ════════════════════════════════════════════════════════════

app = FastAPI(title="ShopLens API", version="2.0.0")

static_path = Path(__file__).resolve().parent / "static"
static_path.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_txn, _exp, _cat, _pc = build_full_dataset()
# NOTA: el precalculado de Spark tiene cifras infladas porque se calculó ANTES
# de la corrección de duplicación de categorías. Solo lo usamos cuando no hay
# datos locales (fallback). En la práctica, _txn no debería estar vacío.
_is_pc = _pc is not None and _txn.empty

# Cache para análisis pesados (segmentación, recomendador)
_advanced_cache = {}


def _reset_globals():
    """Recarga datasets desde disco e invalida caché de análisis."""
    global _txn, _exp, _cat, _pc, _is_pc
    _txn, _exp, _cat, _pc = reload_dataset()
    _is_pc = _pc is not None
    _advanced_cache.clear()


# ════════════════════════════════════════════════════════════
#  Helpers
# ════════════════════════════════════════════════════════════

def _filter_stores(stores: Optional[str]):
    """Devuelve (txn_filtrado, exp_filtrado)."""
    if not stores or _txn.empty:
        return _txn, _exp
    try:
        store_list = [int(s.strip()) for s in stores.split(",") if s.strip()]
    except ValueError:
        return _txn, _exp
    if not store_list:
        return _txn, _exp
    return (
        _txn[_txn["store_id"].isin(store_list)],
        _exp[_exp["store_id"].isin(store_list)],
    )


def _safe_json(obj):
    """Convierte recursivamente np.nan/inf y tipos numpy a Python nativo."""
    if isinstance(obj, dict):
        return {k: _safe_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_safe_json(v) for v in obj]
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        return 0.0 if (np.isnan(v) or np.isinf(v)) else v
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, float):
        return 0.0 if (pd.isna(obj) or np.isinf(obj)) else obj
    if isinstance(obj, pd.Timestamp):
        return obj.strftime("%Y-%m-%d")
    return obj


# ════════════════════════════════════════════════════════════
#  Endpoints base
# ════════════════════════════════════════════════════════════

@app.get("/")
def read_index():
    idx = static_path / "index.html"
    if idx.exists():
        return FileResponse(idx)
    return {"app": "ShopLens API", "docs": "/docs"}


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "cloud": _is_pc,
        "transacciones": int(len(_txn)),
        "exploded_rows": int(len(_exp)),
        "categorias": int(len(_cat)),
        "endpoints": 22,
    }


@app.get("/api/stores")
def get_stores():
    if _txn.empty:
        return {"stores": [102, 103, 107, 110]}
    return {"stores": sorted(_txn["store_id"].unique().tolist())}


# ════════════════════════════════════════════════════════════
#  RESUMEN EJECUTIVO
# ════════════════════════════════════════════════════════════

@app.get("/api/resumen/kpis")
def get_kpis(stores: Optional[str] = Query(None)):
    t, e = _filter_stores(stores)

    if t.empty:
        # Si no hay datos locales pero sí precalculado y no hay filtro
        if _is_pc and not stores:
            k = _pc["kpis"]
            return {
                "total_unidades": k["total_unidades_vendidas"],
                "total_transacciones": k["total_transacciones"],
                "clientes_unicos": 0,
                "productos_distintos": 0,
                "tiendas": 4,
                "promedio_productos_por_transaccion": round(
                    k["total_unidades_vendidas"] / max(k["total_transacciones"], 1), 1
                ),
            }
        return {
            "total_unidades": 0, "total_transacciones": 0, "clientes_unicos": 0,
            "productos_distintos": 0, "tiendas": 0,
            "promedio_productos_por_transaccion": 0,
        }

    return {
        "total_unidades": int(len(e)),
        "total_transacciones": int(t["transaction_id"].nunique()),
        "clientes_unicos": int(e["customer_id"].nunique()) if "customer_id" in e.columns else 0,
        "productos_distintos": int(e["product_id"].nunique()) if "product_id" in e.columns else 0,
        "tiendas": int(t["store_id"].nunique()),
        "promedio_productos_por_transaccion": round(len(e) / max(len(t), 1), 1),
    }


@app.get("/api/resumen/top-productos")
def get_top_productos(stores: Optional[str] = Query(None), limit: int = Query(10)):
    _, e = _filter_stores(stores)
    if e.empty:
        if _is_pc and not stores:
            data = [
                {"product_id": int(p["product_id"]), "unidades": int(p["volumen"]),
                 "category_name": "N/A"}
                for p in _pc.get("top_10_productos", [])
            ]
            return {"data": data[:limit]}
        return {"data": []}
    top = (
        e.groupby("product_id")
        .agg(unidades=("product_id", "size"),
             category_name=("category_name", lambda x: x.dropna().iloc[0] if x.dropna().size else None))
        .reset_index()
        .nlargest(limit, "unidades")
    )
    top["product_id"] = top["product_id"].astype(int)
    top["unidades"] = top["unidades"].astype(int)
    top["category_name"] = top.apply(
        lambda r: r["category_name"] if pd.notna(r["category_name"]) else f"Producto #{r['product_id']} (sin clasificar)",
        axis=1,
    )
    return {"data": top.to_dict(orient="records")}


@app.get("/api/resumen/top-clientes")
def get_top_clientes(stores: Optional[str] = Query(None), limit: int = Query(10)):
    t, _ = _filter_stores(stores)
    if t.empty:
        if _is_pc and not stores:
            data = [
                {"customer_id": int(c["customer_id"]), "transacciones": int(c["compras"])}
                for c in _pc.get("top_10_clientes", [])
            ]
            return {"data": data[:limit]}
        return {"data": []}
    top = (
        t.groupby("customer_id")["transaction_id"].nunique()
        .reset_index(name="transacciones")
        .nlargest(limit, "transacciones")
    )
    top["customer_id"] = top["customer_id"].astype(int)
    top["transacciones"] = top["transacciones"].astype(int)
    return {"data": top.to_dict(orient="records")}


@app.get("/api/resumen/categorias")
def get_categorias(stores: Optional[str] = Query(None)):
    _, e = _filter_stores(stores)
    if e.empty:
        if _is_pc and not stores:
            data = [{"category_name": c["categoria"], "unidades": int(c["volumen"]), "transacciones": 0}
                    for c in _pc.get("categorias_rentables", [])]
            return {"data": data, "porcentaje_sin_categoria": 0, "sin_categoria": 0}
        return {"data": [], "porcentaje_sin_categoria": 0, "sin_categoria": 0}

    total = len(e)
    sin = int(e["category_name"].isna().sum()) if "category_name" in e.columns else 0
    con = e.dropna(subset=["category_name"]) if "category_name" in e.columns else e
    cats = (
        con.groupby("category_name")
        .agg(unidades=("product_id", "size"),
             transacciones=("transaction_id", "nunique"))
        .reset_index()
        .sort_values("unidades", ascending=False)
    )
    cats["unidades"] = cats["unidades"].astype(int)
    cats["transacciones"] = cats["transacciones"].astype(int)
    return {
        "data": cats.to_dict(orient="records"),
        "porcentaje_sin_categoria": round(sin / max(total, 1) * 100, 2),
        "sin_categoria": sin,
    }


@app.get("/api/resumen/dias-pico")
def get_dias_pico(stores: Optional[str] = Query(None)):
    t, _ = _filter_stores(stores)
    if t.empty:
        if _is_pc and not stores:
            return {"data": _pc.get("linea_tiempo_dias", [])}
        return {"data": []}
    daily = (
        t.groupby(t["date"].dt.date)["transaction_id"].nunique()
        .reset_index(name="transacciones")
        .rename(columns={"date": "fecha"})
    )
    daily["fecha"] = pd.to_datetime(daily["fecha"]).dt.strftime("%Y-%m-%d")
    daily["transacciones"] = daily["transacciones"].astype(int)
    return {"data": daily.to_dict(orient="records")}


@app.get("/api/resumen/dias-pico-heatmap")
def get_dias_pico_heatmap(stores: Optional[str] = Query(None)):
    day_names = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    t, _ = _filter_stores(stores)
    if t.empty or "date" not in t.columns:
        return {"data": [], "day_order": day_names}
    tc = t.copy()
    tc["dow"] = tc["date"].dt.dayofweek
    tc["week"] = tc["date"].dt.isocalendar().week.astype(int)
    hm = tc.groupby(["week", "dow"])["transaction_id"].nunique().reset_index(name="transacciones")
    hm["dia"] = hm["dow"].map(lambda x: day_names[x])
    hm["transacciones"] = hm["transacciones"].astype(int)
    hm["week"] = hm["week"].astype(int)
    return {"data": hm[["week", "dia", "transacciones"]].to_dict(orient="records"), "day_order": day_names}


# ════════════════════════════════════════════════════════════
#  VISUALIZACIONES ANALÍTICAS
# ════════════════════════════════════════════════════════════

@app.get("/api/viz/serie-tiempo")
def get_serie_tiempo(
    stores: Optional[str] = Query(None),
    agrupacion: str = Query("dia", pattern="^(dia|semana|mes)$"),
    metrica: str = Query("transacciones", pattern="^(transacciones|unidades)$"),
):
    t, e = _filter_stores(stores)
    source = t if metrica == "transacciones" else e
    if source.empty or "date" not in source.columns:
        # Atajo precalculado solo para día/transacciones global
        if _is_pc and not stores and agrupacion == "dia" and metrica == "transacciones":
            dias = _pc.get("linea_tiempo_dias", [])
            data = [{"periodo": d["fecha"], "valor": int(d["transacciones"])} for d in dias]
            mm = None
            if len(data) > 7:
                vals = [d["valor"] for d in data]
                mm = []
                for i in range(3, len(vals) - 3):
                    mm.append({"periodo": data[i]["periodo"],
                               "media_movil": round(sum(vals[i-3:i+4]) / 7, 1)})
            return {"data": data, "media_movil": mm}
        return {"data": [], "media_movil": None}

    sc = source[["date", "transaction_id"]].copy()
    if agrupacion == "dia":
        sc["periodo"] = sc["date"].dt.date
    elif agrupacion == "semana":
        sc["periodo"] = sc["date"].dt.to_period("W").apply(lambda r: r.start_time)
    else:
        sc["periodo"] = sc["date"].dt.to_period("M").apply(lambda r: r.start_time)

    if metrica == "transacciones":
        ts = sc.groupby("periodo")["transaction_id"].nunique().reset_index(name="valor")
    else:
        ts = sc.groupby("periodo").size().reset_index(name="valor")
    ts["periodo"] = pd.to_datetime(ts["periodo"]).dt.strftime("%Y-%m-%d")
    ts["valor"] = ts["valor"].astype(int)
    ts = ts.sort_values("periodo").reset_index(drop=True)

    mm = None
    if agrupacion == "dia" and len(ts) > 7:
        rolled = ts["valor"].rolling(window=7, center=True).mean().round(1)
        mm_df = pd.DataFrame({"periodo": ts["periodo"], "media_movil": rolled}).dropna()
        mm = mm_df.to_dict(orient="records")

    return {"data": ts.to_dict(orient="records"), "media_movil": mm}


@app.get("/api/viz/serie-tiempo-por-tienda")
def get_serie_tiempo_por_tienda(
    stores: Optional[str] = Query(None),
    metrica: str = Query("transacciones", pattern="^(transacciones|unidades)$"),
):
    t, e = _filter_stores(stores)
    source = (t if metrica == "transacciones" else e).copy()
    if source.empty or "date" not in source.columns:
        return {"data": []}
    source["periodo"] = source["date"].dt.to_period("W").apply(lambda r: r.start_time)
    if metrica == "transacciones":
        ts = source.groupby(["periodo", "store_id"])["transaction_id"].nunique().reset_index(name="valor")
    else:
        ts = source.groupby(["periodo", "store_id"]).size().reset_index(name="valor")
    ts["periodo"] = pd.to_datetime(ts["periodo"]).dt.strftime("%Y-%m-%d")
    ts["store_id"] = ts["store_id"].astype(int)
    ts["valor"] = ts["valor"].astype(int)
    return {"data": ts.to_dict(orient="records")}


@app.get("/api/viz/boxplot-categorias")
def get_boxplot_categorias(stores: Optional[str] = Query(None), limit: int = Query(12)):
    _, exp = _filter_stores(stores)
    if exp.empty or "category_name" not in exp.columns:
        return {"data": []}
    units = (
        exp.dropna(subset=["category_name"])
        .groupby(["transaction_id", "category_name"])
        .size().reset_index(name="unidades")
    )
    if units.empty:
        return {"data": []}
    top_cats = units.groupby("category_name")["unidades"].sum().nlargest(limit).index.tolist()
    filtered = units[units["category_name"].isin(top_cats)]
    stats = []
    for cat in top_cats:
        cd = filtered[filtered["category_name"] == cat]["unidades"]
        if cd.empty:
            continue
        q1, med, q3 = float(cd.quantile(0.25)), float(cd.median()), float(cd.quantile(0.75))
        iqr = q3 - q1
        wl = float(max(cd.min(), q1 - 1.5 * iqr))
        wh = float(min(cd.max(), q3 + 1.5 * iqr))
        stats.append({"category_name": cat, "min": wl, "q1": q1, "median": med,
                      "q3": q3, "max": wh, "count": int(len(cd))})
    return {"data": stats}


@app.get("/api/viz/boxplot-clientes")
def get_boxplot_clientes(stores: Optional[str] = Query(None)):
    _, exp = _filter_stores(stores)
    if exp.empty:
        return {"data": []}
    tpc = exp.groupby(["customer_id", "store_id"])["transaction_id"].nunique().reset_index(name="transacciones")
    stats = []
    for store in sorted(tpc["store_id"].unique()):
        sd = tpc[tpc["store_id"] == store]["transacciones"]
        q1, med, q3 = float(sd.quantile(0.25)), float(sd.median()), float(sd.quantile(0.75))
        iqr = q3 - q1
        wl = float(max(sd.min(), q1 - 1.5 * iqr))
        wh = float(min(sd.max(), q3 + 1.5 * iqr))
        stats.append({"store_id": int(store), "min": wl, "q1": q1, "median": med,
                      "q3": q3, "max": wh, "count": int(len(sd))})
    return {"data": stats}


def _customer_features(exp):
    """Calcula features por cliente (usado en correlación y K-Means)."""
    cust = exp.groupby("customer_id").agg(
        frecuencia=("transaction_id", "nunique"),
        volumen_total=("product_id", "size"),
        productos_distintos=("product_id", "nunique"),
        categorias_distintas=("category_name", lambda x: x.dropna().nunique()),
        tiendas_visitadas=("store_id", "nunique"),
    ).reset_index()
    cust["promedio_unidades_por_visita"] = (cust["volumen_total"] / cust["frecuencia"]).round(2)
    return cust


@app.get("/api/viz/correlacion")
def get_correlacion(stores: Optional[str] = Query(None)):
    _, exp = _filter_stores(stores)
    if exp.empty:
        return {"matrix": {"labels": [], "values": []}, "scatter_sample": [],
                "scatter_columns": [], "scatter_labels": {}, "total_clientes": 0}

    cust = _customer_features(exp)
    all_cols = ["frecuencia", "volumen_total", "productos_distintos",
                "categorias_distintas", "tiendas_visitadas", "promedio_unidades_por_visita"]
    all_labels = {
        "frecuencia": "Frecuencia", "volumen_total": "Volumen Total",
        "productos_distintos": "Productos Distintos", "categorias_distintas": "Categorías Distintas",
        "tiendas_visitadas": "Tiendas Visitadas", "promedio_unidades_por_visita": "Prom. Unid./Visita",
    }
    cols = [c for c in all_cols if cust[c].nunique() > 1]
    labels = {k: v for k, v in all_labels.items() if k in cols}
    corr = cust[cols].corr().round(4).fillna(0)
    corr_renamed = corr.rename(index=labels, columns=labels)

    sample = cust[cols].sample(n=min(5000, len(cust)), random_state=42)

    corr_values = [[0.0 if (pd.isna(v) or np.isinf(v)) else round(float(v), 4) for v in row]
                   for row in corr_renamed.values]
    sample_records = []
    for _, row in sample.iterrows():
        rec = {c: (0.0 if pd.isna(row[c]) or np.isinf(row[c]) else round(float(row[c]), 2)) for c in cols}
        sample_records.append(rec)

    payload = {
        "matrix": {"labels": list(corr_renamed.columns), "values": corr_values},
        "scatter_sample": sample_records,
        "scatter_columns": cols,
        "scatter_labels": labels,
        "total_clientes": int(len(cust)),
    }
    return Response(content=json.dumps(payload, ensure_ascii=False), media_type="application/json")


# ════════════════════════════════════════════════════════════
#  ANÁLISIS AVANZADO  ─ Segmentación de Clientes (K-Means)
# ════════════════════════════════════════════════════════════

@app.get("/api/avanzado/segmentacion")
def get_segmentacion(
    stores: Optional[str] = Query(None),
    k: int = Query(4, ge=2, le=10),
    sample_size: int = Query(8000, ge=200, le=20000),
):
    """Segmenta clientes con K-Means. Devuelve estadísticas por cluster y muestra para scatter."""
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    from sklearn.decomposition import PCA

    _, exp = _filter_stores(stores)
    if exp.empty:
        return {"clusters": [], "scatter": [], "feature_labels": {}, "total_clientes": 0, "k": k}

    cache_key = (stores or "all", k)
    if cache_key in _advanced_cache:
        return _advanced_cache[cache_key]

    cust = _customer_features(exp)
    feature_cols = ["frecuencia", "volumen_total", "productos_distintos",
                    "categorias_distintas", "tiendas_visitadas", "promedio_unidades_por_visita"]
    labels = {
        "frecuencia": "Frecuencia", "volumen_total": "Volumen Total",
        "productos_distintos": "Productos Distintos", "categorias_distintas": "Categorías Distintas",
        "tiendas_visitadas": "Tiendas Visitadas", "promedio_unidades_por_visita": "Prom. Unid./Visita",
    }
    feature_cols = [c for c in feature_cols if cust[c].nunique() > 1]

    X = cust[feature_cols].fillna(0).values
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    cust["cluster"] = km.fit_predict(Xs)

    # Etiqueta semántica basada en volumen y frecuencia
    cluster_stats = []
    cluster_means = cust.groupby("cluster")[feature_cols].mean()
    for c in sorted(cust["cluster"].unique()):
        sub = cust[cust["cluster"] == c]
        means = sub[feature_cols].mean()
        cluster_stats.append({
            "cluster": int(c),
            "n_clientes": int(len(sub)),
            "porcentaje": round(len(sub) / max(len(cust), 1) * 100, 1),
            "metricas": {col: round(float(means[col]), 2) for col in feature_cols},
        })

    # Etiquetar clusters: VIP (alto volumen+freq), Frecuente, Casual, Único/Visitante
    if "volumen_total" in feature_cols and "frecuencia" in feature_cols:
        ranking = cluster_means[["volumen_total", "frecuencia"]].sum(axis=1).sort_values(ascending=False)
        nombres_por_rank = ["VIP", "Frecuentes", "Casuales", "Esporádicos", "Inactivos",
                            "Grupo 6", "Grupo 7", "Grupo 8", "Grupo 9", "Grupo 10"]
        rank_map = {cl: nombres_por_rank[i] for i, cl in enumerate(ranking.index.tolist())}
        for cs in cluster_stats:
            cs["nombre"] = rank_map.get(cs["cluster"], f"Grupo {cs['cluster']}")
    else:
        for cs in cluster_stats:
            cs["nombre"] = f"Grupo {cs['cluster']}"

    # PCA 2D para el scatter
    pca = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(Xs)
    cust["pc1"] = coords[:, 0]
    cust["pc2"] = coords[:, 1]
    sample = cust.sample(n=min(sample_size, len(cust)), random_state=42)
    scatter = [
        {
            "customer_id": int(r.customer_id),
            "pc1": round(float(r.pc1), 3),
            "pc2": round(float(r.pc2), 3),
            "cluster": int(r.cluster),
        }
        for r in sample.itertuples()
    ]

    payload = {
        "k": k,
        "clusters": cluster_stats,
        "scatter": scatter,
        "feature_labels": labels,
        "feature_cols": feature_cols,
        "total_clientes": int(len(cust)),
        "varianza_explicada": [round(float(v) * 100, 1) for v in pca.explained_variance_ratio_],
        "inertia": float(km.inertia_),
    }
    _advanced_cache[cache_key] = payload
    return payload


@app.get("/api/avanzado/segmentacion/cliente/{customer_id}")
def get_segmentacion_cliente(customer_id: int, stores: Optional[str] = Query(None), k: int = Query(4)):
    """Dado un cliente, devuelve el cluster al que pertenece y sus métricas."""
    data = get_segmentacion(stores=stores, k=k)
    match = [s for s in data["scatter"] if s["customer_id"] == customer_id]
    if not match:
        return {"encontrado": False, "customer_id": customer_id}
    cl = match[0]["cluster"]
    cluster_info = next((c for c in data["clusters"] if c["cluster"] == cl), None)
    return {"encontrado": True, "customer_id": customer_id, "cluster": cl, "info": cluster_info}


# ════════════════════════════════════════════════════════════
#  ANÁLISIS AVANZADO ─ Recomendador (reglas de asociación)
# ════════════════════════════════════════════════════════════

def _build_cooccurrence(stores: Optional[str], min_count: int = 50):
    """Construye matriz de co-ocurrencia producto-producto (cacheada)."""
    cache_key = ("cooc", stores or "all", min_count)
    if cache_key in _advanced_cache:
        return _advanced_cache[cache_key]

    _, exp = _filter_stores(stores)
    if exp.empty:
        result = (None, None, None)
        _advanced_cache[cache_key] = result
        return result

    # Filtrar a productos populares (umbral) para acotar la matriz
    prod_count = exp.groupby("product_id").size()
    populares = prod_count[prod_count >= min_count].index
    sub = exp[exp["product_id"].isin(populares)]

    # Total de transacciones por producto (soporte individual)
    prod_txn = sub.groupby("product_id")["transaction_id"].nunique()

    # Co-ocurrencia: para cada transacción, lista de productos únicos
    by_txn = sub.groupby("transaction_id")["product_id"].apply(lambda s: tuple(sorted(set(s))))

    # Contar pares (limitar a transacciones con ≤25 productos para evitar explosión)
    from itertools import combinations
    pair_counts = {}
    for plist in by_txn:
        if len(plist) > 25 or len(plist) < 2:
            continue
        for a, b in combinations(plist, 2):
            pair_counts[(a, b)] = pair_counts.get((a, b), 0) + 1

    # Mapa producto → categoría (para etiquetar). Para productos sin categoría,
    # usamos "Producto N° X" para distinguirlos en vez de un genérico "Sin categoría".
    prod_cat = sub.dropna(subset=["category_name"]).drop_duplicates("product_id").set_index("product_id")["category_name"]

    result = (pair_counts, prod_txn, prod_cat)
    _advanced_cache[cache_key] = result
    return result


def _cat_label(prod_cat, pid):
    """Devuelve la categoría del producto o 'Producto N° X (sin clasificar)' si falta."""
    cat = prod_cat.get(pid) if prod_cat is not None else None
    if cat is None or pd.isna(cat):
        return f"Producto #{int(pid)} (sin clasificar)"
    return str(cat)


@app.get("/api/avanzado/recomendar/producto/{product_id}")
def recomendar_por_producto(
    product_id: int,
    stores: Optional[str] = Query(None),
    top: int = Query(10, ge=1, le=30),
):
    """Recomienda productos comprados junto al dado (lift/confidence)."""
    pair_counts, prod_txn, prod_cat = _build_cooccurrence(stores)
    if not pair_counts:
        return {"product_id": product_id, "recomendaciones": []}

    total_txn = int(prod_txn.sum() / max(prod_txn.size, 1))  # aprox
    base = int(prod_txn.get(product_id, 0))
    if base == 0:
        return {"product_id": product_id, "recomendaciones": [], "razon": "Producto no encontrado"}

    recos = []
    for (a, b), cnt in pair_counts.items():
        other = None
        if a == product_id:
            other = b
        elif b == product_id:
            other = a
        if other is None:
            continue
        sup_other = int(prod_txn.get(other, 0))
        if sup_other == 0:
            continue
        confidence = cnt / base
        # lift sencillo (aproximación; sin total exacto, usamos ratio)
        lift = (cnt / base) / (sup_other / max(prod_txn.sum(), 1))
        recos.append({
            "product_id": int(other),
            "category_name": _cat_label(prod_cat, other),
            "co_ocurrencias": int(cnt),
            "confianza": round(float(confidence), 3),
            "lift": round(float(lift), 2),
        })

    recos.sort(key=lambda x: (x["lift"], x["co_ocurrencias"]), reverse=True)
    return {
        "product_id": product_id,
        "base_transacciones": base,
        "category_name": _cat_label(prod_cat, product_id),
        "recomendaciones": recos[:top],
    }


@app.get("/api/avanzado/recomendar/cliente/{customer_id}")
def recomendar_por_cliente(
    customer_id: int,
    stores: Optional[str] = Query(None),
    top: int = Query(10, ge=1, le=30),
):
    """Recomienda productos para un cliente basándose en lo que ya compró."""
    pair_counts, prod_txn, prod_cat = _build_cooccurrence(stores)
    if not pair_counts:
        return {"customer_id": customer_id, "recomendaciones": []}

    _, exp = _filter_stores(stores)
    if exp.empty:
        return {"customer_id": customer_id, "recomendaciones": []}

    comprados = set(exp[exp["customer_id"] == customer_id]["product_id"].dropna().astype(int).tolist())
    if not comprados:
        return {"customer_id": customer_id, "recomendaciones": [], "razon": "Cliente sin historial"}

    scores = {}
    for (a, b), cnt in pair_counts.items():
        if a in comprados and b not in comprados:
            scores[b] = scores.get(b, 0) + cnt
        elif b in comprados and a not in comprados:
            scores[a] = scores.get(a, 0) + cnt

    ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top]
    recos = [{
        "product_id": int(pid),
        "category_name": _cat_label(prod_cat, pid),
        "score": int(score),
    } for pid, score in ranking]

    return {
        "customer_id": customer_id,
        "productos_comprados": len(comprados),
        "recomendaciones": recos,
    }


@app.get("/api/avanzado/productos-populares")
def productos_populares(stores: Optional[str] = Query(None), limit: int = Query(50)):
    """Lista de productos populares para usar en el dropdown del recomendador."""
    _, exp = _filter_stores(stores)
    if exp.empty:
        return {"data": []}
    top = (
        exp.groupby("product_id")
        .agg(transacciones=("transaction_id", "nunique"),
             category_name=("category_name", lambda x: x.dropna().iloc[0] if x.dropna().size else None))
        .reset_index()
        .nlargest(limit, "transacciones")
    )
    top["product_id"] = top["product_id"].astype(int)
    top["transacciones"] = top["transacciones"].astype(int)
    top["category_name"] = top.apply(
        lambda r: r["category_name"] if pd.notna(r["category_name"]) else f"Producto #{r['product_id']} (sin clasificar)",
        axis=1,
    )
    return {"data": top.to_dict(orient="records")}


@app.get("/api/avanzado/clientes-frecuentes")
def clientes_frecuentes(stores: Optional[str] = Query(None), limit: int = Query(50)):
    """Lista de clientes frecuentes para usar en el dropdown del recomendador."""
    t, _ = _filter_stores(stores)
    if t.empty:
        return {"data": []}
    top = (
        t.groupby("customer_id")["transaction_id"].nunique()
        .reset_index(name="transacciones").nlargest(limit, "transacciones")
    )
    top["customer_id"] = top["customer_id"].astype(int)
    top["transacciones"] = top["transacciones"].astype(int)
    return {"data": top.to_dict(orient="records")}


# ════════════════════════════════════════════════════════════
#  ANÁLISIS AVANZADO ─ Incorporación de Nuevos Datos
# ════════════════════════════════════════════════════════════

@app.post("/api/avanzado/cargar-nuevos-datos")
async def cargar_nuevos_datos(file: UploadFile = File(...)):
    """Recibe un archivo *_Tran.csv y lo guarda en ShopLens/nuevos_datos/, luego recarga el dataset."""
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos .csv")

    dest_dir = Path(__file__).resolve().parent.parent / "nuevos_datos"
    dest_dir.mkdir(exist_ok=True)
    dest = dest_dir / file.filename
    content = await file.read()
    dest.write_bytes(content)

    # Recargar
    prev_rows = len(_txn)
    _reset_globals()
    nuevos = len(_txn) - prev_rows
    return {
        "ok": True,
        "filename": file.filename,
        "bytes": len(content),
        "transacciones_previas": prev_rows,
        "transacciones_actuales": len(_txn),
        "incorporadas": nuevos,
    }


@app.post("/api/avanzado/recargar")
def recargar():
    """Recarga el dataset desde disco sin recibir archivo."""
    prev = len(_txn)
    _reset_globals()
    return {"ok": True, "transacciones_previas": prev, "transacciones_actuales": len(_txn)}
