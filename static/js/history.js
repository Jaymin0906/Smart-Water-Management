/**
 * AquaPulse - Water History & Chart.js Visualization
 */

let waterChartInstance = null;

function initWaterHistoryChart() {
  const chartCanvas = document.getElementById("waterHistoryChart");
  if (!chartCanvas) return;

  const limitSelect = document.getElementById("chartLimitSelect");
  const currentLimit = limitSelect ? limitSelect.value : 20;

  fetch(`/api/history?limit=${currentLimit}`)
    .then((res) => res.json())
    .then((data) => {
      renderChart(chartCanvas, data);
    })
    .catch((err) => {
      console.error("Error fetching historical telemetry:", err);
    });
}

function renderChart(canvas, data) {
  const ctx = canvas.getContext("2d");

  // Create subtle blue-to-cyan gradient
  const gradient = ctx.createLinearGradient(0, 0, 0, 300);
  gradient.addColorStop(0, "rgba(6, 182, 212, 0.45)");
  gradient.addColorStop(0.7, "rgba(2, 132, 199, 0.12)");
  gradient.addColorStop(1, "rgba(2, 132, 199, 0.0)");

  if (waterChartInstance) {
    waterChartInstance.destroy();
  }

  // Format timestamp labels (show time or short date)
  const formattedLabels = data.labels.map((ts) => {
    try {
      const parts = ts.split(" ");
      return parts.length > 1 ? parts[1].substring(0, 5) : ts;
    } catch (e) {
      return ts;
    }
  });

  waterChartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: formattedLabels,
      datasets: [
        {
          label: "Water Level (%)",
          data: data.levels,
          borderColor: "#0284c7",
          backgroundColor: gradient,
          borderWidth: 2.5,
          tension: 0.38,
          fill: true,
          pointBackgroundColor: "#0c1b33",
          pointBorderColor: "#38bdf8",
          pointBorderWidth: 2,
          pointRadius: 4,
          pointHoverRadius: 6,
          yAxisID: "y"
        },
        {
          label: "Volume (Litres)",
          data: data.litres,
          borderColor: "#06b6d4",
          borderDash: [5, 5],
          borderWidth: 1.8,
          tension: 0.38,
          fill: false,
          pointRadius: 2,
          yAxisID: "y1"
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index",
        intersect: false
      },
      plugins: {
        legend: {
          position: "top",
          labels: {
            usePointStyle: true,
            boxWidth: 8,
            font: {
              family: "'Inter', sans-serif",
              size: 12,
              weight: "600"
            }
          }
        },
        tooltip: {
          backgroundColor: "#0c1b33",
          titleFont: { family: "'Inter', sans-serif", size: 13, weight: "700" },
          bodyFont: { family: "'Inter', sans-serif", size: 12 },
          padding: 12,
          cornerRadius: 8,
          callbacks: {
            afterBody: function (context) {
              const idx = context[0].dataIndex;
              const pump = data.pumps ? data.pumps[idx] : "N/A";
              const fullTime = data.labels ? data.labels[idx] : "";
              return `Pump: ${pump}\nRecorded: ${fullTime}`;
            }
          }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            font: { family: "'Inter', sans-serif", size: 11 },
            color: "#64748b"
          }
        },
        y: {
          type: "linear",
          display: true,
          position: "left",
          min: 0,
          max: 100,
          ticks: {
            callback: (val) => `${val}%`,
            font: { family: "'Inter', sans-serif", size: 11 },
            color: "#64748b"
          },
          grid: {
            color: "#f1f5f9"
          }
        },
        y1: {
          type: "linear",
          display: true,
          position: "right",
          grid: {
            drawOnChartArea: false
          },
          ticks: {
            callback: (val) => `${val} L`,
            font: { family: "'Inter', sans-serif", size: 11 },
            color: "#0891b2"
          }
        }
      }
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initWaterHistoryChart();

  const limitSelect = document.getElementById("chartLimitSelect");
  if (limitSelect) {
    limitSelect.addEventListener("change", () => {
      initWaterHistoryChart();
    });
  }
});
