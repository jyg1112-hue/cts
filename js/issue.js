(function () {
  let state = {
    cargoType: "coal",
    year: 2025,
    brand: "",
    category: "",
    keyword: "",
    page: 1,
    pageSize: 20
  };

  let keywordTimer = null;

  function formatDate(v) {
    const d = new Date(v);
    if (Number.isNaN(d.getTime())) return "";
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return y + "-" + m + "-" + day;
  }

  function updateTabStyles() {
    document.querySelectorAll(".cargo-tab").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.cargo === state.cargoType);
    });
    document.querySelectorAll(".year-btn").forEach((btn) => {
      const y = btn.dataset.year === "all" ? "all" : Number(btn.dataset.year);
      btn.classList.toggle("active", y === state.year);
      btn.dataset.cargo = state.cargoType;
    });
    document.querySelectorAll(".category-btn").forEach((btn) => {
      btn.classList.toggle("active", (btn.dataset.category || "") === state.category);
    });
  }

  async function populateBrandFilter() {
    const sel = document.getElementById("brandSelect");
    if (!sel || !window.dbApi) return;
    const rows = await window.dbApi.fetchCargoRecords({
      cargo: state.cargoType,
      year: state.year === "all" ? "전체누적" : state.year
    });
    const brands = Array.from(new Set(rows.map((r) => String(r.brand || "").trim()).filter(Boolean))).sort();
    const current = state.brand;
    sel.innerHTML = '<option value="">브랜드 전체</option>' + brands.map((b) => '<option value="' + b + '">' + b + "</option>").join("");
    sel.value = current;
  }

  function renderIssueStats(stats) {
    const wrap = document.getElementById("issueStatsRow");
    if (!wrap) return;
    const cats = (window.APP_CONFIG && window.APP_CONFIG.ISSUE_CATEGORIES) || {};
    if (!Array.isArray(stats) || stats.length === 0) {
      wrap.innerHTML = '<div class="issue-empty">통계 데이터가 없습니다.</div>';
      return;
    }
    const total = stats.reduce((a, v) => a + Number(v.count || 0), 0);
    wrap.innerHTML = stats.map((s) => {
      const c = cats[s.category] || cats["기타"] || { color: "#888780", bgColor: "#F1EFE8" };
      const pct = total > 0 ? Math.round((Number(s.count || 0) / total) * 100) : 0;
      return (
        '<div class="issue-stat-badge" style="background:' + c.bgColor + ';color:' + c.color + ';">' +
          "<strong>" + s.category + "</strong>" +
          "<span>" + Math.round(Number(s.count || 0)).toLocaleString("ko-KR") + "건</span>" +
          "<span>(" + pct + "%)</span>" +
        "</div>"
      );
    }).join("");
  }

  function renderIssueList(records, appendMode) {
    const list = document.getElementById("issueList");
    if (!list) return;
    const cats = (window.APP_CONFIG && window.APP_CONFIG.ISSUE_CATEGORIES) || {};
    if (!appendMode) list.innerHTML = "";
    if (!records || records.length === 0) {
      if (!appendMode) list.innerHTML = '<div class="issue-empty">조건에 맞는 이슈가 없습니다.</div>';
      return;
    }

    const html = records.map((r, idx) => {
      const cat = (r.issue_categories && r.issue_categories[0]) || "기타";
      const catCfg = cats[cat] || cats["기타"] || { color: "#888780", bgColor: "#F1EFE8" };
      const txt = String(r.note || "");
      const long = txt.length > 150;
      const shortText = long ? (txt.slice(0, 150) + "...") : txt;
      const key = "issue-" + r.id + "-" + state.page + "-" + idx;
      return (
        '<article class="issue-item" style="border-left-color:' + catCfg.color + ';">' +
          '<div class="issue-head">' +
            '<div class="issue-vessel">' + (r.vessel_name || "-") + "</div>" +
            '<span class="cat-badge" style="color:' + catCfg.color + ";background:" + catCfg.bgColor + ';">' + cat + "</span>" +
          "</div>" +
          '<div class="issue-meta">' + formatDate(r.date) + " · " + (r.brand || "-") + "</div>" +
          '<div class="issue-text" id="' + key + '">' + shortText + "</div>" +
          (long ? '<button class="more-btn" type="button" data-target="' + key + '" data-full="' + encodeURIComponent(txt) + '" data-short="' + encodeURIComponent(shortText) + '">더보기</button>' : "") +
        "</article>"
      );
    }).join("");

    list.insertAdjacentHTML("beforeend", html);
  }

  function bindMoreToggle() {
    const list = document.getElementById("issueList");
    if (!list) return;
    list.addEventListener("click", (e) => {
      const btn = e.target.closest(".more-btn");
      if (!btn) return;
      const targetId = btn.dataset.target;
      const el = document.getElementById(targetId);
      if (!el) return;
      const isOpen = btn.dataset.open === "1";
      if (isOpen) {
        el.textContent = decodeURIComponent(btn.dataset.short || "");
        el.classList.remove("full");
        btn.textContent = "더보기";
        btn.dataset.open = "0";
      } else {
        el.textContent = decodeURIComponent(btn.dataset.full || "");
        el.classList.add("full");
        btn.textContent = "접기";
        btn.dataset.open = "1";
      }
    });
  }

  async function loadIssues() {
    try {
      const yearParam = state.year === "all" ? "all" : Number(state.year);
      const appendMode = state.page > 1;
      const statsPromise = window.dbApi.fetchIssueStats
        ? window.dbApi.fetchIssueStats(state.cargoType, yearParam)
        : window.dbApi.fetchIssueSummary({ cargo: state.cargoType, year: yearParam === "all" ? "전체누적" : yearParam })
          .then((rows) => rows.map((r) => ({ category: r.name, count: r.count })));
      const listPromise = window.dbApi.fetchIssueRecords(state);
      const results = await Promise.all([statsPromise, listPromise]);
      renderIssueStats(results[0]);
      renderIssueList(results[1].records || [], appendMode);
      const moreBtn = document.getElementById("loadMoreBtn");
      if (moreBtn) moreBtn.style.display = results[1].hasMore ? "inline-flex" : "none";
    } catch (e) {
      const list = document.getElementById("issueList");
      if (list && state.page === 1) list.innerHTML = '<div class="issue-empty">데이터를 불러올 수 없습니다.</div>';
    }
  }

  function bindFilterEvents() {
    document.querySelectorAll(".cargo-tab").forEach((btn) => {
      btn.addEventListener("click", async function () {
        state.cargoType = this.dataset.cargo || "coal";
        state.page = 1;
        await populateBrandFilter();
        updateTabStyles();
        loadIssues();
      });
    });

    document.querySelectorAll(".year-btn").forEach((btn) => {
      btn.addEventListener("click", function () {
        state.year = btn.dataset.year === "all" ? "all" : Number(btn.dataset.year);
        state.page = 1;
        updateTabStyles();
        loadIssues();
      });
    });

    const brandSelect = document.getElementById("brandSelect");
    if (brandSelect) {
      brandSelect.addEventListener("change", function () {
        state.brand = this.value || "";
        state.page = 1;
        loadIssues();
      });
    }

    document.querySelectorAll(".category-btn").forEach((btn) => {
      btn.addEventListener("click", function () {
        state.category = this.dataset.category || "";
        state.page = 1;
        updateTabStyles();
        loadIssues();
      });
    });

    const keywordInput = document.getElementById("keywordInput");
    if (keywordInput) {
      keywordInput.addEventListener("input", function () {
        const value = this.value || "";
        clearTimeout(keywordTimer);
        keywordTimer = setTimeout(() => {
          state.keyword = value.trim();
          state.page = 1;
          loadIssues();
        }, 300);
      });
    }

    const moreBtn = document.getElementById("loadMoreBtn");
    if (moreBtn) {
      moreBtn.addEventListener("click", function () {
        state.page += 1;
        loadIssues();
      });
    }
  }

  document.addEventListener("DOMContentLoaded", async function () {
    bindFilterEvents();
    bindMoreToggle();
    updateTabStyles();
    await populateBrandFilter();
    loadIssues();
  });
})();
