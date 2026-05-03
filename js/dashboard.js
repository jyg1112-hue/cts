(function () {
  let state = {
    cargoType: "coal",   // 'coal' | 'nickel'
    year: 2025,          // 2023 | 2024 | 2025 | 'all'
    compareYear: 2024
  };

  function normalizeYearValue(v) {
    if (v === "전체누적" || v === "all") return "all";
    const n = Number(v);
    return Number.isFinite(n) ? n : "all";
  }

  function normalizeCargoValue(v) {
    if (v === "석탄" || v === "coal") return "coal";
    if (v === "니켈" || v === "nickel") return "nickel";
    return "coal";
  }

  function filtersFromState(yearOverride) {
    const y = yearOverride !== undefined ? yearOverride : state.year;
    return {
      cargo: state.cargoType,
      year: y === "all" ? "전체누적" : y
    };
  }

  function formatTon(v) {
    return Math.round(Number(v || 0)).toLocaleString("ko-KR") + " t";
  }

  function setSkeletonLoading(on) {
    document.querySelectorAll(".kpi-grid .card, .kpi-grid .kpi-card").forEach((el) => {
      el.classList.toggle("skeleton", !!on);
    });
  }

  function showErrorMessage(message) {
    const text = message || "데이터를 불러올 수 없습니다";
    const ids = ["kpiTotalBl", "kpiShipCount", "kpiAvgRate", "kpiIssueCount"];
    ids.forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.textContent = text;
    });
    const targets = ["monthlyTrendChart", "issueDonutChart", "brandCompareChart"];
    targets.forEach((id) => {
      const canvas = document.getElementById(id);
      if (!canvas || !canvas.parentElement) return;
      let err = canvas.parentElement.querySelector(".chart-error");
      if (!err) {
        err = document.createElement("div");
        err.className = "chart-error";
        err.style.marginTop = "8px";
        err.style.fontSize = "12px";
        err.style.color = "#D85A30";
        canvas.parentElement.appendChild(err);
      }
      err.textContent = text;
    });
  }

  function clearErrorMessage() {
    document.querySelectorAll(".chart-error").forEach((el) => el.remove());
  }

  function ensureKpiDiffEl(valueEl) {
    if (!valueEl || !valueEl.parentElement) return null;
    let diffEl = valueEl.parentElement.querySelector(".kpi-diff");
    if (!diffEl) {
      diffEl = document.createElement("div");
      diffEl.className = "kpi-diff";
      valueEl.insertAdjacentElement("afterend", diffEl);
    }
    return diffEl;
  }

  // DB 래퍼: 요청 스펙의 함수명을 현재 dbApi 기반으로 매핑
  const DB = {
    async init() {
      if (!window.dbApi || !window.dbApi.ping) return;
      await window.dbApi.ping();
    },

    async fetchKPI(cargoType, year) {
      if (!window.dbApi || !window.dbApi.fetchKpiSummary) return { totalBlTon: 0, totalVesselCount: 0, avgUnloadRate: 0, issueCount: 0 };
      return window.dbApi.fetchKpiSummary({ cargo: cargoType, year: year === "all" ? "전체누적" : year });
    },

    async fetchMonthlyTrend(cargoType, years) {
      const y1 = years[0];
      const y2 = years[1];
      const rows1 = await window.dbApi.fetchMonthlySummary({ cargo: cargoType, year: y1 });
      const rows2 = await window.dbApi.fetchMonthlySummary({ cargo: cargoType, year: y2 === "all" ? "전체누적" : y2 });
      const map1 = new Map(rows1.map((r) => [Number(r.month), r]));
      const map2 = new Map(rows2.map((r) => [Number(r.month), r]));
      const labels = Array.from({ length: 12 }, function (_, i) { return (i + 1) + "월"; });
      const bl2024 = [];
      const bl2025 = [];
      const rate2025 = [];
      for (let m = 1; m <= 12; m++) {
        bl2024.push(Math.round((map1.get(m) && map1.get(m).bl_ton) || 0));
        bl2025.push(Math.round((map2.get(m) && map2.get(m).bl_ton) || 0));
        rate2025.push(Math.round((map2.get(m) && map2.get(m).avg_unload_rate) || 0));
      }
      return { labels: labels, datasets: { bl2025: bl2025, bl2024: bl2024, rate2025: rate2025 } };
    },

    async fetchBrandStats(cargoType, year) {
      const filters = { cargo: cargoType, year: year === "all" ? "전체누적" : year };
      const [summary, rows] = await Promise.all([
        window.dbApi.fetchBrandSummary(filters),
        window.dbApi.fetchCargoRecords(filters)
      ]);
      const issueCountByBrand = {};
      rows.forEach((r) => {
        const b = r.brand || "미분류";
        const cnt = Array.isArray(r.issue_categories) ? r.issue_categories.length : 0;
        issueCountByBrand[b] = (issueCountByBrand[b] || 0) + cnt;
      });
      return summary.map((s) => ({
        brand: s.brand,
        blTon: Math.round(Number(s.bl_ton || 0)),
        vesselCount: Math.round(Number(s.vessel_count || 0)),
        avgUnloadRate: Math.round(Number(s.avg_unload_rate || 0)),
        issueCount: Math.round(issueCountByBrand[s.brand] || 0)
      }));
    },

    async fetchIssueStats(cargoType, year) {
      const list = await window.dbApi.fetchIssueSummary({ cargo: cargoType, year: year === "all" ? "전체누적" : year });
      return list.map((it) => ({ category: it.name, count: Math.round(Number(it.count || 0)) }));
    }
  };

  function renderKPI(kpiData, prevKpiData) {
    const totalBlEl = document.getElementById("kpiTotalBl");
    const vesselEl = document.getElementById("kpiShipCount");
    const rateEl = document.getElementById("kpiAvgRate");
    const issueEl = document.getElementById("kpiIssueCount");

    if (totalBlEl) totalBlEl.textContent = formatTon(kpiData.totalBlTon);
    if (vesselEl) vesselEl.textContent = Math.round(kpiData.totalVesselCount || 0).toLocaleString("ko-KR") + " 척";
    if (rateEl) rateEl.textContent = Math.round(kpiData.avgUnloadRate || 0).toLocaleString("ko-KR") + " t/d";
    if (issueEl) issueEl.textContent = Math.round(kpiData.issueCount || 0).toLocaleString("ko-KR") + " 건";

    if (!prevKpiData) return;
    const pairs = [
      [totalBlEl, kpiData.totalBlTon, prevKpiData.totalBlTon, " t"],
      [vesselEl, kpiData.totalVesselCount, prevKpiData.totalVesselCount, " 척"],
      [rateEl, kpiData.avgUnloadRate, prevKpiData.avgUnloadRate, " t/d"],
      [issueEl, kpiData.issueCount, prevKpiData.issueCount, " 건"]
    ];
    pairs.forEach((p) => {
      const diffEl = ensureKpiDiffEl(p[0]);
      if (!diffEl) return;
      const diff = Math.round(Number(p[1] || 0) - Number(p[2] || 0));
      const mark = diff >= 0 ? "▲" : "▼";
      diffEl.classList.remove("up", "down");
      diffEl.classList.add(diff >= 0 ? "up" : "down");
      diffEl.textContent = mark + " " + Math.abs(diff).toLocaleString("ko-KR") + p[3] + " (전년)";
    });
  }

  function renderBrandTable(brands) {
    const tbody = document.getElementById("brandDetailBody");
    if (!tbody) return;
    const maxRate = brands.length ? Math.max.apply(null, brands.map((b) => Number(b.avgUnloadRate || 0))) : 0;
    tbody.innerHTML = brands.map((b) => {
      const rate = Math.round(Number(b.avgUnloadRate || 0));
      const widthPct = maxRate > 0 ? (rate / maxRate) * 100 : 0;
      const issueStyle = Number(b.issueCount || 0) >= 30 ? "color:#D85A30;font-weight:700;" : "";
      return (
        "<tr>" +
          "<td>" + b.brand + "</td>" +
          "<td>" + Math.round(b.blTon || 0).toLocaleString("ko-KR") + " t</td>" +
          "<td>" + Math.round(b.vesselCount || 0).toLocaleString("ko-KR") + " 척</td>" +
          "<td>" +
            '<div style="display:flex;align-items:center;gap:8px;">' +
              '<div class="rate-bar-bg" style="flex:1;"><div class="rate-bar" style="width:' + widthPct.toFixed(1) + '%;background:var(--coal-primary);"></div></div>' +
              "<span>" + rate.toLocaleString("ko-KR") + " t/d</span>" +
            "</div>" +
            '<div style="font-size:11px;' + issueStyle + '">이슈 ' + Math.round(b.issueCount || 0).toLocaleString("ko-KR") + "건</div>" +
          "</td>" +
        "</tr>"
      );
    }).join("");
  }

  function updateCargoTabActive() {
    const tabs = document.querySelectorAll(".tab-btn, .cargo-tab");
    tabs.forEach((btn) => {
      const cargo = normalizeCargoValue(btn.dataset.cargo);
      btn.classList.toggle("active", cargo === state.cargoType);
      if (!btn.dataset.cargo) btn.dataset.cargo = cargo;
    });
  }

  function updateYearButtonActive() {
    const yearBtns = document.querySelectorAll(".year-btn");
    yearBtns.forEach((btn) => {
      const y = normalizeYearValue(btn.dataset.year);
      btn.classList.toggle("active", y === state.year);
      btn.dataset.cargo = state.cargoType;
    });
  }

  async function loadDashboard() {
    setSkeletonLoading(true);
    clearErrorMessage();
    try {
      const activeYear = state.year;
      const prevYear = activeYear === "all" ? 2024 : Number(activeYear) - 1;
      const compareBase = Number(state.compareYear) || prevYear;

      const results = await Promise.all([
        DB.fetchKPI(state.cargoType, activeYear),                                   // 1
        DB.fetchMonthlyTrend(state.cargoType, [compareBase, activeYear]),           // 2
        DB.fetchBrandStats(state.cargoType, activeYear),                            // 3
        DB.fetchIssueStats(state.cargoType, activeYear),                            // 4
        DB.fetchKPI(state.cargoType, prevYear)                                      // KPI diff
      ]);

      const kpiData = results[0];
      const monthlyData = results[1];
      const brands = results[2];
      const issueStats = results[3];
      const prevKpiData = results[4];

      renderKPI(kpiData, prevKpiData);
      if (window.Charts) {
        window.Charts.createMonthlyChart("monthlyTrendChart", monthlyData, state.cargoType);
        window.Charts.createBrandChart("brandCompareChart", brands, state.cargoType);
        window.Charts.createIssueDonut("issueDonutChart", issueStats);
      }
      renderBrandTable(brands);
    } catch (err) {
      console.error(err);
      showErrorMessage("데이터를 불러올 수 없습니다");
    } finally {
      setSkeletonLoading(false);
    }
  }

  function bindEvents() {
    document.querySelectorAll(".tab-btn, .cargo-tab").forEach((btn) => {
      btn.addEventListener("click", function () {
        state.cargoType = normalizeCargoValue(this.dataset.cargo);
        updateCargoTabActive();
        updateYearButtonActive();
        loadDashboard();
      });
    });

    document.querySelectorAll(".year-btn").forEach((btn) => {
      btn.addEventListener("click", function () {
        state.year = normalizeYearValue(this.dataset.year);
        if (state.year !== "all") state.compareYear = Number(state.year) - 1;
        updateYearButtonActive();
        loadDashboard();
      });
    });
  }

  document.addEventListener("DOMContentLoaded", async function () {
    try {
      await DB.init();
    } catch (e) {
      console.warn("db init failed:", e);
    }
    bindEvents();                // 2. 이벤트 등록
    updateCargoTabActive();
    updateYearButtonActive();
    loadDashboard();             // 3. loadDashboard() 호출
  });
})();
