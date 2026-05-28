"""
ShopLens Frontend — Dashboard de Analítica de Supermercado
==========================================================

Este frontend consume exclusivamente la API REST del backend.
No accede directamente a archivos de datos ni a la base de datos.

Ejecutar:
    1. Primero el backend:  uvicorn app.api:app --reload --port 8000
    2. Luego el frontend:   streamlit run frontend/app.py
"""

import streamlit as st
import sys
from pathlib import Path

# Agregar frontend/ al path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import api_client as api

# ── Configuración de la página ──
st.set_page_config(
    page_title="ShopLens — Analítica de Supermercado",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS personalizado ──
st.markdown(
    """
    <style>
    .block-container { padding-top: 1rem; }
    [data-testid="stMetric"] {
        background-color: #f0f2f6;
        padding: 12px 16px;
        border-radius: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Sidebar ──
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/shopping-cart.png", width=60)
    st.title("ShopLens")
    st.caption("Analítica de Transacciones de Supermercado")
    st.divider()

    module = st.radio(
        "Módulo:",
        ["Resumen Ejecutivo", "Visualizaciones Analíticas", "Análisis Avanzado"],
        index=0,
    )

    st.divider()

    # Filtro global de tiendas
    all_stores = api.get_stores()
    selected_stores = st.multiselect(
        "Filtrar por tienda:",
        options=all_stores,
        default=all_stores,
        format_func=lambda x: f"Tienda {x}",
        key="global_stores",
    )

    st.divider()
    st.markdown(
        """
        **Dataset:** 4 tiendas, 6 meses
        **Período:** Ene — Jun 2013
        **Registros:** ~1.1M transacciones
        """
    )

    # Health check
    try:
        h = api.health()
        st.success(f"Backend OK — {h['transacciones']:,} transacciones")
    except Exception:
        st.error("Backend no disponible")

# ── Validación ──
if not selected_stores:
    st.warning("Selecciona al menos una tienda en el panel lateral.")
    st.stop()

# ── Routing de módulos ──
if module == "Resumen Ejecutivo":
    from pages.resumen_ejecutivo import render
    render(selected_stores)

elif module == "Visualizaciones Analíticas":
    from pages.visualizaciones import render
    render(selected_stores)

elif module == "Análisis Avanzado":
    st.header("🧠 Análisis Avanzado")
    st.info(
        "Este módulo se habilitará en la próxima entrega (Junio 5-10).\n\n"
        "Incluirá:\n"
        "- **Segmentación de Clientes** (K-Means)\n"
        "- **Recomendador de Productos** (Filtrado Colaborativo / Reglas de Asociación)\n"
        "- **Incorporación de Nuevos Datos**"
    )
