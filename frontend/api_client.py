"""
api_client.py — Cliente HTTP para consumir el backend de ShopLens.

Toda la comunicación frontend → backend pasa por aquí.
El frontend nunca accede directamente a datos/archivos.
"""

import requests
import streamlit as st
from typing import Optional

API_BASE = "http://localhost:8000/api"


def _get(endpoint: str, params: dict = None, timeout: int = 60) -> dict:
    """GET request genérico al backend."""
    try:
        resp = requests.get(f"{API_BASE}/{endpoint}", params=params, timeout=timeout)
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


def _post_file(endpoint: str, file_tuple, timeout: int = 120) -> dict:
    """POST multipart/form-data."""
    try:
        resp = requests.post(f"{API_BASE}/{endpoint}", files={"file": file_tuple}, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.ConnectionError:
        st.error("No se pudo conectar al backend.")
        st.stop()
    except requests.HTTPError as e:
        st.error(f"Error del servidor: {e}")
        st.stop()


def _post(endpoint: str, timeout: int = 60) -> dict:
    try:
        resp = requests.post(f"{API_BASE}/{endpoint}", timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.ConnectionError:
        st.error("No se pudo conectar al backend.")
        st.stop()
    except requests.HTTPError as e:
        st.error(f"Error del servidor: {e}")
        st.stop()


def _stores_param(stores) -> Optional[str]:
    """Convierte lista de tiendas a string para query param."""
    if not stores:
        return None
    return ",".join(str(s) for s in stores)


# ── Metadata ──

def get_stores() -> list[int]:
    data = _get("stores")
    return data.get("stores", [])


def health() -> dict:
    return _get("health")


# ── Resumen Ejecutivo ──

def get_kpis(stores=None) -> dict:
    return _get("resumen/kpis", {"stores": _stores_param(stores)})


def get_top_productos(stores=None, limit: int = 10) -> list:
    data = _get("resumen/top-productos", {"stores": _stores_param(stores), "limit": limit})
    return data.get("data", [])


def get_top_clientes(stores=None, limit: int = 10) -> list:
    data = _get("resumen/top-clientes", {"stores": _stores_param(stores), "limit": limit})
    return data.get("data", [])


def get_dias_pico(stores=None) -> list:
    data = _get("resumen/dias-pico", {"stores": _stores_param(stores)})
    return data.get("data", [])


def get_dias_pico_heatmap(stores=None) -> dict:
    return _get("resumen/dias-pico-heatmap", {"stores": _stores_param(stores)})


def get_categorias(stores=None) -> dict:
    return _get("resumen/categorias", {"stores": _stores_param(stores)})


# ── Visualizaciones Analíticas ──

def get_serie_tiempo(stores=None, agrupacion: str = "dia", metrica: str = "transacciones") -> dict:
    return _get("viz/serie-tiempo", {
        "stores": _stores_param(stores),
        "agrupacion": agrupacion,
        "metrica": metrica,
    })


def get_serie_tiempo_por_tienda(stores=None, metrica: str = "transacciones") -> list:
    data = _get("viz/serie-tiempo-por-tienda", {
        "stores": _stores_param(stores), "metrica": metrica,
    })
    return data.get("data", [])


def get_boxplot_categorias(stores=None, limit: int = 12) -> list:
    data = _get("viz/boxplot-categorias", {"stores": _stores_param(stores), "limit": limit})
    return data.get("data", [])


def get_boxplot_clientes(stores=None) -> list:
    data = _get("viz/boxplot-clientes", {"stores": _stores_param(stores)})
    return data.get("data", [])


def get_correlacion(stores=None) -> dict:
    return _get("viz/correlacion", {"stores": _stores_param(stores)})


# ── Análisis Avanzado ──

def get_segmentacion(stores=None, k: int = 4, sample_size: int = 8000) -> dict:
    return _get("avanzado/segmentacion", {
        "stores": _stores_param(stores), "k": k, "sample_size": sample_size,
    }, timeout=300)


def get_segmentacion_cliente(customer_id: int, stores=None, k: int = 4) -> dict:
    return _get(f"avanzado/segmentacion/cliente/{customer_id}", {
        "stores": _stores_param(stores), "k": k,
    }, timeout=300)


def recomendar_producto(product_id: int, stores=None, top: int = 10) -> dict:
    return _get(f"avanzado/recomendar/producto/{product_id}", {
        "stores": _stores_param(stores), "top": top,
    }, timeout=300)


def recomendar_cliente(customer_id: int, stores=None, top: int = 10) -> dict:
    return _get(f"avanzado/recomendar/cliente/{customer_id}", {
        "stores": _stores_param(stores), "top": top,
    }, timeout=300)


def productos_populares(stores=None, limit: int = 50) -> list:
    data = _get("avanzado/productos-populares", {
        "stores": _stores_param(stores), "limit": limit,
    })
    return data.get("data", [])


def clientes_frecuentes(stores=None, limit: int = 50) -> list:
    data = _get("avanzado/clientes-frecuentes", {
        "stores": _stores_param(stores), "limit": limit,
    })
    return data.get("data", [])


def cargar_nuevos_datos(filename: str, content: bytes) -> dict:
    return _post_file("avanzado/cargar-nuevos-datos", (filename, content, "text/csv"), timeout=300)


def recargar_dataset() -> dict:
    return _post("avanzado/recargar", timeout=300)
