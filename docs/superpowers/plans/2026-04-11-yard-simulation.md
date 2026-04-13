# 야드 시뮬레이션 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `yard.html`을 전면 교체하여 자가야드/임차야드 두 개 야드의 반입·반출·재고·적치율을 날짜별로 시뮬레이션하는 페이지를 구현한다.

**Architecture:** 단일 HTML 파일(vanilla JS + CSS). `localStorage['berth7_v6']`에서 석탄 반입 데이터를 읽어(읽기 전용) start~end 기간 비율로 날짜별 반입량을 계산하고, 반출은 `localStorage['yard_sim_v1']`에 저장된 설정(고정값 또는 일별값)으로 처리한다. 기존 `yard.html` 전체를 새 코드로 교체한다.

**Tech Stack:** HTML5, CSS3, Vanilla JavaScript (ES6+), localStorage

---

## 파일 구조

| 파일 | 역할 |
|------|------|
| `yard.html` | 전체 구현 (교체) |

---

## Task 1: 페이지 뼈대 — HTML + CSS

**Files:**
- Modify: `yard.html` (전체 교체)

- [ ] **Step 1: yard.html을 아래 내용으로 교체**

```html
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>야드 시뮬레이션</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Malgun Gothic', sans-serif; background: #f3f4f6; color: #111827; min-height: 100vh; }

/* ── HEADER ── */
.app-header {
  background: #1a3a5c; color: #fff;
  padding: 12px 18px;
  display: flex; justify-content: space-between; align-items: center;
  box-shadow: 0 2px 8px rgba(0,0,0,0.25);
  flex-wrap: wrap; gap: 8px;
}
.header-left  { display: flex; gap: 10px; align-items: center; }
.header-right { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.app-header h1 { font-size: 17px; }
.header-summary { display: flex; gap: 18px; align-items: center; flex-wrap: wrap; }
.header-summary .hs { font-size: 12px; }
.header-summary .hs strong { font-size: 13px; }
.header-meta { font-size: 11px; color: #93c5fd; }

/* ── BUTTONS ── */
.btn { border: none; border-radius: 6px; padding: 7px 13px; font-size: 12px; font-weight: 700; cursor: pointer; transition: opacity .15s; font-family: inherit; }
.btn:hover { opacity: .85; }
.btn-blue  { background: #2563eb; color: #fff; }
.btn-gray  { background: #6b7280; color: #fff; }
.btn-red   { background: #ef4444; color: #fff; }

/* ── MAIN WRAPPER ── */
.main-wrap { padding: 14px 16px; }

/* ── TABLE CARD ── */
.card { background: #fff; border-radius: 10px; box-shadow: 0 2px 8px rgba(15,23,42,.08); border: 1px solid #e5e7eb; overflow: hidden; }
.scroll-x { overflow-x: auto; }

/* ── SIMULATION TABLE ── */
.sim-table { border-collapse: collapse; font-size: 12px; min-width: 960px; width: 100%; }
.sim-table th, .sim-table td {
  border: 1px solid #e5e7eb; padding: 6px 8px;
  text-align: right; white-space: nowrap;
}
.sim-table th { background: #f1f5f9; color: #334155; font-weight: 700; position: sticky; top: 0; z-index: 2; }
.sim-table td:first-child, .sim-table th:first-child { text-align: left; }

/* 그룹 헤더 */
.sim-table .gh-self  { background: #1e4a7a; color: #fff; text-align: center; }
.sim-table .gh-rent  { background: #14532d; color: #fff; text-align: center; }
.sim-table .gh-total { background: #312e81; color: #fff; text-align: center; }
.sim-table .gh-date  { background: #1a3a5c; color: #fff; }

/* 수동 편집 셀 */
.sim-table td.manual-edited { outline: 2px solid #3b82f6; outline-offset: -2px; }

/* ── MODAL ── */
.modal-overlay {
  display: none; position: fixed; inset: 0;
  background: rgba(0,0,0,.45); z-index: 1000;
  align-items: center; justify-content: center;
}
.modal-overlay.show { display: flex; }
.modal {
  background: #fff; border-radius: 10px; padding: 22px;
  width: 580px; max-width: 96vw; max-height: 92vh; overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0,0,0,.3);
}
.modal h2 { font-size: 15px; font-weight: 700; color: #1a3a5c; margin-bottom: 16px; }
.modal-footer { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }

/* ── SETTINGS MODAL ── */
.yard-block { border-radius: 8px; padding: 14px; margin-bottom: 14px; }
.yard-block.self { background: #eff6ff; border: 1px solid #bfdbfe; }
.yard-block.rent { background: #f0fdf4; border: 1px solid #bbf7d0; }
.yard-block.silo { background: #fafafa; border: 1px solid #e5e7eb; }
.yard-title { font-size: 13px; font-weight: 700; margin-bottom: 10px; }
.yard-title.self { color: #1e40af; }
.yard-title.rent { color: #166534; }
.meta-row { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; font-size: 12px; }
.meta-row input { width: 90px; text-align: right; padding: 4px 8px; border: 1px solid #d1d5db; border-radius: 4px; font-size: 12px; font-family: inherit; }

/* 탭 */
.tab-bar { display: flex; border-bottom: 2px solid #e5e7eb; margin-bottom: 10px; }
.tab-btn { padding: 6px 16px; font-size: 12px; font-weight: 600; color: #6b7280; border: none; background: none; cursor: pointer; font-family: inherit; border-bottom: 2px solid transparent; margin-bottom: -2px; }
.tab-btn.active { color: #1a3a5c; border-bottom-color: #1a3a5c; }
.tab-panel { display: none; }
.tab-panel.active { display: block; }

/* 고정 입력 그리드 */
.fixed-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 8px; font-size: 12px; }
.fixed-grid label { font-size: 11px; color: #6b7280; display: block; margin-bottom: 3px; }
.fixed-grid input { width: 100%; text-align: right; padding: 5px 8px; border: 1px solid #d1d5db; border-radius: 4px; font-size: 12px; font-family: inherit; }
.fixed-total { background: #f3f4f6; padding: 5px 8px; border-radius: 4px; font-weight: 700; text-align: right; color: #dc2626; font-size: 12px; }

/* 일별 입력 테이블 */
.daily-table-wrap { max-height: 260px; overflow-y: auto; }
.daily-table { border-collapse: collapse; font-size: 11px; width: 100%; }
.daily-table th, .daily-table td { border: 1px solid #e5e7eb; padding: 4px 7px; text-align: right; white-space: nowrap; }
.daily-table th { background: #f1f5f9; color: #334155; font-weight: 700; position: sticky; top: 0; }
.daily-table td:first-child, .daily-table th:first-child { text-align: left; }
.daily-table input { width: 64px; text-align: right; padding: 3px 5px; border: 1px solid #d1d5db; border-radius: 3px; font-size: 11px; font-family: inherit; }

/* ── OVERWRITE CONFIRM MODAL ── */
.confirm-msg { font-size: 13px; color: #374151; line-height: 1.7; }
</style>
</head>
<body>

<!-- ── HEADER ── -->
<header class="app-header">
  <div class="header-left">
    <a href="/" style="text-decoration:none;font-size:20px;line-height:1;" title="메인화면">🏠</a>
    <h1>야드 시뮬레이션</h1>
  </div>
  <div class="header-right">
    <div class="header-summary" id="headerSummary"></div>
    <span class="header-meta" id="headerMeta"></span>
    <button class="btn btn-blue" onclick="handleLoad()">반입 데이터 불러오기</button>
    <button class="btn btn-gray" onclick="openSettings()">상세 설정</button>
  </div>
</header>

<!-- ── MAIN TABLE ── -->
<div class="main-wrap">
  <div class="card">
    <div class="scroll-x">
      <table class="sim-table" id="simTable">
        <thead>
          <tr>
            <th class="gh-date" rowspan="2">날짜</th>
            <th class="gh-self" colspan="4">🏭 자가야드 (<span id="hSelfCapa"></span>t)</th>
            <th class="gh-rent" colspan="4">🏗️ 임차야드 (<span id="hRentCapa"></span>t)</th>
            <th class="gh-total" colspan="3">📊 전체</th>
          </tr>
          <tr>
            <th>반입(t)</th><th>반출(t)</th><th>재고(t)</th><th>적치율</th>
            <th>반입(t)</th><th>반출(t)</th><th>재고(t)</th><th>적치율</th>
            <th>반입(t)</th><th>반출(t)</th><th>총재고(t)</th>
          </tr>
        </thead>
        <tbody id="simBody"></tbody>
      </table>
    </div>
  </div>
</div>

<!-- ── SETTINGS MODAL ── -->
<div class="modal-overlay" id="settingsModal">
  <div class="modal">
    <h2>상세 설정</h2>

    <!-- 자가야드 -->
    <div class="yard-block self">
      <div class="yard-title self">🏭 자가야드</div>
      <div class="meta-row">
        <span>용량</span>
        <input id="sSelfCapa" type="number" value="248400">
        <span>t &nbsp;·&nbsp; 초기 재고</span>
        <input id="sSelfInit" type="number" value="0">
        <span>t</span>
      </div>
      <div class="tab-bar">
        <button class="tab-btn active" onclick="switchTab('self','fixed',this)">일 고정 입력</button>
        <button class="tab-btn" onclick="switchTab('self','daily',this)">일별 직접 입력</button>
      </div>
      <div class="tab-panel active" id="self-fixed">
        <div class="fixed-grid">
          <div><label>이적반출 (t/일)</label><input id="sSelfTransfer" type="number" value="1200" oninput="updateFixedTotal('self')"></div>
          <div><label>육송반출 (t/일)</label><input id="sSelfLand" type="number" value="1800" oninput="updateFixedTotal('self')"></div>
          <div><label>해송반출 (t/일)</label><input id="sSelfSea" type="number" value="1600" oninput="updateFixedTotal('self')"></div>
          <div><label>반출합 (t/일)</label><div class="fixed-total" id="sSelfTotal">4,600</div></div>
        </div>
      </div>
      <div class="tab-panel" id="self-daily">
        <div class="daily-table-wrap"><table class="daily-table"><thead><tr><th>날짜</th><th>이적(t)</th><th>육송(t)</th><th>해송(t)</th><th>반출합</th></tr></thead><tbody id="selfDailyBody"></tbody></table></div>
      </div>
    </div>

    <!-- 임차야드 -->
    <div class="yard-block rent">
      <div class="yard-title rent">🏗️ 임차야드</div>
      <div class="meta-row">
        <span>용량</span>
        <input id="sRentCapa" type="number" value="172800">
        <span>t &nbsp;·&nbsp; 초기 재고</span>
        <input id="sRentInit" type="number" value="0">
        <span>t</span>
      </div>
      <div class="tab-bar">
        <button class="tab-btn active" onclick="switchTab('rent','fixed',this)">일 고정 입력</button>
        <button class="tab-btn" onclick="switchTab('rent','daily',this)">일별 직접 입력</button>
      </div>
      <div class="tab-panel active" id="rent-fixed">
        <div class="fixed-grid">
          <div><label>이적반출 (t/일)</label><input id="sRentTransfer" type="number" value="0" oninput="updateFixedTotal('rent')"></div>
          <div><label>육송반출 (t/일)</label><input id="sRentLand" type="number" value="0" oninput="updateFixedTotal('rent')"></div>
          <div><label>해송반출 (t/일)</label><input id="sRentSea" type="number" value="0" oninput="updateFixedTotal('rent')"></div>
          <div><label>반출합 (t/일)</label><div class="fixed-total" id="sRentTotal">0</div></div>
        </div>
      </div>
      <div class="tab-panel" id="rent-daily">
        <div class="daily-table-wrap"><table class="daily-table"><thead><tr><th>날짜</th><th>이적(t)</th><th>육송(t)</th><th>해송(t)</th><th>반출합</th></tr></thead><tbody id="rentDailyBody"></tbody></table></div>
      </div>
    </div>

    <!-- Silo -->
    <div class="yard-block silo">
      <div class="yard-title" style="color:#374151;">🗄️ Silo (참고용 — 시뮬레이션 제외)</div>
      <div class="meta-row">
        <span style="font-size:12px;">현재 재고 (참고)</span>
        <input id="sSilo" type="number" value="0">
        <span style="font-size:12px;">t</span>
      </div>
    </div>

    <div class="modal-footer">
      <button class="btn btn-gray" onclick="closeSettings()">취소</button>
      <button class="btn btn-blue" onclick="saveSettings()">저장 · 재계산</button>
    </div>
  </div>
</div>

<!-- ── OVERWRITE CONFIRM MODAL ── -->
<div class="modal-overlay" id="confirmModal">
  <div class="modal" style="width:400px;">
    <h2>반입 데이터 불러오기</h2>
    <p class="confirm-msg">수동으로 편집한 반입 셀이 있습니다.<br>새 데이터를 불러오면 <strong>자동 반입 값이 덮어써집니다.</strong><br>수동 편집 값은 유지됩니다. 계속하시겠습니까?</p>
    <div class="modal-footer">
      <button class="btn btn-gray" onclick="closeConfirm()">취소</button>
      <button class="btn btn-blue" onclick="confirmLoad()">불러오기</button>
    </div>
  </div>
</div>

<script>
// ─────────────────────────────────────────
//  CONSTANTS
// ─────────────────────────────────────────
const BERTH_KEY    = 'berth7_v6';
const SIM_KEY      = 'yard_sim_v1';
const SIM_DAYS     = 60;
const DEFAULT_BL   = 60000;

const DEFAULT_SETTINGS = {
  selfYard: {
    capa: 248400, initStock: 0, outMode: 'fixed',
    outFixed: { transfer: 1200, land: 1800, sea: 1600 },
    outDaily: {}
  },
  rentYard: {
    capa: 172800, initStock: 0, outMode: 'fixed',
    outFixed: { transfer: 0, land: 0, sea: 0 },
    outDaily: {}
  },
  silo: { currentStock: 0 },
  autoInbound: {},   // { 'YYYY-MM-DD': { self: ton, rent: ton } }  — from berth
  manualInbound: {}, // { 'YYYY-MM-DD': { self: ton, rent: ton } }  — user edits
  lastFetched: null
};
</script>
</body>
</html>
```

- [ ] **Step 2: 브라우저에서 `/yard` 접속, 헤더와 빈 테이블 틀이 보이는지 확인**

---

## Task 2: 데이터 레이어 — localStorage 읽기/쓰기

**Files:**
- Modify: `yard.html` — `<script>` 블록에 추가

- [ ] **Step 1: DEFAULT_SETTINGS 선언 아래에 설정 load/save 함수 추가**

```js
// ─────────────────────────────────────────
//  SETTINGS PERSISTENCE
// ─────────────────────────────────────────
function loadSimSettings() {
  try {
    const raw = localStorage.getItem(SIM_KEY);
    if (!raw) return JSON.parse(JSON.stringify(DEFAULT_SETTINGS));
    const parsed = JSON.parse(raw);
    // deep-merge: 누락된 키는 기본값으로 채움
    const d = DEFAULT_SETTINGS;
    return {
      selfYard:      { ...d.selfYard,      ...parsed.selfYard,      outFixed: { ...d.selfYard.outFixed, ...(parsed.selfYard?.outFixed || {}) } },
      rentYard:      { ...d.rentYard,      ...parsed.rentYard,      outFixed: { ...d.rentYard.outFixed, ...(parsed.rentYard?.outFixed || {}) } },
      silo:          { ...d.silo,          ...parsed.silo },
      autoInbound:   parsed.autoInbound   || {},
      manualInbound: parsed.manualInbound || {},
      lastFetched:   parsed.lastFetched   || null,
    };
  } catch { return JSON.parse(JSON.stringify(DEFAULT_SETTINGS)); }
}

function saveSimSettings(s) {
  localStorage.setItem(SIM_KEY, JSON.stringify(s));
}

// 앱 전역 상태
let SIM = loadSimSettings();
```

- [ ] **Step 2: 브라우저 콘솔에서 `SIM` 입력 후 DEFAULT_SETTINGS 구조대로 출력되는지 확인**

---

## Task 3: 반입 계산 — berth7_v6 파싱

**Files:**
- Modify: `yard.html` — `<script>` 블록에 추가

- [ ] **Step 1: 날짜 헬퍼 + 반입 계산 함수 추가**

```js
// ─────────────────────────────────────────
//  DATE HELPERS
// ─────────────────────────────────────────
const pad = n => String(n).padStart(2, '0');
function dayKey(d) { return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`; }
function toDateOnly(dt) { return new Date(dt.getFullYear(), dt.getMonth(), dt.getDate()); }
function parseDT(v) { if (!v) return null; const d = new Date(v); return isNaN(d) ? null : d; }
function fmt(n) { return Math.round(n).toLocaleString('ko-KR'); }
function fmtRate(r) { return r.toFixed(1) + '%'; }

/** simStart(오늘 00:00)와 simEnd(+60일 00:00)을 반환 */
function simRange() {
  const today = toDateOnly(new Date());
  const end   = new Date(today.getFullYear(), today.getMonth(), today.getDate() + SIM_DAYS);
  return { start: today, end };
}

// ─────────────────────────────────────────
//  INBOUND FROM berth7_v6 (읽기 전용)
// ─────────────────────────────────────────
/**
 * berth7_v6에서 석탄 반입량을 날짜별로 계산한다.
 * 모든 반입은 자가야드(self)로 처리. rent는 항상 0.
 * @returns {Object} { 'YYYY-MM-DD': { self: number, rent: number } }
 */
function calcAutoInbound() {
  const raw = JSON.parse(localStorage.getItem(BERTH_KEY) || '[]');
  const { start, end } = simRange();
  const result = {};

  raw
    .filter(it => it && it.type === 'ship' && (it.cargoType || '').trim() === '석탄')
    .forEach(it => {
      const s0 = parseDT(it.start);
      const e0 = parseDT(it.end);
      if (!s0 || !e0) return;

      const totalTon = Number(it.bl) > 0 ? Number(it.bl) : DEFAULT_BL;
      const s = s0 < start ? start : s0;
      const e = e0 > end   ? end   : e0;
      const totalMs = e0 - s0;  // 전체 하역 기간
      if (totalMs <= 0 || e <= s) return;

      for (let d = toDateOnly(s); d < e; d = new Date(d.getFullYear(), d.getMonth(), d.getDate() + 1)) {
        if (d < start || d >= end) continue;
        const dayEnd      = new Date(d.getFullYear(), d.getMonth(), d.getDate() + 1);
        const overlapMs   = Math.min(e0, dayEnd) - Math.max(s0, d);
        if (overlapMs <= 0) continue;
        const ton = totalTon * (overlapMs / totalMs);
        const k   = dayKey(d);
        if (!result[k]) result[k] = { self: 0, rent: 0 };
        result[k].self += ton;
      }
    });

  return result;
}
```

- [ ] **Step 2: 브라우저 콘솔에서 `calcAutoInbound()` 실행**
  - `berth7_v6`에 석탄 데이터가 있으면 날짜별 객체 반환
  - 없으면 `{}` 반환 (정상)

---

## Task 4: 일별 반출량 계산 함수

**Files:**
- Modify: `yard.html` — `<script>` 블록에 추가

- [ ] **Step 1: 반출량 계산 함수 추가**

```js
// ─────────────────────────────────────────
//  OUTBOUND HELPERS
// ─────────────────────────────────────────
/**
 * 특정 날짜의 야드 반출량 합계를 반환한다.
 * @param {Object} yardSetting  SIM.selfYard 또는 SIM.rentYard
 * @param {string} dateKey      'YYYY-MM-DD'
 * @returns {number}
 */
function getOutboundForDay(yardSetting, dateKey) {
  if (yardSetting.outMode === 'daily') {
    const d = yardSetting.outDaily[dateKey] || {};
    return (Number(d.transfer) || 0) + (Number(d.land) || 0) + (Number(d.sea) || 0);
  }
  const f = yardSetting.outFixed;
  return (Number(f.transfer) || 0) + (Number(f.land) || 0) + (Number(f.sea) || 0);
}
```

- [ ] **Step 2: 콘솔에서 `getOutboundForDay(SIM.selfYard, '2026-04-11')` 호출, 기본값 4600 반환 확인**

---

## Task 5: 시뮬레이션 계산 엔진

**Files:**
- Modify: `yard.html` — `<script>` 블록에 추가

- [ ] **Step 1: 계산 엔진 함수 추가**

```js
// ─────────────────────────────────────────
//  SIMULATION ENGINE
// ─────────────────────────────────────────
/**
 * 60일치 시뮬레이션 행 배열을 계산한다.
 * @returns {Array<{
 *   date: string,
 *   selfIn: number, selfOut: number, selfStock: number,
 *   rentIn: number, rentOut: number, rentStock: number,
 *   totalIn: number, totalOut: number, totalStock: number
 * }>}
 */
function runCalc() {
  const { start, end } = simRange();
  const rows = [];
  let selfStock = Number(SIM.selfYard.initStock) || 0;
  let rentStock = Number(SIM.rentYard.initStock) || 0;

  for (let d = new Date(start); d < end; d = new Date(d.getFullYear(), d.getMonth(), d.getDate() + 1)) {
    const k = dayKey(d);

    // 반입: auto + manual
    const autoSelf = (SIM.autoInbound[k]   || {}).self || 0;
    const autoRent = (SIM.autoInbound[k]   || {}).rent || 0;
    const manSelf  = (SIM.manualInbound[k] || {}).self;
    const manRent  = (SIM.manualInbound[k] || {}).rent;

    // manual이 null/undefined면 auto 사용, 숫자면 override
    const selfIn = manSelf != null ? Number(manSelf) : autoSelf;
    const rentIn = manRent != null ? Number(manRent) : autoRent;

    const selfOut = getOutboundForDay(SIM.selfYard, k);
    const rentOut = getOutboundForDay(SIM.rentYard, k);

    selfStock = Math.max(0, selfStock + selfIn - selfOut);
    rentStock = Math.max(0, rentStock + rentIn - rentOut);

    rows.push({
      date: k,
      selfIn, selfOut, selfStock,
      rentIn, rentOut, rentStock,
      totalIn:    selfIn + rentIn,
      totalOut:   selfOut + rentOut,
      totalStock: selfStock + rentStock,
    });
  }
  return rows;
}
```

- [ ] **Step 2: 콘솔에서 `runCalc()` 실행, 60개 행 배열이 반환되는지 확인**
  - 각 행에 `date`, `selfStock`, `rentStock` 등 키가 있어야 함

---

## Task 6: 테이블 렌더링

**Files:**
- Modify: `yard.html` — `<script>` 블록에 추가

- [ ] **Step 1: 적치율 색상 함수 + 테이블 렌더 함수 추가**

```js
// ─────────────────────────────────────────
//  RENDERING
// ─────────────────────────────────────────
/** 적치율(0~100+)에 따른 글자색 반환 */
function rateColor(rate) {
  if (rate >= 100) return '#dc2626';
  if (rate >= 90)  return '#ea580c';
  if (rate >= 80)  return '#d97706';
  return '#1f2937';
}

function renderTable(rows) {
  const tbody = document.getElementById('simBody');
  tbody.innerHTML = '';

  rows.forEach(row => {
    const selfCapa = Number(SIM.selfYard.capa) || 1;
    const rentCapa = Number(SIM.rentYard.capa) || 1;
    const selfRate = (row.selfStock / selfCapa) * 100;
    const rentRate = (row.rentStock / rentCapa) * 100;

    // 수동 편집 여부 확인
    const manK = SIM.manualInbound[row.date] || {};
    const selfManual = manK.self != null;
    const rentManual = manK.rent != null;

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${row.date}</td>
      <td class="${selfManual ? 'manual-edited' : ''}" data-yard="self" data-date="${row.date}">${fmt(row.selfIn)}</td>
      <td>${fmt(row.selfOut)}</td>
      <td><strong>${fmt(row.selfStock)}</strong></td>
      <td style="font-weight:700;color:${rateColor(selfRate)}">${fmtRate(selfRate)}</td>
      <td class="${rentManual ? 'manual-edited' : ''}" data-yard="rent" data-date="${row.date}">${fmt(row.rentIn)}</td>
      <td>${fmt(row.rentOut)}</td>
      <td><strong>${fmt(row.rentStock)}</strong></td>
      <td style="font-weight:700;color:${rateColor(rentRate)}">${fmtRate(rentRate)}</td>
      <td>${fmt(row.totalIn)}</td>
      <td>${fmt(row.totalOut)}</td>
      <td><strong>${fmt(row.totalStock)}</strong></td>
    `;
    tbody.appendChild(tr);
  });
}

function renderHeader() {
  document.getElementById('hSelfCapa').textContent = fmt(SIM.selfYard.capa);
  document.getElementById('hRentCapa').textContent = fmt(SIM.rentYard.capa);
}

function renderHeaderSummary(rows) {
  if (!rows.length) return;
  const last = rows[0]; // 오늘 행
  const selfRate = (last.selfStock / (SIM.selfYard.capa || 1)) * 100;
  const rentRate = (last.rentStock / (SIM.rentYard.capa || 1)) * 100;
  document.getElementById('headerSummary').innerHTML = `
    <span class="hs">자가야드 <strong>${fmt(last.selfStock)}</strong>t
      <span style="color:${rateColor(selfRate)};font-weight:700;">${fmtRate(selfRate)}</span></span>
    <span class="hs">임차야드 <strong>${fmt(last.rentStock)}</strong>t
      <span style="color:${rateColor(rentRate)};font-weight:700;">${fmtRate(rentRate)}</span></span>
    <span class="hs">총재고 <strong>${fmt(last.totalStock)}</strong>t</span>
  `;
  if (SIM.lastFetched) {
    const d = new Date(SIM.lastFetched);
    document.getElementById('headerMeta').textContent =
      `마지막 업데이트: ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }
}

/** 전체 재렌더 진입점 */
function refresh() {
  const rows = runCalc();
  renderHeader();
  renderTable(rows);
  renderHeaderSummary(rows);
}
```

- [ ] **Step 2: `</script>` 직전에 초기화 코드 추가**

```js
// ─────────────────────────────────────────
//  INIT
// ─────────────────────────────────────────
refresh();
```

- [ ] **Step 3: `/yard` 새로고침 — 60일치 테이블이 표시되고 적치율이 검정으로 렌더되는지 확인**

---

## Task 7: 상세 설정 모달

**Files:**
- Modify: `yard.html` — `<script>` 블록에 추가

- [ ] **Step 1: 탭 전환 + 일별 반출 테이블 생성 함수 추가**

```js
// ─────────────────────────────────────────
//  SETTINGS MODAL
// ─────────────────────────────────────────
function switchTab(yard, mode, btn) {
  const prefix = yard;
  document.querySelectorAll(`#${prefix}-fixed, #${prefix}-daily`).forEach(el => el.classList.remove('active'));
  document.getElementById(`${prefix}-${mode}`).classList.add('active');
  btn.closest('.tab-bar').querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
}

function updateFixedTotal(yard) {
  const t = Number(document.getElementById(`s${cap(yard)}Transfer`).value) || 0;
  const l = Number(document.getElementById(`s${cap(yard)}Land`).value)     || 0;
  const s = Number(document.getElementById(`s${cap(yard)}Sea`).value)      || 0;
  document.getElementById(`s${cap(yard)}Total`).textContent = fmt(t + l + s);
}
function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

function buildDailyBody(yardKey, tbodyId) {
  const tbody = document.getElementById(tbodyId);
  tbody.innerHTML = '';
  const { start, end } = simRange();
  const yardSetting = SIM[yardKey + 'Yard'];
  for (let d = new Date(start); d < end; d = new Date(d.getFullYear(), d.getMonth(), d.getDate() + 1)) {
    const k  = dayKey(d);
    const od = yardSetting.outDaily[k] || {};
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${k}</td>
      <td><input type="number" value="${od.transfer || 0}" data-dk="${k}" data-field="transfer" data-yard="${yardKey}" oninput="onDailyInput(this)"></td>
      <td><input type="number" value="${od.land     || 0}" data-dk="${k}" data-field="land"     data-yard="${yardKey}" oninput="onDailyInput(this)"></td>
      <td><input type="number" value="${od.sea      || 0}" data-dk="${k}" data-field="sea"      data-yard="${yardKey}" oninput="onDailyInput(this)"></td>
      <td class="daily-total-${k}-${yardKey}">${fmt((od.transfer||0)+(od.land||0)+(od.sea||0))}</td>
    `;
    tbody.appendChild(tr);
  }
}

function onDailyInput(input) {
  const { dk, field, yard } = input.dataset;
  const yardKey = yard + 'Yard';
  if (!SIM[yardKey].outDaily[dk]) SIM[yardKey].outDaily[dk] = {};
  SIM[yardKey].outDaily[dk][field] = Number(input.value) || 0;
  const d = SIM[yardKey].outDaily[dk];
  const total = (d.transfer||0) + (d.land||0) + (d.sea||0);
  const cell = input.closest('tr').lastElementChild;
  cell.textContent = fmt(total);
}

function openSettings() {
  const s = SIM;
  document.getElementById('sSelfCapa').value      = s.selfYard.capa;
  document.getElementById('sSelfInit').value      = s.selfYard.initStock;
  document.getElementById('sSelfTransfer').value  = s.selfYard.outFixed.transfer;
  document.getElementById('sSelfLand').value      = s.selfYard.outFixed.land;
  document.getElementById('sSelfSea').value       = s.selfYard.outFixed.sea;
  updateFixedTotal('self');

  document.getElementById('sRentCapa').value      = s.rentYard.capa;
  document.getElementById('sRentInit').value      = s.rentYard.initStock;
  document.getElementById('sRentTransfer').value  = s.rentYard.outFixed.transfer;
  document.getElementById('sRentLand').value      = s.rentYard.outFixed.land;
  document.getElementById('sRentSea').value       = s.rentYard.outFixed.sea;
  updateFixedTotal('rent');

  document.getElementById('sSilo').value = s.silo.currentStock;

  // 일별 탭 빌드 (활성 모드 탭 선택 반영)
  buildDailyBody('self', 'selfDailyBody');
  buildDailyBody('rent', 'rentDailyBody');

  // outMode에 따라 탭 활성화
  ['self','rent'].forEach(yard => {
    const mode = SIM[yard + 'Yard'].outMode || 'fixed';
    const bar  = document.getElementById(`${yard}-fixed`).closest('.yard-block').querySelector('.tab-bar');
    bar.querySelectorAll('.tab-btn').forEach(btn => {
      const isFixed = btn.textContent.includes('고정');
      btn.classList.toggle('active', (mode === 'fixed') === isFixed);
    });
    document.getElementById(`${yard}-fixed`).classList.toggle('active', mode === 'fixed');
    document.getElementById(`${yard}-daily`).classList.toggle('active', mode === 'daily');
  });

  document.getElementById('settingsModal').classList.add('show');
}

function closeSettings() {
  document.getElementById('settingsModal').classList.remove('show');
}

function saveSettings() {
  SIM.selfYard.capa       = Number(document.getElementById('sSelfCapa').value)     || 248400;
  SIM.selfYard.initStock  = Number(document.getElementById('sSelfInit').value)     || 0;
  SIM.selfYard.outFixed   = {
    transfer: Number(document.getElementById('sSelfTransfer').value) || 0,
    land:     Number(document.getElementById('sSelfLand').value)     || 0,
    sea:      Number(document.getElementById('sSelfSea').value)      || 0,
  };
  // 활성 탭 = 현재 모드
  SIM.selfYard.outMode = document.getElementById('self-daily').classList.contains('active') ? 'daily' : 'fixed';

  SIM.rentYard.capa       = Number(document.getElementById('sRentCapa').value)     || 172800;
  SIM.rentYard.initStock  = Number(document.getElementById('sRentInit').value)     || 0;
  SIM.rentYard.outFixed   = {
    transfer: Number(document.getElementById('sRentTransfer').value) || 0,
    land:     Number(document.getElementById('sRentLand').value)     || 0,
    sea:      Number(document.getElementById('sRentSea').value)      || 0,
  };
  SIM.rentYard.outMode = document.getElementById('rent-daily').classList.contains('active') ? 'daily' : 'fixed';

  SIM.silo.currentStock = Number(document.getElementById('sSilo').value) || 0;

  saveSimSettings(SIM);
  closeSettings();
  refresh();
}
```

- [ ] **Step 2: `/yard` 새로고침 → "상세 설정" 클릭 → 모달 열리고 탭 전환되는지 확인**
- [ ] **Step 3: 자가야드 고정 반출값 변경 후 "저장·재계산" → 테이블 반출(t) 열이 변경되는지 확인**

---

## Task 8: 반입 데이터 불러오기 버튼

**Files:**
- Modify: `yard.html` — `<script>` 블록에 추가

- [ ] **Step 1: 불러오기 + 확인 모달 함수 추가**

```js
// ─────────────────────────────────────────
//  LOAD FROM berth7_v6
// ─────────────────────────────────────────
function handleLoad() {
  // 수동 편집된 반입 값이 있으면 확인 모달 표시
  const hasManual = Object.keys(SIM.manualInbound).length > 0;
  if (hasManual) {
    document.getElementById('confirmModal').classList.add('show');
  } else {
    doLoad();
  }
}

function closeConfirm() {
  document.getElementById('confirmModal').classList.remove('show');
}

function confirmLoad() {
  closeConfirm();
  doLoad();
}

function doLoad() {
  SIM.autoInbound  = calcAutoInbound();
  SIM.lastFetched  = new Date().toISOString();
  saveSimSettings(SIM);
  refresh();
}
```

- [ ] **Step 2: `/yard` 새로고침 → "반입 데이터 불러오기" 클릭**
  - `berth7_v6`에 석탄 데이터 있으면: 반입(t) 열에 값이 채워짐
  - 없으면: 반입(t) 열이 모두 0 (정상)
- [ ] **Step 3: 반입 불러온 후 셀 하나 수동 편집(Task 9 완료 후 재확인) → 다시 불러오기 → 확인 모달 표시 확인**

---

## Task 9: 셀 인라인 편집

**Files:**
- Modify: `yard.html` — `<script>` 블록에 추가

- [ ] **Step 1: 반입 셀 클릭 핸들러 추가**

```js
// ─────────────────────────────────────────
//  INLINE CELL EDITING (반입 셀)
// ─────────────────────────────────────────
document.getElementById('simBody').addEventListener('click', e => {
  const td = e.target.closest('td[data-yard]');
  if (!td || td.querySelector('input')) return; // 이미 편집 중

  const yard = td.dataset.yard;   // 'self' | 'rent'
  const date = td.dataset.date;   // 'YYYY-MM-DD'
  const cur  = (SIM.manualInbound[date] || {})[yard];

  // auto 값 계산
  const autoVal = (SIM.autoInbound[date] || {})[yard] || 0;
  const val = cur != null ? cur : autoVal;

  td.innerHTML = '';
  const input = document.createElement('input');
  input.type  = 'number';
  input.value = Math.round(val);
  input.style.cssText = 'width:80px;text-align:right;padding:3px 5px;border:1px solid #3b82f6;border-radius:3px;font-size:12px;font-family:inherit;';
  td.appendChild(input);
  input.focus();
  input.select();

  function commit() {
    const newVal = Number(input.value);
    if (!SIM.manualInbound[date]) SIM.manualInbound[date] = {};
    SIM.manualInbound[date][yard] = newVal;
    saveSimSettings(SIM);
    refresh(); // 테이블 전체 재계산 후 파란 테두리 자동 적용
  }

  input.addEventListener('blur',  commit);
  input.addEventListener('keydown', ev => {
    if (ev.key === 'Enter')  { ev.preventDefault(); commit(); }
    if (ev.key === 'Escape') {
      saveSimSettings(SIM);
      refresh(); // 원래 값으로 복구
    }
  });
});
```

- [ ] **Step 2: `/yard` 새로고침 → 반입(t) 셀 클릭 → 숫자 입력 후 Enter**
  - 파란 테두리(`.manual-edited`)가 해당 셀에 표시되는지 확인
  - 재고, 적치율이 새 값으로 재계산되는지 확인
- [ ] **Step 3: Escape 입력 시 편집이 취소되고 원래 값이 복구되는지 확인**

---

## Task 10: 오버레이 닫기 + 최종 마무리

**Files:**
- Modify: `yard.html` — `<script>` 블록에 추가

- [ ] **Step 1: 모달 오버레이 클릭으로 닫기 추가**

```js
// ─────────────────────────────────────────
//  MODAL CLOSE ON OVERLAY CLICK
// ─────────────────────────────────────────
document.getElementById('settingsModal').addEventListener('click', e => {
  if (e.target.id === 'settingsModal') closeSettings();
});
document.getElementById('confirmModal').addEventListener('click', e => {
  if (e.target.id === 'confirmModal') closeConfirm();
});
```

- [ ] **Step 2: `yard.html` 헤더 h1 텍스트에서 "(프로토타입)" 제거**

  [yard.html:133](yard.html#L133) 의 `야드 시뮬레이션 (프로토타입)` → `야드 시뮬레이션`

  *(이 변경은 Task 1에서 이미 새 skeleton을 쓰면 자동 반영됨)*

- [ ] **Step 3: 전체 시나리오 최종 확인**
  1. `/yard` 접속 → 60일치 빈 테이블 렌더됨
  2. "상세 설정" → 자가야드 초기 재고 100,000 입력 → 저장 → 재고 반영됨
  3. "반입 데이터 불러오기" → 석탄 반입 자동 채워짐, 헤더 업데이트 시간 표시됨
  4. 반입 셀 클릭 → 수동 편집 → 파란 테두리 + 재계산 확인
  5. 다시 "반입 데이터 불러오기" → 확인 모달 → 취소 시 값 유지, 불러오기 시 auto 값 갱신(수동값은 유지)
  6. "상세 설정" → 일별 직접 입력 탭 → 값 입력 → 저장 → 반출(t) 열 반영 확인
  7. 페이지 새로고침 → 모든 설정과 수동 편집값이 localStorage에서 복원됨

- [ ] **Step 4: git commit**

```bash
git add yard.html
git commit -m "feat: 야드 시뮬레이션 — 자가/임차 이중 야드, 반입 자동연동, 상세설정 모달"
```

---

## 자체 검토 — 스펙 대비 커버리지

| 스펙 요구사항 | 구현 Task |
|---|---|
| berth7_v6 석탄 반입 자동 fetch | Task 3, 8 |
| start~end 비율 분산 반입 | Task 3 |
| 기본 자가야드 반입, 임차야드 수동 설정 | Task 9 (셀 편집) |
| 니켈 제외 | Task 3 필터 |
| 자가야드/임차야드 테이블 칼럼 구조 | Task 1, 6 |
| 반입/반출/재고/적치율 칼럼 | Task 6 |
| 전체 반입/반출/총재고 칼럼 | Task 6 |
| 적치율 색상 4단계 | Task 6 |
| 셀 배경 흰색 | Task 1 CSS |
| 수동 편집 셀 파란 테두리 | Task 6, 9 |
| 반입 데이터 불러오기 버튼 | Task 8 |
| 덮어쓰기 확인 모달 | Task 8 |
| 상세 설정 모달 (용량/초기재고/반출) | Task 7 |
| 고정 t/일 + 일별 입력 탭 | Task 7 |
| Silo 참고 입력 (시뮬레이션 제외) | Task 7 |
| yard_sim_v1 localStorage 저장 | Task 2, 7 |
| 기본값 자가 248,400t / 임차 172,800t | Task 1 (DEFAULT_SETTINGS) |
| 60일 시뮬레이션 기간 | Task 5 |
| 페이지 새로고침 시 설정 복원 | Task 2 |
