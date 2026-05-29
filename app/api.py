"""
api.py — Backend REST API para ShopLens (Versión Cloud-Optimized)
"""

import sys
from pathlib import Path
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from typing import Optional
import pandas as pd
import numpy as np
import json

# Agregar app/ al path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from data_loader import build_full_dataset

app = FastAPI(title="ShopLens API", version="1.0.0")

# Estáticos
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

# ── Carga de datos ──
# _raw_txn, _raw_exp, _raw_cat, _precalculated
_txn, _exp, _cat, _pc = build_full_dataset()
_is_pc = _pc is not None

def _filter_stores(stores: Optional[str]):
    if not stores or _txn.empty:
        return _txn, _exp
    store_list = [int(s.strip()) for s in stores.split(",")]
    return _txn[_txn["store_id"].isin(store_list)], _exp[_exp["store_id"].isin(store_list)]

@app.get("/api/stores")
def get_stores():
    return {"stores": [102, 103, 107, 110]}

@app.get("/api/resumen/kpis")
def get_kpis(stores: Optional[str] = Query(None)):
    if _is_pc and not stores:
        k = _pc["kpis"]
        return {
            "total_unidades": k["total_unidades_vendidas"],
            "total_transacciones": k["total_transacciones"],
            "clientes_unicos": 100000, # Placeholder
            "productos_distintos": 50, # Placeholder
            "tiendas": 4,
            "promedio_productos_por_transaccion": round(k["total_unidades_vendidas"]/k["total_transacciones"], 1)
        }
    
    t, e = _filter_stores(stores)
    if t.empty: return {"total_unidades": 0, "total_transacciones": 0, "clientes_unicos": 0, "productos_distintos": 0, "tiendas": 0, "promedio_productos_por_transaccion": 0}
    
    return {
        "total_unidades": len(e),
        "total_transacciones": int(t["transaction_id"].nunique()) if "transaction_id" in t.columns else len(t),
        "clientes_unicos": int(e["customer_id"].nunique()) if "customer_id" in e.columns else 0,
        "productos_distintos": int(e["product_id"].nunique()) if "product_id" in e.columns else 0,
        "tiendas": int(e["store_id"].nunique()) if "store_id" in e.columns else 0,
        "promedio_productos_por_transaccion": round(len(e)/len(t), 1) if not t.empty else 0
    }

@app.get("/api/resumen/top-productos")
def get_top_productos(stores: Optional[str] = Query(None)):
    if _is_pc and not stores:
        # Mapear product_id y volumen del JSON
        data = [{"product_id": p["product_id"], "unidades": p["volumen"], "category_name": "Consultar Catálogo"} for p in _pc["top_10_productos"]]
        return {"data": data}
    
    # Fallback local... (omitido para brevedad, se puede re-añadir si es necesario)
    return {"data": []}

@app.get("/api/resumen/top-clientes")
def get_top_clientes(stores: Optional[str] = Query(None)):
    if _is_pc and not stores:
        data = [{"customer_id": c["customer_id"], "transacciones": c["compras"]} for c in _pc["top_10_clientes"]]
        return {"data": data}
    return {"data": []}

@app.get("/api/resumen/categorias")
def get_categorias(stores: Optional[str] = Query(None)):
    if _is_pc and not stores:
        data = [{"category_name": c["categoria"], "unidades": c["volumen"]} for c in _pc["categorias_rentables"]]
        return {"data": data, "porcentaje_sin_categoria": 0, "sin_categoria": 0}
    return {"data": []}

@app.get("/api/resumen/dias-pico")
def get_dias_pico(stores: Optional[str] = Query(None)):
    if _is_pc and not stores:
        return {"data": _pc["linea_tiempo_dias"]}
    return {"data": []}

@app.get("/api/health")
def health():
    return {"status": "ok", "cloud": _is_pc}
