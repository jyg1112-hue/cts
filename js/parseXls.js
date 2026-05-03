(function () {
  function toJsDateFromExcelCell(cellValue) {
    if (cellValue == null || cellValue === "") return null;
    if (cellValue instanceof Date) return cellValue;
    if (typeof cellValue === "number" && window.XLSX && XLSX.SSF && XLSX.SSF.parse_date_code) {
      const parsed = XLSX.SSF.parse_date_code(cellValue);
      if (!parsed) return null;
      return new Date(
        parsed.y,
        (parsed.m || 1) - 1,
        parsed.d || 1,
        parsed.H || 0,
        parsed.M || 0,
        Math.floor(parsed.S || 0)
      );
    }
    const d = new Date(cellValue);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  function cleanBrand(value) {
    return String(value || "").replace(/\n/g, " ").trim();
  }

  function isShiftExchange(value) {
    const v = String(value || "").trim();
    return v === "O" || v === "○";
  }

  function toNumber(value) {
    if (value == null || value === "") return null;
    const n = Number(String(value).replace(/,/g, "").trim());
    return Number.isFinite(n) ? n : null;
  }

  function isSkipRowByVesselNoAndName(vesselNoRaw, vesselNameRaw) {
    const vesselName = String(vesselNameRaw || "").trim();
    if (!vesselName) return true;
    const vesselNoText = String(vesselNoRaw || "").trim();
    if (vesselNoText === "제외하역률") return true;
    const vesselNo = Number(vesselNoText);
    return !Number.isFinite(vesselNo);
  }

  function getSheetRows(workbook, sheetName) {
    const ws = workbook.Sheets[sheetName];
    if (!ws) return [];
    return XLSX.utils.sheet_to_json(ws, { header: 1, defval: "", raw: true });
  }

  function parseNickelSheet(workbook, year) {
    const rows = getSheetRows(workbook, "니켈(년)");
    if (!rows.length) return [];
    const out = [];
    for (let i = 2; i < rows.length; i++) {
      const r = rows[i] || [];
      const vesselNoRaw = r[0];
      const voyageNo = String(r[1] || "").trim() || null;
      const month = toNumber(r[2]);
      const vesselName = String(r[3] || "").trim();
      const brand = cleanBrand(r[4]);
      const blTon = toNumber(r[5]);
      const startedAt = toJsDateFromExcelCell(r[6]);
      const finishedAt = toJsDateFromExcelCell(r[7]);
      const durationDays = toNumber(r[8]);
      const adjDays = toNumber(r[9]);
      const netDays = toNumber(r[10]);
      const unloadRate = toNumber(r[11]);
      const note = String(r[12] || "").trim() || null;
      const shiftExchange = isShiftExchange(r[13]);

      if (isSkipRowByVesselNoAndName(vesselNoRaw, vesselName)) continue;
      const vesselNo = Number(String(vesselNoRaw).trim());

      out.push({
        cargo_type: "nickel",
        year: Number(year),
        month: month,
        vessel_no: vesselNo,
        voyage_no: voyageNo,
        vessel_name: vesselName,
        brand: brand,
        bl_ton: blTon,
        started_at: startedAt,
        finished_at: finishedAt,
        duration_days: durationDays,
        adj_days: adjDays,
        net_days: netDays,
        unload_rate: unloadRate,
        shift_exchange: shiftExchange,
        note: note,
        issue_categories: window.classifyIssue ? window.classifyIssue(note || "") : ["기타"]
      });
    }
    return out;
  }

  function parseCoalSheet(workbook, year) {
    const rows = getSheetRows(workbook, "석탄(년)");
    if (!rows.length) return [];
    const out = [];
    for (let i = 2; i < rows.length; i++) {
      const r = rows[i] || [];
      const vesselNoRaw = r[0];
      const month = toNumber(r[1]);
      const vesselName = String(r[2] || "").trim();
      const brand = cleanBrand(r[3]);
      const blTon = toNumber(r[4]);
      const startedAt = toJsDateFromExcelCell(r[5]);
      const finishedAt = toJsDateFromExcelCell(r[6]);
      const durationDays = toNumber(r[7]);
      const adjDays = toNumber(r[8]);
      const netDays = toNumber(r[9]);
      const unloadRate = toNumber(r[10]);
      const note = String(r[11] || "").trim() || null;
      const shiftExchange = isShiftExchange(r[12]);

      if (isSkipRowByVesselNoAndName(vesselNoRaw, vesselName)) continue;
      const vesselNo = Number(String(vesselNoRaw).trim());

      out.push({
        cargo_type: "coal",
        year: Number(year),
        month: month,
        vessel_no: vesselNo,
        voyage_no: null,
        vessel_name: vesselName,
        brand: brand,
        bl_ton: blTon,
        started_at: startedAt,
        finished_at: finishedAt,
        duration_days: durationDays,
        adj_days: adjDays,
        net_days: netDays,
        unload_rate: unloadRate,
        shift_exchange: shiftExchange,
        note: note,
        issue_categories: window.classifyIssue ? window.classifyIssue(note || "") : ["기타"]
      });
    }
    return out;
  }

  function parseXlsFile(file, year) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = function (e) {
        try {
          const data = new Uint8Array(e.target.result);
          const workbook = XLSX.read(data, { type: "array", cellDates: false });
          const nickel = parseNickelSheet(workbook, year);
          const coal = parseCoalSheet(workbook, year);
          resolve({ nickel: nickel, coal: coal });
        } catch (err) {
          reject(err);
        }
      };
      reader.onerror = reject;
      reader.readAsArrayBuffer(file);
    });
  }

  window.parseNickelSheet = parseNickelSheet;
  window.parseCoalSheet = parseCoalSheet;
  window.parseXlsFile = parseXlsFile;
})();
