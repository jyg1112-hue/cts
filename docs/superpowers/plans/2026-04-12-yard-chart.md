# 야드 총재고 추이 차트 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `yard.html`에 토글 버튼으로 펼치고 접을 수 있는 총재고 추이 선 그래프를 추가한다.

**Architecture:** `yard.html` 단일 파일에 인라인으로 Chart.js CDN, 차트 HTML/CSS, JS 함수 3개(`toggleChart`, `initChart`, `updateChart`)를 추가하고 기존 `refresh()`가 차트 열림 상태일 때 `updateChart`를 호출하도록 수정한다.

**Tech Stack:** Chart.js 4.4.3 (CDN), 순수 HTML/CSS/JS

---

## 파일 구조

- **수정:** `yard.html` — Chart.js CDN 추가, 차트 CSS 추가, 차트 HTML 추가, 차트 JS 추가, `refresh()` 수정

---

### Task 1: Chart.js CDN + 차트 CSS + 차트 HTML 뼈대 추가

**Files:**
- Modify: `yard.html`

- [ ] **Step 1: `<head>` 끝 `</style>` 바로 앞에 차트 CSS 추가**

`yard.html`의 `</style>` (line 108) 바로 앞에 다음을 삽입:

```css
/* ── CHART ── */
#chartWrap {
  margin: 12px 18px 0;
}
#chartWrap .card {
  padding: 16px 18px 12px;
}
#chartWrap canvas {
  max-height: 260px;
}
```

- [ ] **Step 2: `<head>` 안에 Chart.js CDN 추가**

`</style>` 바로 다음 줄(line 109)에 삽입:

```html
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
```

- [ ] **Step 3: 헤더 툴바에 "차트 보기" 토글 버튼 추가**

`yard.html`의 line 122 (`<button class="btn btn-gray" onclick="openSettings()">상세 설정</button>`) 바로 앞에 삽입:

```html
<button class="btn btn-gray" id="btnChart" onclick="toggleChart()">📈 차트 보기</button>
```

- [ ] **Step 4: 차트 컨테이너 HTML 추가**

`yard.html`의 line 127 (`<!-- ── MAIN TABLE ── -->`) 바로 앞에 삽입:

```html
<!-- ── CHART ── -->
<div id="chartWrap" hidden>
  <div class="card">
    <canvas id="stockChart"></canvas>
  </div>
</div>
```

- [ ] **Step 5: 브라우저에서 페이지 열어 구조 확인**

`yard.html`을 브라우저로 직접 열거나 백엔드를 통해 열어서:
- 헤더에 "📈 차트 보기" 버튼이 보이는지 확인
- 버튼 클릭해도 아직 아무 동작 없음 (JS 미구현) — 정상

- [ ] **Step 6: 커밋**

```bash
git add yard.html
git commit -m "feat: 차트 HTML 뼈대 + CSS + Chart.js CDN 추가"
```

---

### Task 2: 차트 JS 함수 구현 + refresh() 수정

**Files:**
- Modify: `yard.html`

**배경:**
- `refresh()` 함수는 `yard.html` line 471~476에 있음:
  ```js
  function refresh() {
    const rows = runCalc();
    renderHeader();
    renderTable(rows);
    renderHeaderSummary(rows);
  }
  ```
- `simRange()` 함수는 오늘부터 60일치 `{ start: Date, end: Date }` 반환
- `dayKey(d)` 함수는 Date → `'YYYY-MM-DD'` 문자열 반환
- `SIM_DAYS = 60` 상수 존재

- [ ] **Step 1: `refresh()` 함수 바로 위에 차트 JS 추가**

`yard.html`에서 `// ─── RENDERING ───` 섹션 아래, `// ─── SETTINGS MODAL ───` 섹션 위 (현재 line 477~480 사이)에 다음 코드 블록 삽입:

```js
// ─────────────────────────────────────────
//  CHART
// ─────────────────────────────────────────
let stockChart = null;

function toggleChart() {
  const wrap = document.getElementById('chartWrap');
  const btn  = document.getElementById('btnChart');
  const hidden = wrap.hidden;
  wrap.hidden = !hidden;
  btn.textContent = hidden ? '📈 차트 닫기' : '📈 차트 보기';
  if (hidden) {
    const rows = runCalc();
    if (!stockChart) {
      initChart(rows);
    } else {
      updateChart(rows);
    }
  }
}

function initChart(rows) {
  const labels = rows.map(r => {
    const parts = r.date.split('-');
    return `${Number(parts[1])}/${Number(parts[2])}`;
  });
  const data = rows.map(r => r.totalStock);

  stockChart = new Chart(document.getElementById('stockChart'), {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: '총재고(t)',
        data,
        borderColor: '#2563eb',
        backgroundColor: 'rgba(37,99,235,0.08)',
        fill: true,
        tension: 0.3,
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 4,
      }]
    },
    options: {
      animation: false,
      responsive: true,
      plugins: {
        legend: { position: 'top', labels: { font: { size: 11 }, boxWidth: 12 } },
        tooltip: { mode: 'index', intersect: false }
      },
      scales: {
        x: {
          ticks: { font: { size: 10 }, maxTicksLimit: 15 }
        },
        y: {
          ticks: {
            font: { size: 10 },
            callback: v => Math.round(v / 10000) + '만t'
          }
        }
      }
    }
  });
}

function updateChart(rows) {
  if (!stockChart) return;
  stockChart.data.datasets[0].data = rows.map(r => r.totalStock);
  stockChart.update('none');
}
```

- [ ] **Step 2: `refresh()` 함수에 `updateChart` 호출 추가**

기존 `refresh()` 함수를 다음으로 교체:

```js
function refresh() {
  const rows = runCalc();
  renderHeader();
  renderTable(rows);
  renderHeaderSummary(rows);
  if (stockChart && !document.getElementById('chartWrap').hidden) {
    updateChart(rows);
  }
}
```

- [ ] **Step 3: 브라우저에서 동작 확인**

1. 페이지 열기
2. "📈 차트 보기" 버튼 클릭 → 차트 펼쳐짐, 버튼 텍스트 "📈 차트 닫기" 변경 확인
3. 다시 클릭 → 차트 접힘, 버튼 텍스트 "📈 차트 보기" 복원 확인
4. "반입 데이터 불러오기" 클릭 후 차트를 열어 데이터가 갱신되는지 확인
5. 상세 설정에서 초기 재고 값을 변경 후 저장 → 열린 차트가 즉시 갱신되는지 확인

- [ ] **Step 4: 커밋**

```bash
git add yard.html
git commit -m "feat: 총재고 추이 차트 토글 기능 구현"
```
