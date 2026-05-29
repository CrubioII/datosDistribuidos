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
    col1.metric("Total Unidades Vendidas (Volumen)", f"{kpis['total_unidades']:,.0f}")
    col2.metric("Total Transacciones (Frecuencia)", f"{kpis['total_transacciones']:,.0f}")
    
    if kpis['clientes_unicos'] > 0:
        col3.metric("Clientes Únicos", f"{kpis['clientes_unicos']:,.0f}")
    else:
        col3.metric("Tiendas", f"{kpis['tiendas']}")

    col4, col5, col6 = st.columns(3)
    if kpis['productos_distintos'] > 0:
        col4.metric("Productos Distintos", f"{kpis['productos_distintos']:,.0f}")
    else:
        col4.write("") # Espacio vacío si no hay dato
        
    if kpis['clientes_unicos'] > 0:
        col5.metric("Tiendas", f"{kpis['tiendas']}")
    
    col6.metric("Promedio Unid/Transacción", f"{kpis['promedio_productos_por_transaccion']}")

    if not selected_stores and kpis['clientes_unicos'] == 0:
        st.caption("ℹ️ Nota: Métricas de clientes y productos únicos solo disponibles en filtros por tienda.")

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
    st.subheader("Categorías con Mayor Desempeño")
    cat_data = api.get_categorias(selected_stores)
    cat_df = pd.DataFrame(cat_data["data"])

    if not cat_df.empty:
        # Toggle de métrica si está disponible la frecuencia
        has_freq = cat_df["transacciones"].sum() > 0
        if has_freq:
            metric_cat = st.radio("Analizar por:", ["Volumen (Unidades)", "Frecuencia (Transacciones)"], 
                                  horizontal=True, key="cat_metric")
            col_metric = "unidades" if "Volumen" in metric_cat else "transacciones"
            label_metric = "Unidades Vendidas" if col_metric == "unidades" else "Número de Transacciones"
        else:
            col_metric = "unidades"
            label_metric = "Unidades Vendidas"

        col_a, col_b = st.columns(2)

        with col_a:
            top_cat = cat_df.sort_values(col_metric, ascending=False).head(10)
            fig5 = px.bar(
                top_cat, y="category_name", x=col_metric, orientation="h",
                text=col_metric, color=col_metric, color_continuous_scale="Oranges",
            )
            fig5.update_layout(
                yaxis=dict(autorange="reversed", title=""),
                xaxis_title=label_metric,
                coloraxis_showscale=False, height=400, title=f"Top 10 Categorías ({label_metric})",
            )
            fig5.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
            st.plotly_chart(fig5, use_container_width=True)

        with col_b:
            pie_df = cat_df.sort_values(col_metric, ascending=False)
            top_8 = pie_df.head(8)[["category_name", col_metric]].copy()
            others = pd.DataFrame({
                "category_name": ["OTRAS"],
                col_metric: [pie_df.iloc[8:][col_metric].sum()],
            })
            pie_data = pd.concat([top_8, others], ignore_index=True)

            fig6 = px.pie(pie_data, names="category_name", values=col_metric, hole=0.4)
            fig6.update_layout(height=400, title=f"Distribución por {label_metric}")
            st.plotly_chart(fig6, use_container_width=True)
    else:
        st.warning("No hay datos de categorías disponibles.")

    # Nota de cobertura
    pct = cat_data["porcentaje_sin_categoria"]
    if pct > 1:
        st.info(
            f"ℹ️ {cat_data['sin_categoria']:,} unidades ({pct}%) no tienen categoría "
            f"asignada. Estas se excluyen de los gráficos de categorías."
        )
