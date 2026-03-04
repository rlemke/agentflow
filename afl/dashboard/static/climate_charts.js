/**
 * Climate Trends — Chart.js visualizations
 *
 * ES module that renders 4 charts (temperature, precipitation,
 * extreme events, decadal comparison) from /climate-trends/api/data.
 *
 * @license Apache-2.0
 */

let tempChart = null;
let precipChart = null;
let extremeChart = null;
let decadeChart = null;

function destroyCharts() {
    if (tempChart)   { tempChart.destroy();   tempChart = null; }
    if (precipChart) { precipChart.destroy(); precipChart = null; }
    if (extremeChart){ extremeChart.destroy(); extremeChart = null; }
    if (decadeChart) { decadeChart.destroy(); decadeChart = null; }
}

function renderTemperatureChart(yearly) {
    const ctx = document.getElementById("chart-temperature").getContext("2d");
    tempChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: yearly.map(d => d.year),
            datasets: [{
                label: "Mean Temp (°C)",
                data: yearly.map(d => d.temp_mean),
                borderColor: "#e74c3c",
                backgroundColor: "rgba(231,76,60,0.1)",
                fill: true,
                tension: 0.3,
                pointRadius: 1,
            }],
        },
        options: {
            responsive: true,
            plugins: { legend: { display: true } },
            scales: {
                x: { title: { display: true, text: "Year" } },
                y: { title: { display: true, text: "°C" } },
            },
        },
    });
}

function renderPrecipitationChart(yearly) {
    const ctx = document.getElementById("chart-precipitation").getContext("2d");
    precipChart = new Chart(ctx, {
        type: "bar",
        data: {
            labels: yearly.map(d => d.year),
            datasets: [{
                label: "Annual Precip (mm)",
                data: yearly.map(d => d.precip_annual),
                backgroundColor: "rgba(52,152,219,0.6)",
                borderColor: "#3498db",
                borderWidth: 1,
            }],
        },
        options: {
            responsive: true,
            plugins: { legend: { display: true } },
            scales: {
                x: { title: { display: true, text: "Year" } },
                y: { title: { display: true, text: "mm" } },
            },
        },
    });
}

function renderExtremesChart(yearly) {
    const ctx = document.getElementById("chart-extremes").getContext("2d");
    extremeChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: yearly.map(d => d.year),
            datasets: [
                {
                    label: "Hot Days (>35°C)",
                    data: yearly.map(d => d.hot_days),
                    borderColor: "#e67e22",
                    backgroundColor: "rgba(230,126,34,0.1)",
                    fill: false,
                    tension: 0.3,
                    pointRadius: 1,
                },
                {
                    label: "Frost Days (<0°C)",
                    data: yearly.map(d => d.frost_days),
                    borderColor: "#3498db",
                    backgroundColor: "rgba(52,152,219,0.1)",
                    fill: false,
                    tension: 0.3,
                    pointRadius: 1,
                },
            ],
        },
        options: {
            responsive: true,
            plugins: { legend: { display: true } },
            scales: {
                x: { title: { display: true, text: "Year" } },
                y: { title: { display: true, text: "Days" } },
            },
        },
    });
}

function renderDecadeChart(decades) {
    const labels = Object.keys(decades).sort();
    const temps = labels.map(d => decades[d].avg_temp);
    const precips = labels.map(d => decades[d].avg_precip);

    const ctx = document.getElementById("chart-decades").getContext("2d");
    decadeChart = new Chart(ctx, {
        type: "bar",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Avg Temp (°C)",
                    data: temps,
                    backgroundColor: "rgba(231,76,60,0.6)",
                    borderColor: "#e74c3c",
                    borderWidth: 1,
                    yAxisID: "y",
                },
                {
                    label: "Avg Precip (mm)",
                    data: precips,
                    backgroundColor: "rgba(52,152,219,0.6)",
                    borderColor: "#3498db",
                    borderWidth: 1,
                    yAxisID: "y1",
                },
            ],
        },
        options: {
            responsive: true,
            plugins: { legend: { display: true } },
            scales: {
                x: { title: { display: true, text: "Decade" } },
                y: { type: "linear", position: "left", title: { display: true, text: "°C" } },
                y1: { type: "linear", position: "right", title: { display: true, text: "mm" }, grid: { drawOnChartArea: false } },
            },
        },
    });
}

function updateSummary(trend) {
    const panel = document.getElementById("summary-panel");
    if (!trend || !trend.state) {
        panel.style.display = "none";
        return;
    }
    panel.style.display = "block";

    const warming = trend.warming_rate_per_decade || 0;
    const precip = trend.precip_change_pct || 0;
    const start = trend.start_year || "?";
    const end = trend.end_year || "?";

    document.getElementById("summary-warming").textContent =
        `Warming: ${warming >= 0 ? "+" : ""}${warming}°C per decade`;
    document.getElementById("summary-precip").textContent =
        `Precipitation change: ${precip >= 0 ? "+" : ""}${precip}%`;
    document.getElementById("summary-years").textContent =
        `Period: ${start} — ${end}`;
}

function updateNarrative(narrative) {
    const panel = document.getElementById("narrative-panel");
    if (!narrative) {
        panel.style.display = "none";
        return;
    }
    panel.style.display = "block";
    document.getElementById("narrative-text").textContent = narrative;
}

async function loadState(state) {
    if (!state) {
        document.getElementById("no-data-msg").style.display = "block";
        document.getElementById("charts-container").style.display = "none";
        document.getElementById("summary-panel").style.display = "none";
        document.getElementById("narrative-panel").style.display = "none";
        return;
    }

    const resp = await fetch(`/climate-trends/api/data?state=${encodeURIComponent(state)}`);
    const data = await resp.json();

    destroyCharts();

    const yearly = data.yearly || [];
    const trend = data.trend || {};
    const decades = trend.decades || {};

    document.getElementById("no-data-msg").style.display = yearly.length ? "none" : "block";
    document.getElementById("charts-container").style.display = yearly.length ? "block" : "none";

    if (yearly.length) {
        renderTemperatureChart(yearly);
        renderPrecipitationChart(yearly);
        renderExtremesChart(yearly);
    }
    if (Object.keys(decades).length) {
        renderDecadeChart(decades);
    }

    updateSummary(trend);
    updateNarrative(data.narrative);
}

export function initClimateCharts() {
    const select = document.getElementById("state-select");
    if (!select) return;
    select.addEventListener("change", () => loadState(select.value));
}
