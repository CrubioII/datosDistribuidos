"""
Módulo 1: Resumen Ejecutivo
Consume datos del backend vía api_client.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import sys
from pathlib import Path

# Agregar frontend/ al path para importar api_client
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import api_client as api


def render(selected_stores: list[int]):
    st.header("📊 Resumen Ejecutivo")

    # ── KPIs ──
    kpis = api.get_kpis(selected_stores)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Unidades Vendidas", f"{kpis['total_unidades']:,.0f}")
    col2.metric("Transacciones", f"{kpis['total_transacciones']:,.0f}")
    col3.metric("Clientes Únicos", f"{kpis['clientes_unicos']:,.0f}")

    col4, col5, col6 = st.columns(3)
    col4.metric("Productos Distintos", f"{kpis['productos_distintos']:,.0f}")
    col5.metric("Tiendas", f"{kpis['tiendas']}")
    col6.metric("Promedio Prod/Transacción", f"{kpis['promedio_productos_por_transaccion']}")

    st.divider()

    # ── Top 10 Productos ──
    st.subheader("Top 10 Productos Más Comprados")
    top_prod = pd.DataFrame(api.get_top_productos(selected_stores))

    top_prod["label"] = top_prod.apply(
        lambda r: f"Prod. {r['product_id']} ({r['category_name']})", axis=1
    )

    fig = px.bar(
        top_prod, y="label", x="unidades", orientation="h",
        text="unidades", color="unidades", color_continuous_scale="Blues",
    )
    fig.update_layout(
        yaxis=dict(autorange="reversed", title=""),
        xaxis_title="Unidades Vendidas",
        coloraxis_showscale=False, height=400,
    )
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

    # ── Top 10 Clientes ──
    st.subheader("Top 10 Clientes con Más Compras")
    top_cli = pd.DataFrame(api.get_top_clientes(selected_stores))
    top_cli["label"] = "Cliente " + top_cli["customer_id"].astype(str)

    fig2 = px.bar(
        top_cli, y="label", x="transacciones", orientation="h",
        text="transacciones", color="transacciones", color_continuous_scale="Greens",
        hover_data=["unidades", "productos_distintos"],
    )
    fig2.update_layout(
        yaxis=dict(autorange="reversed", title=""),
        xaxis_title="Número de Transacciones",
        coloraxis_showscale=False, height=400,
    )
    fig2.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    st.plotly_chart(fig2, use_container_width=True)

    # ── Días Pico ──
    st.subheader("Días Pico de Compra")
    tab1, tab2 = st.tabs(["Serie de Tiempo", "Heatmap Semanal"])

    with tab1:
        daily = pd.DataFrame(api.get_dias_pico(selected_stores))
        fig3 = px.line(daily, x="fecha", y="transacciones",
                       labels={"fecha": "Fecha", "transacciones": "Transacciones"})
        fig3.update_layout(height=350)
        st.plotly_chart(fig3, use_container_width=True)

    with tab2:
        hm_data = api.get_dias_pico_heatmap(selected_stores)
        hm_df = pd.DataFrame(hm_data["data"])
        day_order = hm_data["day_order"]

        pivot = hm_df.pivot(index="dia", columns="week", values="transacciones")
        pivot = pivot.reindex(day_order)

        fig4 = px.imshow(
            pivot,
            labels=dict(x="Semana del Año", y="Día", color="Transacciones"),
            color_continuous_scale="YlOrRd", aspect="auto",
        )
        fig4.update_layout(height=350)
        st.plotly_chart(fig4, use_container_width=True)

    # ── Categorías ──
    st.subheader("Categorías con Mayor Volumen de Ventas")
    cat_data = api.get_categorias(selected_stores)
    cat_df = pd.DataFrame(cat_data["data"])

    col_a, col_b = st.columns(2)

    with col_a:
        top_cat = cat_df.head(10)
        fig5 = px.bar(
            top_cat, y="category_name", x="unidades", orientation="h",
            text="unidades", color="unidades", color_continuous_scale="Oranges",
        )
        fig5.update_layout(
            yaxis=dict(autorange="reversed", title=""),
            xaxis_title="Unidades Vendidas",
            coloraxis_showscale=False, height=400, title="Top 10 Categorías",
        )
        fig5.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
        st.plotly_chart(fig5, use_container_width=True)

    with col_b:
        top_8 = cat_df.head(8)[["category_name", "unidades"]].copy()
        others = pd.DataFrame({
            "category_name": ["OTRAS"],
            "unidades": [cat_df.iloc[8:]["unidades"].sum()],
        })
        pie_data = pd.concat([top_8, others], ignore_index=True)

        fig6 = px.pie(pie_data, names="category_name", values="unidades", hole=0.4)
        fig6.update_layout(height=400, title="Distribución por Categoría")
        st.plotly_chart(fig6, use_container_width=True)

    # Nota de cobertura
    pct = cat_data["porcentaje_sin_categoria"]
    if pct > 1:
        st.info(
            f"ℹ️ {cat_data['sin_categoria']:,} unidades ({pct}%) no tienen categoría "
            f"asignada. Estas se excluyen de los gráficos de categorías."
        )
