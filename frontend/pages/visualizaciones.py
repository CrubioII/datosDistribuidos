"""
Módulo 2: Visualizaciones Analíticas
Consume datos del backend vía api_client.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import api_client as api


def render(selected_stores: list[int]):
    st.header("📈 Visualizaciones Analíticas")

    # ═══════════════════════════════════════
    # 1. SERIE DE TIEMPO
    # ═══════════════════════════════════════
    st.subheader("1. Serie de Tiempo — Ventas por Período")

    agg_map = {"Día": "dia", "Semana": "semana", "Mes": "mes"}
    met_map = {"Transacciones": "transacciones", "Unidades Vendidas": "unidades"}

    agg_option = st.radio("Agrupar por:", list(agg_map.keys()), horizontal=True, key="ts_agg")
    metric_option = st.radio("Métrica:", list(met_map.keys()), horizontal=True, key="ts_metric")

    ts_data = api.get_serie_tiempo(
        selected_stores,
        agrupacion=agg_map[agg_option],
        metrica=met_map[metric_option],
    )

    ts_df = pd.DataFrame(ts_data["data"])
    ts_df["periodo"] = pd.to_datetime(ts_df["periodo"])

    fig_ts = go.Figure()
    fig_ts.add_trace(go.Scatter(
        x=ts_df["periodo"], y=ts_df["valor"],
        mode="lines", name=metric_option, line=dict(color="#636EFA"),
    ))

    if ts_data["media_movil"]:
        mm_df = pd.DataFrame(ts_data["media_movil"])
        mm_df["periodo"] = pd.to_datetime(mm_df["periodo"])
        fig_ts.add_trace(go.Scatter(
            x=mm_df["periodo"], y=mm_df["media_movil"],
            mode="lines", name="Media Móvil 7 días",
            line=dict(color="#EF553B", dash="dash", width=2),
        ))

    fig_ts.update_layout(
        xaxis_title="Período", yaxis_title=metric_option,
        height=450, hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig_ts, use_container_width=True)

    # Desglose por tienda
    if len(selected_stores) > 1:
        with st.expander("Ver desglose por tienda"):
            store_data = api.get_serie_tiempo_por_tienda(
                selected_stores, metrica=met_map[metric_option]
            )
            store_df = pd.DataFrame(store_data)
            store_df["periodo"] = pd.to_datetime(store_df["periodo"])
            store_df["store_id"] = "Tienda " + store_df["store_id"].astype(str)

            fig_ts2 = px.line(
                store_df, x="periodo", y="valor", color="store_id",
                labels={"periodo": "Semana", "valor": metric_option, "store_id": "Tienda"},
            )
            fig_ts2.update_layout(height=400)
            st.plotly_chart(fig_ts2, use_container_width=True)

    st.divider()

    # ═══════════════════════════════════════
    # 2. BOXPLOT
    # ═══════════════════════════════════════
    st.subheader("2. Boxplot — Distribución de Comportamiento")

    box_type = st.radio(
        "Analizar distribución de:",
        ["Unidades por transacción (por categoría)", "Transacciones por cliente (por tienda)"],
        horizontal=True, key="box_type",
    )

    if box_type == "Unidades por transacción (por categoría)":
        box_stats = api.get_boxplot_categorias(selected_stores)
        
        if not box_stats:
            st.warning("No hay datos suficientes para generar el boxplot con la selección actual.")
            return

        fig_box = go.Figure()
        for stat in box_stats:
            fig_box.add_trace(go.Box(
                name=stat["category_name"],
                lowerfence=[stat["min"]],
                q1=[stat["q1"]],
                median=[stat["median"]],
                q3=[stat["q3"]],
                upperfence=[stat["max"]],
            ))

        fig_box.update_layout(
            showlegend=False, height=500,
            yaxis_title="Unidades por Transacción",
            xaxis_tickangle=-45,
        )
        st.plotly_chart(fig_box, use_container_width=True)
        st.caption(
            "Top categorías por volumen. Los bigotes indican el rango sin outliers (1.5×IQR)."
        )

    else:
        box_stats = api.get_boxplot_clientes(selected_stores)
        
        if not box_stats:
            st.warning("No hay datos suficientes para generar el boxplot de clientes.")
            return

        fig_box2 = go.Figure()
        for stat in box_stats:
            fig_box2.add_trace(go.Box(
                name=f"Tienda {stat['store_id']}",
                lowerfence=[stat["min"]],
                q1=[stat["q1"]],
                median=[stat["median"]],
                q3=[stat["q3"]],
                upperfence=[stat["max"]],
            ))

        fig_box2.update_layout(
            showlegend=False, height=500,
            yaxis_title="Transacciones por Cliente",
        )
        st.plotly_chart(fig_box2, use_container_width=True)
        st.caption(
            "Distribución de frecuencia de compra por cliente en cada tienda."
        )

    st.divider()

    # ═══════════════════════════════════════
    # 3. HEATMAP DE CORRELACIÓN
    # ═══════════════════════════════════════
    st.subheader("3. Heatmap — Correlación entre Variables de Comportamiento")

    st.caption(
        "Variables derivadas por cliente: frecuencia, volumen total, "
        "diversidad de productos/categorías, tiendas visitadas, promedio unidades/visita."
    )

    corr_data = api.get_correlacion(selected_stores)
    matrix = corr_data["matrix"]

    fig_heat = px.imshow(
        matrix["values"],
        x=matrix["labels"],
        y=matrix["labels"],
        text_auto=".2f",
        color_continuous_scale="RdBu_r",
        zmin=-1, zmax=1, aspect="equal",
    )
    fig_heat.update_layout(height=550)
    st.plotly_chart(fig_heat, use_container_width=True)

    # Interpretación
    with st.expander("Interpretación de la correlación"):
        vals = np.array(matrix["values"])
        labels = matrix["labels"]
        n = len(labels)

        pairs = []
        for i in range(n):
            for j in range(i + 1, n):
                pairs.append((labels[i], labels[j], vals[i][j]))

        pairs.sort(key=lambda x: x[2], reverse=True)

        st.write("**Correlaciones más fuertes (positivas):**")
        for v1, v2, val in pairs[:3]:
            st.write(f"- {v1} ↔ {v2}: **{val:.2f}**")

        st.write("**Correlaciones más débiles o negativas:**")
        for v1, v2, val in pairs[-3:]:
            st.write(f"- {v1} ↔ {v2}: **{val:.2f}**")

        st.write(
            "\nCorrelación cercana a 1 = crecen juntas. "
            "Cercana a 0 = independientes. Cercana a -1 = relación inversa."
        )

    # ── Scatter exploratorio ──
    st.subheader("Exploración: Scatter Plot entre Variables")

    scatter_cols = corr_data["scatter_columns"]
    scatter_labels = corr_data["scatter_labels"]

    col1, col2 = st.columns(2)
    with col1:
        x_var = st.selectbox(
            "Variable X:", scatter_cols,
            format_func=lambda x: scatter_labels[x], index=0, key="scatter_x",
        )
    with col2:
        y_var = st.selectbox(
            "Variable Y:", scatter_cols,
            format_func=lambda x: scatter_labels[x], index=1, key="scatter_y",
        )

    sample_df = pd.DataFrame(corr_data["scatter_sample"])

    fig_scatter = px.scatter(
        sample_df, x=x_var, y=y_var, opacity=0.3,
        labels={x_var: scatter_labels[x_var], y_var: scatter_labels[y_var]},
        trendline="ols",
    )
    fig_scatter.update_layout(height=450)
    st.plotly_chart(fig_scatter, use_container_width=True)

    st.caption(
        f"Muestra de {len(sample_df):,} clientes de {corr_data['total_clientes']:,} totales."
    )
