"""
api_client.py — Cliente HTTP para consumir el backend de ShopLens.

Toda la comunicación frontend → backend pasa por aquí.
El frontend nunca accede directamente a datos/archivos.
"""

import requests
import streamlit as st
from typing import Optional

API_BASE = "http://localhost:8000/api"


def _get(endpoint: str, params: dict = None) -> dict:
    """GET request genérico al backend."""
    try:
        resp = requests.get(f"{API_BASE}/{endpoint}", params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.ConnectionError:
        st.error(
            "No se pudo conectar al backend. "
            "Asegúrate de que el servidor esté corriendo:\n\n"
            "`uvicorn app.api:app --reload --port 8000`"
        )
        st.stop()
    except requests.HTTPError as e:
        st.error(f"Error del servidor: {e}")
        st.stop()


def _stores_param(stores: list[int]) -> Optional[str]:
    """Convierte lista de tiendas a string para query param."""
    if not stores:
        return None
    return ",".join(str(s) for s in stores)


# ── Metadata ──

def get_stores() -> list[int]:
    data = _get("stores")
    return data["stores"]


# ── Resumen Ejecutivo ──

def get_kpis(stores: list[int] = None) -> dict:
    return _get("resumen/kpis", {"stores": _stores_param(stores)})


def get_top_productos(stores: list[int] = None, limit: int = 10) -> list[dict]:
    data = _get("resumen/top-productos", {"stores": _stores_param(stores), "limit": limit})
    return data["data"]


def get_top_clientes(stores: list[int] = None, limit: int = 10) -> list[dict]:
    data = _get("resumen/top-clientes", {"stores": _stores_param(stores), "limit": limit})
    return data["data"]


def get_dias_pico(stores: list[int] = None) -> list[dict]:
    data = _get("resumen/dias-pico", {"stores": _stores_param(stores)})
    return data["data"]


def get_dias_pico_heatmap(stores: list[int] = None) -> dict:
    return _get("resumen/dias-pico-heatmap", {"stores": _stores_param(stores)})


def get_categorias(stores: list[int] = None) -> dict:
    return _get("resumen/categorias", {"stores": _stores_param(stores)})


# ── Visualizaciones Analíticas ──

def get_serie_tiempo(
    stores: list[int] = None,
    agrupacion: str = "dia",
    metrica: str = "transacciones",
) -> dict:
    return _get("viz/serie-tiempo", {
        "stores": _stores_param(stores),
        "agrupacion": agrupacion,
        "metrica": metrica,
    })


def get_serie_tiempo_por_tienda(
    stores: list[int] = None,
    metrica: str = "transacciones",
) -> list[dict]:
    data = _get("viz/serie-tiempo-por-tienda", {
        "stores": _stores_param(stores),
        "metrica": metrica,
    })
    return data["data"]


def get_boxplot_categorias(stores: list[int] = None, limit: int = 12) -> list[dict]:
    data = _get("viz/boxplot-categorias", {"stores": _stores_param(stores), "limit": limit})
    return data["data"]


def get_boxplot_clientes(stores: list[int] = None) -> list[dict]:
    data = _get("viz/boxplot-clientes", {"stores": _stores_param(stores)})
    return data["data"]


def get_correlacion(stores: list[int] = None) -> dict:
    return _get("viz/correlacion", {"stores": _stores_param(stores)})


# ── Health ──

def health() -> dict:
    return _get("health")
