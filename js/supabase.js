(function () {
  const cfg = window.APP_CONFIG || {};
  window.supabaseClient = (window.supabase && cfg.SUPABASE_URL && cfg.SUPABASE_ANON_KEY)
    ? window.supabase.createClient(cfg.SUPABASE_URL, cfg.SUPABASE_ANON_KEY)
    : null;

  function normalizeCargoType(cargo) {
    if (!cargo || cargo === "전체") return null;
    if (cargo === "석탄" || cargo === "coal") return "coal";
    if (cargo === "니켈" || cargo === "nickel") return "nickel";
    return String(cargo).toLowerCase();
  }

  function buildCargoRecordQuery(filters, selectClause) {
    let query = window.supabaseClient.from("cargo_records").select(selectClause || "*");
    const cargoType = normalizeCargoType(filters?.cargo);
    if (cargoType) query = query.eq("cargo_type", cargoType);
    if (filters?.year && filters.year !== "전체누적") query = query.eq("year", Number(filters.year));
    if (filters?.month != null && filters.month !== "") query = query.eq("month", Number(filters.month));
    return query;
  }

  async function fetchCargoRecords(filters) {
    if (!window.supabaseClient) return [];
    const { data, error } = await buildCargoRecordQuery(filters, "*")
      .order("year", { ascending: true })
      .order("month", { ascending: true })
      .order("created_at", { ascending: true });
    if (error) throw error;
    return data || [];
  }

  async function fetchIssueCategories() {
    if (!window.supabaseClient) return [];
    const { data, error } = await window.supabaseClient
      .from("issue_categories")
      .select("id,name,keywords,color,bg_color")
      .order("id", { ascending: true });
    if (error) throw error;
    return data || [];
  }

  async function fetchMonthlySummary(filters) {
    const rows = await fetchCargoRecords(filters);
    const map = new Map();
    rows.forEach((r) => {
      const m = Number(r.month || 0);
      if (!map.has(m)) {
        map.set(m, { month: m, bl_ton: 0, vessel_count: 0, unload_rate_sum: 0, unload_rate_cnt: 0 });
      }
      const item = map.get(m);
      item.bl_ton += Number(r.bl_ton || 0);
      item.vessel_count += 1;
      if (r.unload_rate != null) {
        item.unload_rate_sum += Number(r.unload_rate || 0);
        item.unload_rate_cnt += 1;
      }
    });
    return Array.from(map.values())
      .sort((a, b) => a.month - b.month)
      .map((v) => ({
        month: v.month,
        bl_ton: v.bl_ton,
        vessel_count: v.vessel_count,
        avg_unload_rate: v.unload_rate_cnt ? (v.unload_rate_sum / v.unload_rate_cnt) : 0
      }));
  }

  async function fetchBrandSummary(filters) {
    const rows = await fetchCargoRecords(filters);
    const map = new Map();
    rows.forEach((r) => {
      const brand = r.brand || "미분류";
      if (!map.has(brand)) {
        map.set(brand, { brand: brand, bl_ton: 0, vessel_count: 0, unload_rate_sum: 0, unload_rate_cnt: 0 });
      }
      const item = map.get(brand);
      item.bl_ton += Number(r.bl_ton || 0);
      item.vessel_count += 1;
      if (r.unload_rate != null) {
        item.unload_rate_sum += Number(r.unload_rate || 0);
        item.unload_rate_cnt += 1;
      }
    });
    return Array.from(map.values())
      .sort((a, b) => b.bl_ton - a.bl_ton)
      .map((v) => ({
        brand: v.brand,
        bl_ton: v.bl_ton,
        vessel_count: v.vessel_count,
        avg_unload_rate: v.unload_rate_cnt ? (v.unload_rate_sum / v.unload_rate_cnt) : 0
      }));
  }

  async function fetchIssueSummary(filters) {
    const rows = await fetchCargoRecords(filters);
    const counts = {};
    rows.forEach((r) => {
      const cats = Array.isArray(r.issue_categories) ? r.issue_categories : [];
      cats.forEach((cat) => {
        const key = String(cat || "기타").trim() || "기타";
        counts[key] = (counts[key] || 0) + 1;
      });
    });
    return Object.entries(counts)
      .map(function (entry) { return { name: entry[0], count: entry[1] }; })
      .sort((a, b) => b.count - a.count);
  }

  async function fetchIssueStats(cargoType, year) {
    const filters = {
      cargo: cargoType,
      year: year === "all" ? "전체누적" : year
    };
    const rows = await fetchIssueSummary(filters);
    return rows.map((r) => ({ category: r.name, count: r.count }));
  }

  async function fetchIssueRecords(state) {
    const filters = {
      cargo: state && state.cargoType ? state.cargoType : null,
      year: state && state.year === "all" ? "전체누적" : (state ? state.year : null)
    };
    const rows = await fetchCargoRecords(filters);
    const keyword = String((state && state.keyword) || "").trim().toLowerCase();
    const brand = String((state && state.brand) || "").trim();
    const category = String((state && state.category) || "").trim();
    const page = Math.max(1, Number((state && state.page) || 1));
    const pageSize = Math.max(1, Number((state && state.pageSize) || 20));

    let records = rows.filter((r) => Array.isArray(r.issue_categories) && r.issue_categories.length > 0)
      .map((r) => ({
        id: r.id,
        vessel_name: r.vessel_name,
        brand: r.brand,
        note: r.note || "",
        cargo_type: r.cargo_type,
        date: r.finished_at || r.started_at || r.created_at,
        issue_categories: Array.isArray(r.issue_categories) ? r.issue_categories : []
      }));

    if (brand) records = records.filter((r) => String(r.brand || "") === brand);
    if (category) records = records.filter((r) => r.issue_categories.includes(category));
    if (keyword) {
      records = records.filter((r) => {
        const hay = [
          r.vessel_name || "",
          r.brand || "",
          r.note || "",
          (r.issue_categories || []).join(" ")
        ].join(" ").toLowerCase();
        return hay.includes(keyword);
      });
    }

    records.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
    const start = (page - 1) * pageSize;
    const end = start + pageSize;
    return {
      records: records.slice(start, end),
      hasMore: end < records.length,
      total: records.length
    };
  }

  async function fetchKpiSummary(filters) {
    const rows = await fetchCargoRecords(filters);
    const totalBlTon = rows.reduce((acc, r) => acc + Number(r.bl_ton || 0), 0);
    const totalVesselCount = rows.length;
    const rateRows = rows.filter((r) => r.unload_rate != null);
    const avgUnloadRate = rateRows.length
      ? rateRows.reduce((acc, r) => acc + Number(r.unload_rate || 0), 0) / rateRows.length
      : 0;
    const issueCount = rows.reduce((acc, r) => acc + (Array.isArray(r.issue_categories) ? r.issue_categories.length : 0), 0);
    return { totalBlTon, totalVesselCount, avgUnloadRate, issueCount };
  }

  // 하위 호환: 기존 함수명 유지
  async function fetchWorkData(filters) {
    return fetchCargoRecords(filters);
  }

  async function fetchIssueData(filters) {
    const rows = await fetchCargoRecords(filters);
    return rows
      .filter((r) => Array.isArray(r.issue_categories) && r.issue_categories.length > 0)
      .map((r) => ({
        id: r.id,
        date: r.finished_at || r.started_at || r.created_at,
        title: (r.issue_categories || []).join(", "),
        memo: r.note || "",
        cargo_type: r.cargo_type,
        brand: r.brand,
        vessel_name: r.vessel_name
      }));
  }

  async function rawQueryCargoRecords(filters, selectClause) {
    if (!window.supabaseClient) return [];
    const { data, error } = await buildCargoRecordQuery(filters, selectClause || "*");
    if (error) throw error;
    return data || [];
  }

  async function ping() {
    if (!window.supabaseClient) return { ok: false, reason: "no-client" };
    const { error } = await window.supabaseClient.from("cargo_records").select("id").limit(1);
    return { ok: !error, error };
  }


  window.dbApi = {
    fetchCargoRecords,
    fetchIssueCategories,
    fetchMonthlySummary,
    fetchBrandSummary,
    fetchIssueSummary,
    fetchIssueStats,
    fetchIssueRecords,
    fetchKpiSummary,
    rawQueryCargoRecords,
    fetchWorkData,
    fetchIssueData,
    ping
  };
})();
