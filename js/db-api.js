/**
 * 레거시 대시보드/이슈 페이지용 DB API 스텁.
 * Supabase 제거 후 동일한 window.dbApi 시그니처를 유지하며, 데이터는 빈 값을 반환합니다.
 */
(function () {
  async function fetchCargoRecords(_filters) {
    return [];
  }

  async function fetchIssueCategories() {
    return [];
  }

  async function fetchMonthlySummary() {
    return [];
  }

  async function fetchBrandSummary() {
    return [];
  }

  async function fetchIssueSummary() {
    return [];
  }

  async function fetchIssueStats() {
    return [];
  }

  async function fetchIssueRecords() {
    return { records: [], hasMore: false, total: 0 };
  }

  async function fetchKpiSummary() {
    return { totalBlTon: 0, totalVesselCount: 0, avgUnloadRate: 0, issueCount: 0 };
  }

  async function rawQueryCargoRecords() {
    return [];
  }

  async function ping() {
    return { ok: true };
  }

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
        vessel_name: r.vessel_name,
      }));
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
    ping,
  };
})();
