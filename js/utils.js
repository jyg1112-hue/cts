(function () {
  function formatNumber(value) {
    return Number(value || 0).toLocaleString("ko-KR");
  }

  function formatDate(value) {
    if (!value) return "";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return "";
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return y + "-" + m + "-" + day;
  }

  window.appUtils = {
    formatNumber,
    formatDate
  };
})();
