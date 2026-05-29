async function fetchData(endpoint) {
    try {
        const response = await fetch(endpoint);
        return await response.json();
    } catch (error) {
        console.error(`Error fetching ${endpoint}:`, error);
        return null;
    }
}

function renderBarChart(ctxId, labels, data, label, color) {
    const ctx = document.getElementById(ctxId).getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: label,
                data: data,
                backgroundColor: color,
                borderRadius: 4
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { x: { beginAtZero: true, grid: { display: false } } }
        }
    });
}

function renderPieChart(ctxId, labels, data) {
    const ctx = document.getElementById(ctxId).getContext('2d');
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: [
                    '#2563eb', '#3b82f6', '#60a5fa', '#93c5fd', '#bfdbfe',
                    '#1d4ed8', '#1e40af', '#1e3a8a', '#dbeafe'
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'right' } }
        }
    });
}

function renderLineChart(ctxId, labels, data) {
    const ctx = document.getElementById(ctxId).getContext('2d');
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Transacciones',
                data: data,
                borderColor: '#ef4444',
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { 
                y: { beginAtZero: true },
                x: { grid: { display: false } }
            }
        }
    });
}

async function initDashboard() {
    // 1. Fetch KPIs
    const kpis = await fetchData('/api/resumen/kpis');
    if (kpis) {
        document.getElementById('kpi-unidades').innerText = kpis.total_unidades.toLocaleString();
        document.getElementById('kpi-transacciones').innerText = kpis.total_transacciones.toLocaleString();
        document.getElementById('kpi-clientes').innerText = kpis.clientes_unicos.toLocaleString();
        document.getElementById('kpi-avg').innerText = kpis.promedio_productos_por_transaccion;
    }

    // 2. Top Products
    const productsData = await fetchData('/api/resumen/top-productos');
    if (productsData) {
        const labels = productsData.data.map(p => `Prod ${p.product_id}`);
        const values = productsData.data.map(p => p.unidades);
        renderBarChart('chart-products', labels, values, 'Unidades', '#3b82f6');
    }

    // 3. Top Customers
    const customersData = await fetchData('/api/resumen/top-clientes');
    if (customersData) {
        const labels = customersData.data.map(c => `Cliente ${c.customer_id}`);
        const values = customersData.data.map(c => c.transacciones);
        renderBarChart('chart-customers', labels, values, 'Transacciones', '#10b981');
    }

    // 4. Categories
    const categoriesData = await fetchData('/api/resumen/categorias');
    if (categoriesData) {
        const topCats = categoriesData.data.slice(0, 8);
        const labels = topCats.map(c => c.category_name);
        const values = topCats.map(c => c.unidades);
        
        // Add "Others"
        const othersVal = categoriesData.data.slice(8).reduce((acc, c) => acc + c.unidades, 0);
        if (othersVal > 0) {
            labels.push('OTRAS');
            values.push(othersVal);
        }
        renderPieChart('chart-categories', labels, values);
    }

    // 5. Peak Days
    const timeData = await fetchData('/api/resumen/dias-pico');
    if (timeData) {
        const labels = timeData.data.map(d => d.fecha);
        const values = timeData.data.map(d => d.transacciones);
        renderLineChart('chart-time', labels, values);
    }
}

document.addEventListener('DOMContentLoaded', initDashboard);
