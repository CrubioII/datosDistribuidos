"""
Módulo 1: Resumen Ejecutivo — Defensivo contra datos vacíos/parciales.
"""

import streamlit as st
import plotly.express as px
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import api_client as api


def render(selected_stores: list[int]):
    st.header("📊 Resumen Ejecutivo")

    # ── KPIs ──
    kpis = api.get_kpis(selected_stores) or {}

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Unidades Vendidas", f"{kpis.get('total_unidades', 0):,.0f}")
    col2.metric("Total Transacciones", f"{kpis.get('total_transacciones', 0):,.0f}")
    col3.metric("Clientes Únicos", f"{kpis.get('clientes_unicos', 0):,.0f}")

    col4, col5, col6 = st.columns(3)
    col4.metric("Productos Distintos", f"{kpis.get('productos_distintos', 0):,.0f}")
    col5.metric("Tiendas", f"{kpis.get('tiendas', 0)}")
    col6.metric("Prom. Unid/Transacción", f"{kpis.get('promedio_productos_por_transaccion', 0)}")

    st.divider()

    # ── Top 10 Productos ──
    st.subheader("Top 10 Productos Más Comprados")
    top_prod_data = api.get_top_productos(selected_stores) or []
    if top_prod_data:
        top_prod = pd.DataFrame(top_prod_data)
        if "product_id" in top_prod.columns and "unidades" in top_prod.columns:
            top_prod["label"] = top_prod.apply(
                lambda r: f"Prod. {r['product_id']} ({r.get('category_name', 'N/A')})", axis=1
            )
            fig = px.bar(top_prod, y="label", x="unidades", orientation="h",
                         text="unidades", color="unidades", color_continuous_scale="Blues")
            fig.update_layout(yaxis=dict(autorange="reversed", title=""),
                              xaxis_title="Unidades Vendidas", coloraxis_showscale=False, height=400)
            fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Datos de productos con formato inesperado.")
    else:
        st.info("No hay datos de productos disponibles para la selección actual.")

    # ── Top 10 Clientes ──
    st.subheader("Top 10 Clientes con Más Compras")
    top_cli_data = api.get_top_clientes(selected_stores) or []
    if top_cli_data:
        top_cli = pd.DataFrame(top_cli_data)
        if "customer_id" in top_cli.columns and "transacciones" in top_cli.columns:
            top_cli["label"] = "Cliente " + top_cli["customer_id"].astype(str)
            fig2 = px.bar(top_cli, y="label", x="transacciones", orientation="h",
                          text="transacciones", color="transacciones", color_continuous_scale="Greens")
            fig2.update_layout(yaxis=dict(autorange="reversed", title=""),
                               xaxis_title="Número de Transacciones", coloraxis_showscale=False, height=400)
            fig2.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.warning("Datos de clientes con formato inesperado.")
    else:
        st.info("No hay datos de clientes disponibles.")

    # ── Días Pico ──
    st.subheader("Días Pico de Compra")
    tab1, tab2 = st.tabs(["Serie de Tiempo", "Heatmap Semanal"])

    with tab1:
        dias_data = api.get_dias_pico(selected_stores) or []
        if dias_data:
            daily = pd.DataFrame(dias_data)
            if "fecha" in daily.columns and "transacciones" in daily.columns:
                daily["fecha"] = pd.to_datetime(daily["fecha"])
                fig3 = px.line(daily.sort_values("fecha"), x="fecha", y="transacciones",
                               labels={"fecha": "Fecha", "transacciones": "Transacciones"})
                fig3.update_layout(height=350)
                st.plotly_chart(fig3, use_container_width=True)
            else:
                st.warning("Formato de días pico inesperado.")
        else:
            st.info("No hay datos de días pico.")

    with tab2:
        hm_data = api.get_dias_pico_heatmap(selected_stores) or {}
        hm_list = hm_data.get("data", []) if isinstance(hm_data, dict) else []
        day_order = hm_data.get("day_order", []) if isinstance(hm_data, dict) else []
        if hm_list:
            hm_df = pd.DataFrame(hm_list)
            if {"dia", "week", "transacciones"}.issubset(hm_df.columns):
                pivot = hm_df.pivot(index="dia", columns="week", values="transacciones")
                if day_order:
                    pivot = pivot.reindex([d for d in day_order if d in pivot.index])
                fig4 = px.imshow(pivot, labels=dict(x="Semana del Año", y="Día", color="Transacciones"),
                                 color_continuous_scale="YlOrRd", aspect="auto")
                fig4.update_layout(height=350)
                st.plotly_chart(fig4, use_container_width=True)
            else:
                st.warning("Formato de heatmap inesperado.")
        else:
            st.info("No hay datos para el heatmap semanal.")

    # ── Categorías ──
    st.subheader("Categorías con Mayor Volumen")
    cat_data = api.get_categorias(selected_stores) or {}
    cat_list = cat_data.get("data", []) if isinstance(cat_data, dict) else []

    if cat_list:
        cat_df = pd.DataFrame(cat_list)
        if "category_name" in cat_df.columns and "unidades" in cat_df.columns:
            col_metric = "unidades"
            label_metric = "Unidades Vendidas"

            # Si hay transacciones, ofrecer toggle
            if "transacciones" in cat_df.columns and cat_df["transacciones"].sum() > 0:
                metric_cat = st.radio("Analizar por:", ["Volumen (Unidades)", "Frecuencia (Transacciones)"],
                                      horizontal=True, key="cat_metric")
                if "Frecuencia" in metric_cat:
                    col_metric = "transacciones"
                    label_metric = "Transacciones"

            col_a, col_b = st.columns(2)
            with col_a:
                top_cat = cat_df.sort_values(col_metric, ascending=False).head(10)
                fig5 = px.bar(top_cat, y="category_name", x=col_metric, orientation="h",
                              text=col_metric, color=col_metric, color_continuous_scale="Oranges")
                fig5.update_layout(yaxis=dict(autorange="reversed", title=""), xaxis_title=label_metric,
                                   coloraxis_showscale=False, height=400, title="Top 10 Categorías")
                fig5.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
                st.plotly_chart(fig5, use_container_width=True)

            with col_b:
                pie_df = cat_df.sort_values(col_metric, ascending=False)
                top_8 = pie_df.head(8)[["category_name", col_metric]].copy()
                rest = pie_df.iloc[8:][col_metric].sum() if len(pie_df) > 8 else 0
                if rest > 0:
                    others = pd.DataFrame({"category_name": ["OTRAS"], col_metric: [rest]})
                    pie_data = pd.concat([top_8, others], ignore_index=True)
                else:
                    pie_data = top_8
                fig6 = px.pie(pie_data, names="category_name", values=col_metric, hole=0.4)
                fig6.update_layout(height=400, title="Distribución por Categoría")
                st.plotly_chart(fig6, use_container_width=True)
        else:
            st.warning("Formato de categorías inesperado.")
    else:
        st.info("No hay datos de categorías disponibles.")

    # Nota de cobertura — usar .get() defensivo
    pct = cat_data.get("porcentaje_sin_categoria", 0) if isinstance(cat_data, dict) else 0
    if pct and pct > 1:
        sin_cat = cat_data.get("sin_categoria", 0)
        st.info(f"ℹ️ {sin_cat:,} unidades ({pct}%) no tienen categoría asignada. Se excluyen de estos gráficos.")
