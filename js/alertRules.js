(() => {
  /**
   * @typedef {Object} AlertRule
   * @property {string} id
   * @property {'danger'|'warning'|'info'|'success'} level
   * @property {(simData: any) => boolean} condition
   * @property {(simData: any) => string} message
   */

  /** @type {AlertRule[]} */
  const toRequiredAreaM = (excessTon) => {
    const raw = Number(excessTon || 0) / 200;
    const rounded10 = Math.round(raw / 10) * 10;
    return Math.max(0, rounded10);
  };
  const toKton = (ton) => `${Math.round(Number(ton || 0) / 1000).toLocaleString("ko-KR")}천톤`;
  const pad2 = (n) => String(n).padStart(2, "0");
  const fmtMDorYYMD = (d) => {
    if (!d || !/^\d{4}-\d{2}-\d{2}$/.test(d)) return "-";
    const [yyyy, mm, dd] = d.split("-");
    return `${mm}/${dd}`;
  };
  const fmtRange = (startDate, endDate) => {
    if (!startDate || !endDate) return "-";
    const [sy] = startDate.split("-");
    const [ey] = endDate.split("-");
    if (sy === ey) return `${fmtMDorYYMD(startDate)} ~ ${fmtMDorYYMD(endDate)}`;
    const toYYMD = (d) => {
      const [yyyy, mm, dd] = d.split("-");
      return `${pad2(Number(yyyy) % 100)}/${mm}/${dd}`;
    };
    return `${toYYMD(startDate)} ~ ${toYYMD(endDate)}`;
  };

  const rules = [
    {
      id: "import-over-amount",
      level: "warning",
      condition: (simData) => !!simData?.importOver?.has,
      message: (simData) => {
        const excessTon = Number(simData?.importOver?.maxExcessTon || simData?.importOver?.startExcessTon || 0);
        return `반입야드 ${toKton(excessTon)} 초과`;
      },
    },
    {
      id: "self-over-transfer-plan",
      level: "warning",
      condition: (simData) => !!simData?.importOver?.has,
      message: (simData) => {
        const moveTon = Number(simData?.importOver?.maxExcessTon || simData?.importOver?.startExcessTon || 0);
        const overallHasRoom = !simData?.overallOver?.has;
        if (overallHasRoom) {
          return `자가야드 ${toKton(moveTon)} 임차야드 이적 필요`;
        }
        const excessTon = Number(simData?.overallOver?.maxExcessTon || simData?.overallOver?.startExcessTon || 0);
        const area = toRequiredAreaM(excessTon);
        const period = fmtRange(simData?.overallOver?.startDate, simData?.overallOver?.endDate);
        return `자가야드 ${toKton(moveTon)} 이적 필요, ${period} 추가 야드 ${area}m 임차 필요`;
      },
    },
    {
      id: "overall-over-limit",
      level: "danger",
      condition: (simData) => !!simData?.overallOver?.has,
      message: (simData) => {
        const excessTon = Number(simData?.overallOver?.maxExcessTon || simData?.overallOver?.startExcessTon || 0);
        const area = toRequiredAreaM(excessTon);
        const period = fmtRange(simData?.overallOver?.startDate, simData?.overallOver?.endDate);
        return `${period} 추가 야드 ${area}m 임차 필요 (전체야드 ${toKton(excessTon)} 초과)`;
      },
    },
  ];

  window.yardAlertRules = rules;
})();
