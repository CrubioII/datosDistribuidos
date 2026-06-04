"""
Módulo 3: Análisis Avanzado
- A. Segmentación de Clientes (K-Means)
- B. Recomendador de Productos (reglas de asociación)
- C. Incorporación de Nuevos Datos
"""

import streamlit as st
import plotly.express as px
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import api_client as api


def render(selected_stores: list[int]):
    st.header("🧠 Análisis Avanzado")

    tab_seg, tab_rec, tab_new = st.tabs([
        "🎯 Segmentación de Clientes (K-Means)",
        "🛍️ Recomendador de Productos",
        "📥 Incorporación de Nuevos Datos",
    ])

    # ═════════════════════════════════════════════════════════
    # A. SEGMENTACIÓN DE CLIENTES — K-MEANS
    # ═════════════════════════════════════════════════════════
    with tab_seg:
        st.subheader("Segmentación con K-Means")
        st.caption(
            "Agrupa clientes según su comportamiento: frecuencia, volumen total, "
            "diversidad de productos/categorías, tiendas visitadas y unidades por visita. "
            "Las variables se estandarizan antes del clustering y se proyectan a 2D con PCA para la visualización."
        )

        col_k, col_n = st.columns(2)
        with col_k:
            k = st.slider("Número de clusters (k):", min_value=2, max_value=8, value=4, step=1)
        with col_n:
            sample_size = st.slider("Muestra para scatter:", min_value=1000, max_value=15000, value=5000, step=500)

        with st.spinner("Ejecutando K-Means..."):
            seg = api.get_segmentacion(selected_stores, k=k, sample_size=sample_size) or {}

        clusters = seg.get("clusters", [])
        scatter = seg.get("scatter", [])
        feature_labels = seg.get("feature_labels", {})
        feature_cols = seg.get("feature_cols", [])
        var_exp = seg.get("varianza_explicada", [])

        if not clusters or not scatter:
            st.warning("No hay datos suficientes para segmentar.")
        else:
            colA, colB, colC = st.columns(3)
            colA.metric("Total clientes analizados", f"{seg.get('total_clientes', 0):,}")
            colB.metric("Clusters generados", k)
            if var_exp and len(var_exp) >= 2:
                colC.metric("Varianza explicada (PC1+PC2)",
                            f"{var_exp[0] + var_exp[1]:.1f}%")

            # Scatter PCA
            scatter_df = pd.DataFrame(scatter)
            cluster_name_map = {c["cluster"]: c.get("nombre", f"Grupo {c['cluster']}") for c in clusters}
            scatter_df["Grupo"] = scatter_df["cluster"].map(cluster_name_map)

            fig = px.scatter(
                scatter_df, x="pc1", y="pc2", color="Grupo",
                opacity=0.5, hover_data=["customer_id"],
                labels={"pc1": f"PC1 ({var_exp[0]:.1f}%)" if var_exp else "PC1",
                        "pc2": f"PC2 ({var_exp[1]:.1f}%)" if len(var_exp) > 1 else "PC2"},
                title=f"Proyección PCA de {len(scatter_df):,} clientes en {k} grupos",
            )
            fig.update_traces(marker=dict(size=6, line=dict(width=0)))
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)

            # Tabla de perfil de cada cluster
            st.subheader("Perfil de cada grupo")
            profile_rows = []
            for c in clusters:
                row = {
                    "Grupo": c.get("nombre", f"Grupo {c['cluster']}"),
                    "Clientes": c["n_clientes"],
                    "% del total": f"{c['porcentaje']}%",
                }
                for col in feature_cols:
                    row[feature_labels.get(col, col)] = c["metricas"].get(col, 0)
                profile_rows.append(row)
            profile_df = pd.DataFrame(profile_rows)
            st.dataframe(profile_df, use_container_width=True, hide_index=True)

            # Comparación gráfica de promedios
            st.subheader("Comparación de promedios por grupo")
            comp_rows = []
            for c in clusters:
                for col in feature_cols:
                    comp_rows.append({
                        "Grupo": c.get("nombre", f"Grupo {c['cluster']}"),
                        "Variable": feature_labels.get(col, col),
                        "Valor": c["metricas"].get(col, 0),
                    })
            comp_df = pd.DataFrame(comp_rows)
            fig_bar = px.bar(comp_df, x="Variable", y="Valor", color="Grupo",
                             barmode="group", height=420)
            st.plotly_chart(fig_bar, use_container_width=True)

            # Interpretación automática
            with st.expander("Interpretación de los grupos"):
                for c in clusters:
                    nombre_grupo = c.get('nombre') or f"Grupo {c['cluster']}"
                    st.markdown(
                        f"**{nombre_grupo}** — {c['n_clientes']:,} clientes ({c['porcentaje']}% del total)"
                    )
                    metricas = c["metricas"]
                    bullets = []
                    if "frecuencia" in metricas:
                        bullets.append(f"frecuencia promedio: **{metricas['frecuencia']:.1f}** visitas")
                    if "volumen_total" in metricas:
                        bullets.append(f"volumen promedio: **{metricas['volumen_total']:.1f}** unidades")
                    if "categorias_distintas" in metricas:
                        bullets.append(f"categorías distintas: **{metricas['categorias_distintas']:.1f}**")
                    if "tiendas_visitadas" in metricas:
                        bullets.append(f"tiendas visitadas: **{metricas['tiendas_visitadas']:.1f}**")
                    if bullets:
                        st.write("• " + " · ".join(bullets))
                    st.write("")

            # Buscar cliente
            st.subheader("Buscar cluster de un cliente específico")
            customer_search = st.number_input("ID de cliente:", min_value=1, value=336296, step=1)
            if st.button("Buscar"):
                result = api.get_segmentacion_cliente(int(customer_search), selected_stores, k=k) or {}
                if result.get("encontrado"):
                    info = result.get("info", {}) or {}
                    nombre_grupo = info.get('nombre') or f"Grupo {result.get('cluster')}"
                    st.success(
                        f"Cliente **{customer_search}** pertenece al grupo "
                        f"**{nombre_grupo}** "
                        f"({info.get('n_clientes', 0):,} clientes)"
                    )
                else:
                    st.warning(f"Cliente {customer_search} no está en la muestra del scatter (puede existir en el dataset completo).")

    # ═════════════════════════════════════════════════════════
    # B. RECOMENDADOR DE PRODUCTOS
    # ═════════════════════════════════════════════════════════
    with tab_rec:
        st.subheader("Recomendador basado en reglas de asociación")
        st.caption(
            "Las recomendaciones se calculan a partir de la co-ocurrencia de productos "
            "en las mismas transacciones (similar a 'frecuentemente comprado junto'). "
            "Se reportan métricas de confianza y lift."
        )

        modo = st.radio("Modo de recomendación:",
                        ["Dado un producto", "Dado un cliente"],
                        horizontal=True, key="reco_modo")

        if modo == "Dado un producto":
            with st.spinner("Cargando lista de productos populares..."):
                productos = api.productos_populares(selected_stores, limit=80) or []

            if not productos:
                st.warning("No hay productos disponibles para la selección actual.")
            else:
                opciones = {f"Prod. {p['product_id']} — {p.get('category_name', 'N/A')} "
                            f"({p['transacciones']:,} tx)": p['product_id'] for p in productos}
                seleccion = st.selectbox("Selecciona un producto:", list(opciones.keys()))
                top_n = st.slider("Top productos a recomendar:", 5, 25, 10)

                if st.button("Generar recomendaciones", key="rec_prod_btn"):
                    pid = opciones[seleccion]
                    with st.spinner("Calculando recomendaciones..."):
                        resp = api.recomendar_producto(int(pid), selected_stores, top=top_n) or {}
                    recos = resp.get("recomendaciones", [])
                    if not recos:
                        st.info("No se encontraron recomendaciones.")
                    else:
                        st.success(
                            f"Producto **{resp.get('product_id')}** "
                            f"({resp.get('category_name', 'N/A')}) — "
                            f"presente en **{resp.get('base_transacciones', 0):,}** transacciones."
                        )
                        recos_df = pd.DataFrame(recos)
                        recos_df.columns = ["Producto", "Categoría", "Co-ocurrencias", "Confianza", "Lift"]
                        st.dataframe(recos_df, use_container_width=True, hide_index=True)

                        # Gráfico de lift
                        fig_rec = px.bar(
                            recos_df.head(15),
                            x="Lift", y="Producto", orientation="h",
                            color="Confianza", color_continuous_scale="Viridis",
                            title="Top recomendaciones por Lift",
                        )
                        fig_rec.update_layout(yaxis=dict(autorange="reversed"), height=450)
                        st.plotly_chart(fig_rec, use_container_width=True)

        else:  # Dado un cliente
            with st.spinner("Cargando lista de clientes frecuentes..."):
                clientes = api.clientes_frecuentes(selected_stores, limit=80) or []

            if not clientes:
                st.warning("No hay clientes disponibles para la selección actual.")
            else:
                cli_opts = {f"Cliente {c['customer_id']} ({c['transacciones']:,} tx)": c['customer_id']
                            for c in clientes}
                cli_sel = st.selectbox("Selecciona un cliente frecuente o ingresa otro:",
                                       ["(Ingresar ID manualmente)"] + list(cli_opts.keys()),
                                       key="reco_cli_select")
                if cli_sel == "(Ingresar ID manualmente)":
                    cid = st.number_input("ID de cliente:", min_value=1, value=336296, step=1)
                else:
                    cid = cli_opts[cli_sel]
                top_n = st.slider("Top productos a recomendar:", 5, 25, 10, key="rec_cli_top")

                if st.button("Generar recomendaciones", key="rec_cli_btn"):
                    with st.spinner("Calculando recomendaciones..."):
                        resp = api.recomendar_cliente(int(cid), selected_stores, top=top_n) or {}
                    recos = resp.get("recomendaciones", [])
                    if not recos:
                        st.info(resp.get("razon", "No se encontraron recomendaciones."))
                    else:
                        st.success(
                            f"Cliente **{resp.get('customer_id')}** — "
                            f"ha comprado **{resp.get('productos_comprados', 0)}** productos distintos."
                        )
                        recos_df = pd.DataFrame(recos)
                        recos_df.columns = ["Producto", "Categoría", "Score"]
                        st.dataframe(recos_df, use_container_width=True, hide_index=True)

                        fig_rec2 = px.bar(
                            recos_df.head(15),
                            x="Score", y="Producto", orientation="h",
                            color="Score", color_continuous_scale="Plasma",
                            title="Top recomendaciones para el cliente",
                        )
                        fig_rec2.update_layout(yaxis=dict(autorange="reversed"), height=450)
                        st.plotly_chart(fig_rec2, use_container_width=True)

    # ═════════════════════════════════════════════════════════
    # C. INCORPORACIÓN DE NUEVOS DATOS
    # ═════════════════════════════════════════════════════════
    with tab_new:
        st.subheader("Incorporar Nuevos Datos")
        st.caption(
            "Sube un archivo `*_Tran.csv` con el mismo formato del dataset original "
            "(separador `|`, columnas: fecha | store_id | customer_id | productos). "
            "El backend lo guardará y regenerará todos los análisis automáticamente."
        )

        st.markdown(
            """
            **Formato esperado** (sin encabezado):
            ```
            2013-07-01|102|530|20 3 1
            2013-07-01|102|587|6 29 43 21
            ```
            """
        )

        uploaded = st.file_uploader(
            "Selecciona un archivo CSV de transacciones:",
            type=["csv"],
            help="El archivo debe terminar en _Tran.csv (ej: 115_Tran.csv)",
        )

        col_up, col_re = st.columns(2)
        with col_up:
            if uploaded is not None:
                if st.button("📤 Cargar archivo y regenerar análisis", type="primary"):
                    with st.spinner("Cargando archivo y recalculando todo..."):
                        result = api.cargar_nuevos_datos(uploaded.name, uploaded.getvalue()) or {}
                    if result.get("ok"):
                        st.success("Archivo cargado e incorporado correctamente.")
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Transacciones previas", f"{result.get('transacciones_previas', 0):,}")
                        c2.metric("Transacciones actuales", f"{result.get('transacciones_actuales', 0):,}")
                        c3.metric("Incorporadas", f"{result.get('incorporadas', 0):,}")
                        st.info("Los análisis (segmentación, recomendador y resumen) usan ya los nuevos datos. "
                                "Recarga la página para ver los cambios.")
                    else:
                        st.error("La carga falló.")

        with col_re:
            if st.button("🔄 Recargar dataset desde disco"):
                with st.spinner("Recargando..."):
                    result = api.recargar_dataset() or {}
                if result.get("ok"):
                    st.success(
                        f"Dataset recargado. "
                        f"Transacciones: {result.get('transacciones_actuales', 0):,}"
                    )

        # Estado actual
        st.divider()
        st.subheader("Estado del Dataset")
        h = api.health() or {}
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Transacciones cargadas", f"{h.get('transacciones', 0):,}")
        c2.metric("Filas explotadas", f"{h.get('exploded_rows', 0):,}")
        c3.metric("Categorías", f"{h.get('categorias', 0)}")
        c4.metric("Nube activa", "Sí" if h.get("cloud") else "No")
