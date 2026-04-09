(function () {
  let monthlyChart = null;
  let issueDonutChart = null;
  let brandChart = null;
  let monthlyMeta = null;
  let brandMeta = null;
  let issueMeta = null;

  function roundNum(v) {
    return Math.round(Number(v || 0));
  }

  function getCssVar(name, fallback) {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fallback;
  }

  function hexToRgba(hex, alpha) {
    const clean = String(hex || "").replace("#", "");
    if (clean.length !== 6) return hex;
    const r = parseInt(clean.slice(0, 2), 16);
    const g = parseInt(clean.slice(2, 4), 16);
    const b = parseInt(clean.slice(4, 6), 16);
    return "rgba(" + r + ", " + g + ", " + b + ", " + alpha + ")";
  }

  function getCargoMainColor(cargoType) {
    return cargoType === "nickel"
      ? getCssVar("--nickel-primary", "#1D9E75")
      : getCssVar("--coal-primary", "#185FA5");
  }

  function ensureLegendElement(canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !canvas.parentElement) return null;
    const legendId = canvasId + "-legend";
    let legend = document.getElementById(legendId);
    if (!legend) {
      legend = document.createElement("div");
      legend.id = legendId;
      legend.style.marginTop = "10px";
      legend.style.display = "flex";
      legend.style.flexWrap = "wrap";
      legend.style.gap = "8px 10px";
      canvas.parentElement.appendChild(legend);
    }
    return legend;
  }

  function renderLegendItems(container, items) {
    if (!container) return;
    container.innerHTML = items.map(function (it) {
      return (
        '<span style="display:inline-flex;align-items:center;gap:6px;font-size:11px;color:#6b6b6b;">' +
          '<span style="display:inline-block;width:10px;height:10px;border-radius:999px;background:' + it.color + ';"></span>' +
          "<span>" + it.label + "</span>" +
        "</span>"
      );
    }).join("");
  }

  function createMonthlyChart(canvasId, data, cargoType) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !window.Chart) return null;
    if (monthlyChart) monthlyChart.destroy();

    const labels = (data && data.labels) || [];
    const ds = (data && data.datasets) || {};
    const bl2025 = (ds.bl2025 || []).map(roundNum);
    const bl2024 = (ds.bl2024 || []).map(roundNum);
    const rate2025 = (ds.rate2025 || []).map(roundNum);
    const main = getCargoMainColor(cargoType);
    const light = hexToRgba(main, 0.5);

    monthlyChart = new Chart(canvas, {
      data: {
        labels: labels,
        datasets: [
          { type: "bar", label: "2025 B/L량", yAxisID: "yBl", backgroundColor: main, borderColor: main, data: bl2025, borderRadius: 4 },
          { type: "bar", label: "2024 B/L량", yAxisID: "yBl", backgroundColor: light, borderColor: light, data: bl2024, borderRadius: 4 },
          { type: "line", label: "평균 하역율", yAxisID: "yRate", borderColor: "#D85A30", backgroundColor: "#D85A30", data: rate2025, tension: 0.25, pointRadius: 3 }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { autoSkip: false } },
          yBl: {
            position: "left",
            ticks: { callback: function (v) { return roundNum(v) + "k톤"; } }
          },
          yRate: {
            position: "right",
            grid: { drawOnChartArea: false },
            ticks: { callback: function (v) { return roundNum(v) + "k t/d"; } }
          }
        }
      }
    });

    renderLegendItems(ensureLegendElement(canvasId), [
      { label: "2025 B/L량", color: main },
      { label: "2024 B/L량", color: light },
      { label: "평균 하역율", color: "#D85A30" }
    ]);

    monthlyMeta = { canvasId: canvasId, data: data, cargoType: cargoType };
    return monthlyChart;
  }

  function createBrandChart(canvasId, brands, cargoType) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !window.Chart) return null;
    if (brandChart) brandChart.destroy();

    const list = Array.isArray(brands) ? brands : [];
    const labels = list.map(function (b) { return b.brand; });
    const values = list.map(function (b) { return roundNum(b.avgUnloadRate); });
    const max = values.length ? Math.max.apply(null, values) : 0;
    const main = getCargoMainColor(cargoType);
    const dim = hexToRgba(main, 0.6);
    const bg = values.map(function (v) { return v === max ? main : dim; });

    if (canvas.parentElement) {
      canvas.parentElement.style.height = String(list.length * 44 + 60) + "px";
    }

    brandChart = new Chart(canvas, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [{ label: "평균 하역율", data: values, backgroundColor: bg, borderColor: bg, borderRadius: 6 }]
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                return roundNum(ctx.raw).toLocaleString("ko-KR") + " t/day";
              }
            }
          }
        }
      }
    });

    renderLegendItems(ensureLegendElement(canvasId), [
      { label: "최고 하역율", color: main },
      { label: "기타 브랜드", color: dim }
    ]);

    brandMeta = { canvasId: canvasId, brands: brands, cargoType: cargoType };
    return brandChart;
  }

  function createIssueDonut(canvasId, issueStats) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !window.Chart) return null;
    if (issueDonutChart) issueDonutChart.destroy();

    const list = Array.isArray(issueStats) ? issueStats : [];
    const labels = list.map(function (i) { return i.category; });
    const values = list.map(function (i) { return roundNum(i.count); });
    const total = values.reduce(function (a, b) { return a + b; }, 0);
    const categoryConfig = (window.APP_CONFIG && window.APP_CONFIG.ISSUE_CATEGORIES) || {};
    const colors = labels.map(function (name) {
      return (categoryConfig[name] && categoryConfig[name].color) || "#888780";
    });

    issueDonutChart = new Chart(canvas, {
      type: "doughnut",
      data: {
        labels: labels,
        datasets: [{ data: values, backgroundColor: colors, borderWidth: 0 }]
      },
      options: {
        cutout: "65%",
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } }
      }
    });

    const legend = ensureLegendElement(canvasId);
    if (legend) {
      legend.innerHTML = list.map(function (it, idx) {
        const pct = total > 0 ? roundNum((Number(it.count || 0) / total) * 100) : 0;
        return (
          '<div style="display:flex;align-items:center;gap:6px;font-size:11px;color:#6b6b6b;">' +
            '<span style="display:inline-block;width:10px;height:10px;border-radius:999px;background:' + colors[idx] + ';"></span>' +
            '<span>' + it.category + "</span>" +
            '<span style="color:#9a9a9a;">' + roundNum(it.count) + "건 (" + pct + "%)</span>" +
          "</div>"
        );
      }).join("");
    }

    issueMeta = { canvasId: canvasId, issueStats: issueStats };
    return issueDonutChart;
  }

  function updateChartColors(cargoType) {
    if (monthlyMeta) createMonthlyChart(monthlyMeta.canvasId, monthlyMeta.data, cargoType);
    if (brandMeta) createBrandChart(brandMeta.canvasId, brandMeta.brands, cargoType);
  }

  window.Charts = {
    createMonthlyChart: createMonthlyChart,
    createBrandChart: createBrandChart,
    createIssueDonut: createIssueDonut,
    updateChartColors: updateChartColors
  };
})();
