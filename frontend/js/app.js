/* ═══════════════════════════════════════════
   ShopLens Frontend — app.js
   ═══════════════════════════════════════════ */

const API = 'http://localhost:8000/api';

// ── State ──
let selectedStores = [];
let allStores = [];
let currentModule = 'resumen';
let tsAgg = 'dia';
let tsMetric = 'transacciones';
let boxType = 'categorias';
let corrData = null;

// ── Plotly dark theme ──
const plotlyLayout = {
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    font: { family: 'Inter, sans-serif', color: '#8b949e', size: 12 },
    margin: { l: 50, r: 20, t: 10, b: 50 },
    xaxis: { gridcolor: '#2a3244', zerolinecolor: '#2a3244' },
    yaxis: { gridcolor: '#2a3244', zerolinecolor: '#2a3244' },
    hoverlabel: { bgcolor: '#1c2333', bordercolor: '#3b82f6', font: { color: '#e6edf3', size: 12 } },
};

const plotlyConfig = { responsive: true, displayModeBar: false };

// ── API ──
async function api(endpoint, params = {}) {
    const url = new URL(`${API}/${endpoint}`);
    if (selectedStores.length > 0 && selectedStores.length < allStores.length) {
        params.stores = selectedStores.join(',');
    }
    Object.entries(params).forEach(([k, v]) => { if (v != null) url.searchParams.set(k, v); });
    const res = await fetch(url);
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
}

// ── Init ──
document.addEventListener('DOMContentLoaded', async () => {
    try {
        const health = await api('health');
        setApiStatus('ok', `Backend OK — ${health.transacciones.toLocaleString()} transacciones`);

        const storeData = await api('stores');
        allStores = storeData.stores;
        selectedStores = [...allStores];
        renderStoreFilters();
        loadModule('resumen');
    } catch (e) {
        setApiStatus('error', 'No se pudo conectar al backend');
        console.error(e);
    }
});

function setApiStatus(status, text) {
    const el = document.getElementById('apiStatus');
    el.className = `api-status ${status}`;
    el.querySelector('span:last-child').textContent = text;
}

// ── Store Filters ──
function renderStoreFilters() {
    const container = document.getElementById('storeFilters');
    container.innerHTML = allStores.map(s => `
        <label class="store-filter active" onclick="toggleStore(${s}, this)">
            <span class="store-check"></span>
            Tienda ${s}
        </label>
    `).join('');
    updateStoreBadge();
}

function toggleStore(storeId, el) {
    const idx = selectedStores.indexOf(storeId);
    if (idx >= 0) {
        if (selectedStores.length === 1) return; // al menos una
        selectedStores.splice(idx, 1);
        el.classList.remove('active');
    } else {
        selectedStores.push(storeId);
        el.classList.add('active');
    }
    updateStoreBadge();
    loadModule(currentModule);
}

function updateStoreBadge() {
    const badge = document.getElementById('badgeStores');
    badge.textContent = selectedStores.length === allStores.length
        ? 'Todas las tiendas'
        : `Tienda${selectedStores.length > 1 ? 's' : ''} ${selectedStores.sort().join(', ')}`;
}

// ── Module Navigation ──
function switchModule(name, el) {
    if (name === 'avanzado') return;
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    el.classList.add('active');
    document.querySelectorAll('.module').forEach(m => m.classList.add('hidden'));
    document.getElementById(`module-${name}`).classList.remove('hidden');

    const labels = { resumen: ['MÓDULO 01', 'Resumen Ejecutivo'], visualizaciones: ['MÓDULO 02', 'Visualizaciones Analíticas'] };
    document.getElementById('moduleLabel').textContent = labels[name][0];
    document.getElementById('moduleTitle').textContent = labels[name][1];
    currentModule = name;
    loadModule(name);
}

async function loadModule(name) {
    if (name === 'resumen') await loadResumen();
    else if (name === 'visualizaciones') await loadVisualizaciones();
}

// ═══════════════════════════════════════════
// MODULE 1: RESUMEN EJECUTIVO
// ═══════════════════════════════════════════

async function loadResumen() {
    try {
        const [kpis, topProd, topCli, diasPico, heatmap, cats] = await Promise.all([
            api('resumen/kpis'),
            api('resumen/top-productos', { limit: 10 }),
            api('resumen/top-clientes', { limit: 10 }),
            api('resumen/dias-pico'),
            api('resumen/dias-pico-heatmap'),
            api('resumen/categorias'),
        ]);

        renderKPIs(kpis);
        renderTopProductos(topProd.data);
        renderTopClientes(topCli.data);
        renderDiasPicoSerie(diasPico.data);
        renderDiasPicoHeatmap(heatmap);
        renderCategorias(cats);
    } catch (e) {
        console.error('Error loading resumen:', e);
    }
}

function renderKPIs(kpis) {
    const items = [
        { label: 'Total Unidades Vendidas', value: kpis.total_unidades.toLocaleString() },
        { label: 'Transacciones', value: kpis.total_transacciones.toLocaleString() },
        { label: 'Clientes Únicos', value: kpis.clientes_unicos.toLocaleString() },
        { label: 'Productos Distintos', value: kpis.productos_distintos.toLocaleString() },
        { label: 'Tiendas', value: kpis.tiendas },
        { label: 'Prom. Productos / Transacción', value: kpis.promedio_productos_por_transaccion },
    ];
    document.getElementById('kpiGrid').innerHTML = items.map(k => `
        <div class="kpi-card">
            <div class="kpi-label">${k.label}</div>
            <div class="kpi-value">${k.value}</div>
        </div>
    `).join('');
}

function renderTopProductos(data) {
    const labels = data.map(d => `Prod. ${d.product_id} (${d.category_name})`).reverse();
    const values = data.map(d => d.unidades).reverse();

    Plotly.newPlot('chartTopProductos', [{
        type: 'bar', orientation: 'h', x: values, y: labels,
        marker: { color: values.map((_, i) => `rgba(59, 130, 246, ${0.4 + (i / values.length) * 0.6})`) },
        text: values.map(v => v.toLocaleString()), textposition: 'outside',
        textfont: { color: '#8b949e', size: 11 },
        hovertemplate: '%{y}<br>Unidades: %{x:,.0f}<extra></extra>',
    }], {
        ...plotlyLayout,
        margin: { ...plotlyLayout.margin, l: 220 },
        xaxis: { ...plotlyLayout.xaxis, title: { text: 'Unidades Vendidas', font: { size: 11 } } },
        height: 400,
    }, plotlyConfig);
}

function renderTopClientes(data) {
    const labels = data.map(d => `Cliente ${d.customer_id}`).reverse();
    const values = data.map(d => d.transacciones).reverse();

    Plotly.newPlot('chartTopClientes', [{
        type: 'bar', orientation: 'h', x: values, y: labels,
        marker: { color: values.map((_, i) => `rgba(34, 197, 94, ${0.4 + (i / values.length) * 0.6})`) },
        text: values.map(v => v.toLocaleString()), textposition: 'outside',
        textfont: { color: '#8b949e', size: 11 },
        hovertemplate: '%{y}<br>Transacciones: %{x:,.0f}<extra></extra>',
    }], {
        ...plotlyLayout,
        margin: { ...plotlyLayout.margin, l: 120 },
        xaxis: { ...plotlyLayout.xaxis, title: { text: 'Número de Transacciones', font: { size: 11 } } },
        height: 400,
    }, plotlyConfig);
}

function renderDiasPicoSerie(data) {
    Plotly.newPlot('chartDiasPicoSerie', [{
        type: 'scatter', mode: 'lines',
        x: data.map(d => d.fecha), y: data.map(d => d.transacciones),
        line: { color: '#3b82f6', width: 1.5 },
        hovertemplate: '%{x}<br>Transacciones: %{y:,.0f}<extra></extra>',
    }], {
        ...plotlyLayout, height: 350,
        xaxis: { ...plotlyLayout.xaxis, title: { text: 'Fecha', font: { size: 11 } } },
        yaxis: { ...plotlyLayout.yaxis, title: { text: 'Transacciones', font: { size: 11 } } },
    }, plotlyConfig);
}

function renderDiasPicoHeatmap(heatmapData) {
    const dayOrder = heatmapData.day_order;
    const data = heatmapData.data;
    const weeks = [...new Set(data.map(d => d.week))].sort((a, b) => a - b);

    const z = dayOrder.map(day =>
        weeks.map(week => {
            const item = data.find(d => d.dia === day && d.week === week);
            return item ? item.transacciones : 0;
        })
    );

    Plotly.newPlot('chartDiasPicoHeatmap', [{
        type: 'heatmap', z, x: weeks, y: dayOrder,
        colorscale: [[0, '#1c2333'], [0.5, '#f59e0b'], [1, '#ef4444']],
        hovertemplate: 'Semana %{x}<br>%{y}<br>Transacciones: %{z:,.0f}<extra></extra>',
    }], {
        ...plotlyLayout, height: 320,
        xaxis: { ...plotlyLayout.xaxis, title: { text: 'Semana del Año', font: { size: 11 } } },
        yaxis: { ...plotlyLayout.yaxis, autorange: 'reversed' },
    }, plotlyConfig);
}

function switchDiasPico(type, btn) {
    document.querySelectorAll('#diasPicoTabs .tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('chartDiasPicoSerie').classList.toggle('hidden', type !== 'serie');
    document.getElementById('chartDiasPicoHeatmap').classList.toggle('hidden', type !== 'heatmap');
}

function renderCategorias(catData) {
    const data = catData.data;
    const top10 = data.slice(0, 10);

    // Bar chart
    Plotly.newPlot('chartCategoriasBar', [{
        type: 'bar', orientation: 'h',
        x: top10.map(d => d.unidades).reverse(),
        y: top10.map(d => d.category_name).reverse(),
        marker: { color: top10.map((_, i) => `rgba(249, 115, 22, ${0.4 + ((9 - i) / 10) * 0.6})`).reverse() },
        text: top10.map(d => d.unidades.toLocaleString()).reverse(), textposition: 'outside',
        textfont: { color: '#8b949e', size: 10 },
        hovertemplate: '%{y}<br>Unidades: %{x:,.0f}<extra></extra>',
    }], {
        ...plotlyLayout,
        margin: { ...plotlyLayout.margin, l: 180 },
        title: { text: 'Top 10 Categorías', font: { size: 13, color: '#8b949e' }, x: 0 },
        height: 380,
    }, plotlyConfig);

    // Pie chart
    const top8 = data.slice(0, 8);
    const othersSum = data.slice(8).reduce((s, d) => s + d.unidades, 0);
    const pieLabels = [...top8.map(d => d.category_name), 'OTRAS'];
    const pieValues = [...top8.map(d => d.unidades), othersSum];
    const colors = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#a855f7', '#06b6d4', '#ec4899', '#84cc16', '#6b7280'];

    Plotly.newPlot('chartCategoriasPie', [{
        type: 'pie', labels: pieLabels, values: pieValues, hole: 0.45,
        marker: { colors },
        textinfo: 'percent', textfont: { size: 10, color: '#e6edf3' },
        hovertemplate: '%{label}<br>Unidades: %{value:,.0f}<br>%{percent}<extra></extra>',
    }], {
        ...plotlyLayout,
        title: { text: 'Distribución por Categoría', font: { size: 13, color: '#8b949e' }, x: 0 },
        height: 380, showlegend: true,
        legend: { font: { size: 10, color: '#8b949e' }, bgcolor: 'transparent' },
    }, plotlyConfig);

    // Info banner
    const banner = document.getElementById('catInfoBanner');
    if (catData.porcentaje_sin_categoria > 1) {
        banner.textContent = `ℹ️ ${catData.sin_categoria.toLocaleString()} unidades (${catData.porcentaje_sin_categoria}%) no tienen categoría asignada. Se excluyen de estos gráficos.`;
        banner.classList.add('visible');
    } else {
        banner.classList.remove('visible');
    }
}

// ═══════════════════════════════════════════
// MODULE 2: VISUALIZACIONES ANALÍTICAS
// ═══════════════════════════════════════════

async function loadVisualizaciones() {
    try {
        await Promise.all([
            loadSerieTime(),
            loadBoxplot(),
            loadCorrelacion(),
        ]);
    } catch (e) {
        console.error('Error loading visualizaciones:', e);
    }
}

// ── Serie de Tiempo ──
function setTsAgg(val, btn) {
    tsAgg = val;
    btn.parentElement.querySelectorAll('.btn-toggle').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    loadSerieTime();
}

function setTsMetric(val, btn) {
    tsMetric = val;
    btn.parentElement.querySelectorAll('.btn-toggle').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    loadSerieTime();
}

async function loadSerieTime() {
    const data = await api('viz/serie-tiempo', { agrupacion: tsAgg, metrica: tsMetric });
    const metricLabel = tsMetric === 'transacciones' ? 'Transacciones' : 'Unidades Vendidas';

    const traces = [{
        type: 'scatter', mode: 'lines',
        x: data.data.map(d => d.periodo), y: data.data.map(d => d.valor),
        name: metricLabel, line: { color: '#3b82f6', width: 1.5 },
        hovertemplate: '%{x}<br>' + metricLabel + ': %{y:,.0f}<extra></extra>',
    }];

    if (data.media_movil) {
        traces.push({
            type: 'scatter', mode: 'lines',
            x: data.media_movil.map(d => d.periodo), y: data.media_movil.map(d => d.media_movil),
            name: 'Media móvil 7 días', line: { color: '#f59e0b', width: 2, dash: 'dash' },
            hovertemplate: '%{x}<br>Media: %{y:,.1f}<extra></extra>',
        });
    }

    Plotly.newPlot('chartSerieTime', traces, {
        ...plotlyLayout, height: 440,
        xaxis: { ...plotlyLayout.xaxis, title: { text: 'Período', font: { size: 11 } } },
        yaxis: { ...plotlyLayout.yaxis, title: { text: metricLabel, font: { size: 11 } } },
        legend: { orientation: 'h', y: 1.08, font: { size: 11, color: '#8b949e' }, bgcolor: 'transparent' },
        hovermode: 'x unified',
    }, plotlyConfig);

    // Desglose por tienda
    if (selectedStores.length > 1) {
        const storeData = await api('viz/serie-tiempo-por-tienda', { metrica: tsMetric });
        const storeColors = { 102: '#3b82f6', 103: '#22c55e', 107: '#f59e0b', 110: '#a855f7' };
        const storeGroups = {};
        storeData.data.forEach(d => {
            if (!storeGroups[d.store_id]) storeGroups[d.store_id] = { x: [], y: [] };
            storeGroups[d.store_id].x.push(d.periodo);
            storeGroups[d.store_id].y.push(d.valor);
        });

        const storeTraces = Object.entries(storeGroups).map(([sid, vals]) => ({
            type: 'scatter', mode: 'lines',
            x: vals.x, y: vals.y,
            name: `Tienda ${sid}`, line: { color: storeColors[sid] || '#8b949e', width: 1.5 },
        }));

        Plotly.newPlot('chartSerieByStore', storeTraces, {
            ...plotlyLayout, height: 380,
            legend: { orientation: 'h', y: 1.08, font: { size: 11, color: '#8b949e' }, bgcolor: 'transparent' },
        }, plotlyConfig);
    }
}

// ── Boxplot ──
function setBoxType(val, btn) {
    boxType = val;
    btn.parentElement.querySelectorAll('.btn-toggle').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    loadBoxplot();
}

async function loadBoxplot() {
    if (boxType === 'categorias') {
        const data = await api('viz/boxplot-categorias', { limit: 12 });
        const traces = data.data.map(d => ({
            type: 'box', name: d.category_name,
            lowerfence: [d.min], q1: [d.q1], median: [d.median], q3: [d.q3], upperfence: [d.max],
            marker: { color: '#3b82f6' }, fillcolor: 'rgba(59,130,246,0.15)',
            line: { color: '#3b82f6' },
        }));

        Plotly.newPlot('chartBoxplot', traces, {
            ...plotlyLayout, height: 460, showlegend: false,
            xaxis: { ...plotlyLayout.xaxis, tickangle: -45 },
            yaxis: { ...plotlyLayout.yaxis, title: { text: 'Unidades por Transacción', font: { size: 11 } } },
        }, plotlyConfig);
    } else {
        const data = await api('viz/boxplot-clientes');
        const storeColors = { 102: '#3b82f6', 103: '#22c55e', 107: '#f59e0b', 110: '#a855f7' };
        const traces = data.data.map(d => ({
            type: 'box', name: `Tienda ${d.store_id}`,
            lowerfence: [d.min], q1: [d.q1], median: [d.median], q3: [d.q3], upperfence: [d.max],
            marker: { color: storeColors[d.store_id] }, fillcolor: `${storeColors[d.store_id]}25`,
            line: { color: storeColors[d.store_id] },
        }));

        Plotly.newPlot('chartBoxplot', traces, {
            ...plotlyLayout, height: 460, showlegend: false,
            yaxis: { ...plotlyLayout.yaxis, title: { text: 'Transacciones por Cliente', font: { size: 11 } } },
        }, plotlyConfig);
    }
}

// ── Correlación ──
async function loadCorrelacion() {
    corrData = await api('viz/correlacion');
    const m = corrData.matrix;

    Plotly.newPlot('chartCorrelacion', [{
        type: 'heatmap', z: m.values, x: m.labels, y: m.labels,
        colorscale: [[0, '#ef4444'], [0.5, '#1c2333'], [1, '#3b82f6']],
        zmin: -1, zmax: 1,
        text: m.values.map(row => row.map(v => (v != null ? v.toFixed(2) : '—'))),
        texttemplate: '%{text}', textfont: { size: 11, color: '#e6edf3' },
        hovertemplate: '%{x}<br>%{y}<br>Correlación: %{z:.3f}<extra></extra>',
    }], {
        ...plotlyLayout, height: 480,
        xaxis: { ...plotlyLayout.xaxis, tickangle: -30, side: 'bottom' },
        yaxis: { ...plotlyLayout.yaxis, autorange: 'reversed' },
    }, plotlyConfig);

    // Interpretation
    const pairs = [];
    for (let i = 0; i < m.labels.length; i++) {
        for (let j = i + 1; j < m.labels.length; j++) {
            pairs.push({ a: m.labels[i], b: m.labels[j], v: m.values[i][j] });
        }
    }
    pairs.sort((a, b) => b.v - a.v);

    const top3 = pairs.slice(0, 3).map(p => `<strong>${p.a}</strong> ↔ <strong>${p.b}</strong>: ${p.v.toFixed(2)}`);
    const bot3 = pairs.slice(-3).map(p => `<strong>${p.a}</strong> ↔ <strong>${p.b}</strong>: ${p.v.toFixed(2)}`);

    document.getElementById('corrInterpretation').innerHTML = `
        <p><strong>Correlaciones más fuertes (positivas):</strong></p>
        ${top3.map(t => `<p style="margin-left:12px">• ${t}</p>`).join('')}
        <br>
        <p><strong>Correlaciones más débiles o negativas:</strong></p>
        ${bot3.map(t => `<p style="margin-left:12px">• ${t}</p>`).join('')}
        <br>
        <p>Correlación cercana a 1 = crecen juntas. Cercana a 0 = independientes. Cercana a -1 = relación inversa.</p>
    `;

    // Scatter selects
    const selX = document.getElementById('scatterX');
    const selY = document.getElementById('scatterY');
    selX.innerHTML = corrData.scatter_columns.map((c, i) =>
        `<option value="${c}" ${i === 0 ? 'selected' : ''}>${corrData.scatter_labels[c]}</option>`
    ).join('');
    selY.innerHTML = corrData.scatter_columns.map((c, i) =>
        `<option value="${c}" ${i === 1 ? 'selected' : ''}>${corrData.scatter_labels[c]}</option>`
    ).join('');
    renderScatter();
}

function renderScatter() {
    if (!corrData) return;
    const xCol = document.getElementById('scatterX').value;
    const yCol = document.getElementById('scatterY').value;
    const labels = corrData.scatter_labels;
    const sample = corrData.scatter_sample;

    Plotly.newPlot('chartScatter', [{
        type: 'scatter', mode: 'markers',
        x: sample.map(d => d[xCol]), y: sample.map(d => d[yCol]),
        marker: { color: '#3b82f6', opacity: 0.3, size: 5 },
        hovertemplate: `${labels[xCol]}: %{x}<br>${labels[yCol]}: %{y}<extra></extra>`,
    }], {
        ...plotlyLayout, height: 440,
        xaxis: { ...plotlyLayout.xaxis, title: { text: labels[xCol], font: { size: 11 } } },
        yaxis: { ...plotlyLayout.yaxis, title: { text: labels[yCol], font: { size: 11 } } },
    }, plotlyConfig);

    document.getElementById('scatterCaption').textContent =
        `Muestra de ${sample.length.toLocaleString()} clientes de ${corrData.total_clientes.toLocaleString()} totales.`;
}
