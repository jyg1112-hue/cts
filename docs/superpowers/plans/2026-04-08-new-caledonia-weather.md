# 뉴칼레도니아 날씨 현황 위젯 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `unloading_data.html` 하역 데이터 대시보드에 뉴칼레도니아 주요 광산 5곳의 실시간 날씨(기온·날씨 상태)와 3일 예보를 SVG 지도 위젯으로 추가한다.

**Architecture:** 단일 파일(`unloading_data.html`) 수정만으로 완성. Open-Meteo API를 브라우저에서 직접 호출(백엔드 불필요). 기존 `.main-grid`를 4-column으로 확장하고 날씨 패널을 4번째 `<article>`로 삽입. 인터랙션(hover 툴팁)·자동 갱신은 순수 JS로 처리.

**Tech Stack:** Vanilla JS (fetch, setInterval), SVG, Open-Meteo REST API (무료·무인증)

---

## File Map

| 파일 | 변경 내용 |
|------|-----------|
| `unloading_data.html:139-144` | `.main-grid` CSS — 3 → 4 column |
| `unloading_data.html:517` | `@media` 반응형 — main-grid 예외 없음(이미 1fr) |
| `unloading_data.html:520` | `</style>` 바로 앞 — 날씨 패널 CSS 삽입 |
| `unloading_data.html:608-609` | `</section>` 바로 앞 — 날씨 패널 HTML 삽입 |
| `unloading_data.html:1397` | `init()` 호출 바로 위 — 날씨 JS 블록 삽입 |

---

## Task 1: CSS — 날씨 패널 스타일

**Files:**
- Modify: `unloading_data.html:519` (`</style>` 바로 앞)

- [ ] **Step 1: `</style>` 바로 앞에 아래 CSS를 삽입한다**

```css
    /* ── 날씨 패널 ── */
    .weather-panel {
      display: flex;
      flex-direction: column;
      min-height: 420px;
      padding: 0;
    }
    .weather-header {
      padding: 12px 14px 8px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid #f3f4f6;
      flex-shrink: 0;
    }
    .weather-panel-title {
      font-size: 13px;
      font-weight: 700;
      color: #374151;
    }
    .weather-live-badge {
      display: flex;
      align-items: center;
      gap: 5px;
      font-size: 10px;
      color: #10b981;
      background: #ecfdf5;
      border: 1px solid #a7f3d0;
      border-radius: 20px;
      padding: 2px 8px;
      font-weight: 600;
    }
    .weather-live-dot {
      width: 5px;
      height: 5px;
      border-radius: 50%;
      background: #10b981;
    }
    .weather-map-area {
      flex: 1;
      position: relative;
      padding: 10px 12px 6px;
      min-height: 0;
    }
    .weather-map-area svg {
      width: 100%;
      height: 100%;
      min-height: 300px;
    }
    .weather-tooltip {
      position: absolute;
      background: #fff;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      padding: 8px 10px;
      width: 130px;
      box-shadow: 0 4px 16px rgba(0,0,0,0.12);
      pointer-events: none;
      z-index: 10;
      display: none;
    }
    .weather-tooltip.visible { display: block; }
    .weather-tooltip-name {
      font-size: 10px;
      font-weight: 700;
      color: #1a3a5c;
      margin-bottom: 6px;
      padding-bottom: 5px;
      border-bottom: 1px solid #f3f4f6;
    }
    .weather-tooltip-row {
      display: flex;
      align-items: center;
      gap: 4px;
      padding: 2px 0;
      font-size: 10px;
    }
    .weather-tooltip-day { color: #9ca3af; width: 26px; flex-shrink: 0; }
    .weather-tooltip-icon { font-size: 11px; }
    .weather-tooltip-label { color: #9ca3af; font-size: 9px; }
    .weather-tooltip-temp { font-size: 11px; font-weight: 700; color: #1f2937; margin-left: auto; }
    .weather-footer {
      padding: 7px 14px;
      border-top: 1px solid #f3f4f6;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-shrink: 0;
    }
    .weather-footer-text { font-size: 10px; color: #9ca3af; }
```

- [ ] **Step 2: 브라우저에서 `unloading_data.html` 열고 콘솔에 CSS 오류 없는지 확인**

---

## Task 2: HTML — main-grid 4-column 확장 + 날씨 패널 마크업

**Files:**
- Modify: `unloading_data.html:141` (`.main-grid` grid-template-columns)
- Modify: `unloading_data.html:608` (`</section>` 바로 앞)

- [ ] **Step 1: `.main-grid` CSS의 `grid-template-columns` 값을 변경한다**

찾을 텍스트 (unloading_data.html:141):
```css
      grid-template-columns: repeat(3, minmax(0, 1fr));
```
바꿀 텍스트:
```css
      grid-template-columns: repeat(4, minmax(0, 1fr));
```

- [ ] **Step 2: `@media (max-width: 1100px)` 블록의 `.main-grid` 줄은 이미 `1fr`이므로 변경 불필요 — 확인만 한다**

`unloading_data.html:517` 이 아래와 같은지 확인:
```css
      .main-grid { grid-template-columns: 1fr; }
```

- [ ] **Step 3: `</section>` (unloading_data.html:609) 바로 앞, 즉 supply-panel `</article>` 닫는 태그(608) 다음에 날씨 패널 HTML을 삽입한다**

`unloading_data.html:608` 에 있는:
```html
      </article>
    </section>
```
를 아래로 교체한다:
```html
      </article>

      <article class="panel weather-panel" id="weather-panel">
        <div class="weather-header">
          <span class="weather-panel-title">뉴칼레도니아 날씨 현황</span>
          <span class="weather-live-badge">
            <span class="weather-live-dot"></span>실시간
          </span>
        </div>
        <div class="weather-map-area">
          <!-- 호버 툴팁 -->
          <div class="weather-tooltip" id="weather-tooltip">
            <div class="weather-tooltip-name" id="wtt-name"></div>
            <div class="weather-tooltip-row">
              <span class="weather-tooltip-day">오늘</span>
              <span class="weather-tooltip-icon" id="wtt-d0-icon"></span>
              <span class="weather-tooltip-label" id="wtt-d0-label"></span>
              <span class="weather-tooltip-temp" id="wtt-d0-temp"></span>
            </div>
            <div class="weather-tooltip-row">
              <span class="weather-tooltip-day">내일</span>
              <span class="weather-tooltip-icon" id="wtt-d1-icon"></span>
              <span class="weather-tooltip-label" id="wtt-d1-label"></span>
              <span class="weather-tooltip-temp" id="wtt-d1-temp"></span>
            </div>
            <div class="weather-tooltip-row">
              <span class="weather-tooltip-day">모레</span>
              <span class="weather-tooltip-icon" id="wtt-d2-icon"></span>
              <span class="weather-tooltip-label" id="wtt-d2-label"></span>
              <span class="weather-tooltip-temp" id="wtt-d2-temp"></span>
            </div>
          </div>

          <svg id="weather-svg" viewBox="0 0 300 220" preserveAspectRatio="xMidYMid meet">
            <defs>
              <linearGradient id="wOceanGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#dbeafe"/>
                <stop offset="100%" stop-color="#bfdbfe"/>
              </linearGradient>
              <linearGradient id="wLandGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#d1fae5"/>
                <stop offset="100%" stop-color="#a7f3d0"/>
              </linearGradient>
              <filter id="wMarkerShadow" x="-80%" y="-80%" width="260%" height="260%">
                <feDropShadow dx="0" dy="1" stdDeviation="1.5" flood-color="rgba(0,0,0,0.15)"/>
              </filter>
            </defs>

            <!-- 바다 -->
            <rect width="300" height="220" fill="url(#wOceanGrad)" rx="6"/>

            <!-- 파도 결 -->
            <g stroke="rgba(147,197,253,0.35)" stroke-width="0.5" fill="none">
              <path d="M0,65 Q30,60 60,65 Q90,70 120,65 Q150,60 180,65 Q210,70 240,65 Q270,60 300,65"/>
              <path d="M0,155 Q30,150 60,155 Q90,160 120,155 Q150,150 180,155 Q210,160 240,155 Q270,150 300,155"/>
            </g>

            <!-- 뉴칼레도니아 Grande Terre 실루엣 -->
            <path d="M18,120 Q25,92 45,80 Q65,65 90,62 Q115,54 138,52 Q162,48 185,50 Q208,50 228,58 Q248,68 258,82 Q264,96 260,110 Q255,124 242,128 Q225,134 205,130 Q182,126 160,124 Q138,124 115,127 Q90,130 68,130 Q45,130 28,126 Z"
              fill="url(#wLandGrad)" stroke="#6ee7b7" stroke-width="0.8"/>

            <!-- 산악 음영 -->
            <path d="M80,80 Q105,65 130,62 Q155,56 175,60 Q190,60 200,68 Q185,74 165,76 Q145,76 125,78 Q105,80 85,84 Z"
              fill="#6ee7b7" opacity="0.3"/>

            <!-- 나침반 -->
            <text x="278" y="14" text-anchor="middle" font-size="6" fill="#93c5fd" font-weight="700">N</text>
            <line x1="278" y1="16" x2="278" y2="22" stroke="#93c5fd" stroke-width="0.8"/>
            <line x1="274" y1="19" x2="282" y2="19" stroke="#bfdbfe" stroke-width="0.5"/>

            <!-- 스케일 -->
            <line x1="12" y1="208" x2="52" y2="208" stroke="#93c5fd" stroke-width="0.8"/>
            <text x="32" y="216" text-anchor="middle" font-size="5" fill="#93c5fd">200 km</text>

            <!-- 광산 마커 그룹 (JS가 data-mine-id로 찾음) -->
            <!-- Nouméa: cx=60 cy=118 -->
            <g class="mine-marker" data-mine-id="noumea" style="cursor:pointer;" filter="url(#wMarkerShadow)">
              <circle class="marker-ring" cx="60" cy="118" r="8" fill="rgba(26,58,92,0.1)" stroke="#1a3a5c" stroke-width="1.5"/>
              <circle class="marker-dot" cx="60" cy="118" r="3.5" fill="#1a3a5c"/>
            </g>
            <text x="60" y="133" text-anchor="middle" font-size="6.5" fill="#374151" font-weight="700" pointer-events="none">Nouméa</text>
            <text class="marker-weather" data-mine-id="noumea" x="60" y="143" text-anchor="middle" font-size="9" pointer-events="none">—</text>

            <!-- Thio: cx=195 cy=100 -->
            <g class="mine-marker" data-mine-id="thio" style="cursor:pointer;" filter="url(#wMarkerShadow)">
              <circle class="marker-ring" cx="195" cy="100" r="8" fill="rgba(26,58,92,0.1)" stroke="#1a3a5c" stroke-width="1.5"/>
              <circle class="marker-dot" cx="195" cy="100" r="3.5" fill="#1a3a5c"/>
            </g>
            <text x="195" y="115" text-anchor="middle" font-size="6.5" fill="#374151" font-weight="700" pointer-events="none">Thio</text>
            <text class="marker-weather" data-mine-id="thio" x="195" y="125" text-anchor="middle" font-size="9" pointer-events="none">—</text>

            <!-- Koniambo: cx=148 cy=68 -->
            <g class="mine-marker" data-mine-id="koniambo" style="cursor:pointer;" filter="url(#wMarkerShadow)">
              <circle class="marker-ring" cx="148" cy="68" r="8" fill="rgba(26,58,92,0.1)" stroke="#1a3a5c" stroke-width="1.5"/>
              <circle class="marker-dot" cx="148" cy="68" r="3.5" fill="#1a3a5c"/>
            </g>
            <text x="148" y="83" text-anchor="middle" font-size="6.5" fill="#374151" font-weight="700" pointer-events="none">Koniambo</text>
            <text class="marker-weather" data-mine-id="koniambo" x="148" y="93" text-anchor="middle" font-size="9" pointer-events="none">—</text>

            <!-- Kouaoua: cx=224 cy=80 -->
            <g class="mine-marker" data-mine-id="kouaoua" style="cursor:pointer;" filter="url(#wMarkerShadow)">
              <circle class="marker-ring" cx="224" cy="80" r="8" fill="rgba(26,58,92,0.1)" stroke="#1a3a5c" stroke-width="1.5"/>
              <circle class="marker-dot" cx="224" cy="80" r="3.5" fill="#1a3a5c"/>
            </g>
            <text x="224" y="95" text-anchor="middle" font-size="6.5" fill="#374151" font-weight="700" pointer-events="none">Kouaoua</text>
            <text class="marker-weather" data-mine-id="kouaoua" x="224" y="105" text-anchor="middle" font-size="9" pointer-events="none">—</text>

            <!-- Goro: cx=236 cy=122 -->
            <g class="mine-marker" data-mine-id="goro" style="cursor:pointer;" filter="url(#wMarkerShadow)">
              <circle class="marker-ring" cx="236" cy="122" r="8" fill="rgba(26,58,92,0.1)" stroke="#1a3a5c" stroke-width="1.5"/>
              <circle class="marker-dot" cx="236" cy="122" r="3.5" fill="#1a3a5c"/>
            </g>
            <text x="236" y="137" text-anchor="middle" font-size="6.5" fill="#374151" font-weight="700" pointer-events="none">Goro</text>
            <text class="marker-weather" data-mine-id="goro" x="236" y="147" text-anchor="middle" font-size="9" pointer-events="none">—</text>
          </svg>
        </div>
        <div class="weather-footer">
          <span class="weather-footer-text"><span style="color:#10b981;font-weight:600;">●</span> Open-Meteo · 자동 갱신</span>
          <span class="weather-footer-text" id="weather-last-updated">—</span>
        </div>
      </article>
    </section>
```

- [ ] **Step 4: 브라우저에서 새로고침 — 4번째 패널이 나타나고, SVG 지도(민트 섬·파란 바다)와 마커 5개가 보이는지 확인. 날씨 텍스트는 아직 `—` 로 표시됨**

- [ ] **Step 5: Commit**

```bash
git add unloading_data.html
git commit -m "feat: add NC weather panel HTML/CSS skeleton"
```

---

## Task 3: JS — 광산 데이터 상수 + WMO 날씨 코드 매핑

**Files:**
- Modify: `unloading_data.html` — `<script>` 블록 상단 (기존 `const state = {` 바로 위)

- [ ] **Step 1: 기존 `<script>` 태그 바로 다음 줄, `const state = {` 바로 위에 아래 상수를 삽입한다**

```js
    // ── 뉴칼레도니아 광산 날씨 ──────────────────────────────
    const MINES = [
      { id: 'noumea',   name: 'Nouméa',   lat: -22.2758, lon: 166.4580 },
      { id: 'thio',     name: 'Thio',     lat: -21.6128, lon: 166.2178 },
      { id: 'koniambo', name: 'Koniambo', lat: -20.9167, lon: 164.3500 },
      { id: 'kouaoua',  name: 'Kouaoua',  lat: -21.3833, lon: 165.8167 },
      { id: 'goro',     name: 'Goro',     lat: -22.2667, lon: 166.9833 },
    ];

    function wmoInfo(code) {
      if (code === 0)                          return { icon: '☀️', label: '맑음' };
      if (code <= 3)                           return { icon: '⛅', label: '구름' };
      if (code <= 48)                          return { icon: '🌫️', label: '안개' };
      if (code <= 55)                          return { icon: '🌦️', label: '이슬비' };
      if (code <= 65)                          return { icon: '🌧️', label: '비' };
      if (code <= 77)                          return { icon: '🌨️', label: '눈' };
      if (code <= 82)                          return { icon: '🌦️', label: '소나기' };
      if (code <= 86)                          return { icon: '🌨️', label: '눈소나기' };
      return                                          { icon: '⛈️', label: '뇌우' };
    }
    // ────────────────────────────────────────────────────────
```

- [ ] **Step 2: 브라우저 콘솔에서 `wmoInfo(0)`, `wmoInfo(61)`, `wmoInfo(95)` 를 입력해 각각 `{icon:'☀️',label:'맑음'}`, `{icon:'🌧️',label:'비'}`, `{icon:'⛈️',label:'뇌우'}` 가 반환되는지 확인**

---

## Task 4: JS — fetchWeather() 함수

**Files:**
- Modify: `unloading_data.html` — MINES 상수 블록 아래

- [ ] **Step 1: `wmoInfo` 함수 아래, `// ────` 구분선 바로 위에 fetchWeather 함수를 삽입한다**

```js
    async function fetchWeather() {
      const BASE = 'https://api.open-meteo.com/v1/forecast';
      const PARAMS = 'current=temperature_2m,weathercode&daily=temperature_2m_max,weathercode&forecast_days=3&timezone=Pacific%2FNoumea';

      const results = await Promise.all(
        MINES.map(mine =>
          fetch(`${BASE}?latitude=${mine.lat}&longitude=${mine.lon}&${PARAMS}`)
            .then(r => r.json())
            .then(data => ({
              id: mine.id,
              name: mine.name,
              currentTemp: Math.round(data.current.temperature_2m),
              currentCode: data.current.weathercode,
              daily: data.daily.temperature_2m_max.map((t, i) => ({
                temp: Math.round(t),
                code: data.daily.weathercode[i],
              })),
            }))
        )
      );
      return results;
    }
```

- [ ] **Step 2: 브라우저 콘솔에서 `fetchWeather().then(console.log)` 실행 — 5개 광산 데이터 객체 배열이 출력되는지 확인. 각 객체에 `currentTemp`(숫자), `currentCode`(숫자), `daily`(길이 3 배열) 있어야 함**

---

## Task 5: JS — renderWeatherMarkers() 함수

**Files:**
- Modify: `unloading_data.html` — `fetchWeather` 함수 아래

- [ ] **Step 1: `fetchWeather` 함수 다음 줄에 renderWeatherMarkers 함수를 삽입한다**

```js
    function renderWeatherMarkers(weatherData) {
      weatherData.forEach(mine => {
        const { icon } = wmoInfo(mine.currentCode);
        // 마커 위 날씨 텍스트 업데이트
        document.querySelectorAll(`.marker-weather[data-mine-id="${mine.id}"]`).forEach(el => {
          el.textContent = `${icon} ${mine.currentTemp}°`;
        });
        // 마커에 날씨 데이터 저장 (툴팁에서 사용)
        document.querySelectorAll(`.mine-marker[data-mine-id="${mine.id}"]`).forEach(el => {
          el.dataset.weatherJson = JSON.stringify(mine);
        });
      });

      // 마지막 업데이트 시각
      const now = new Date();
      const hhmm = now.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
      const el = document.getElementById('weather-last-updated');
      if (el) el.textContent = `${hhmm} 업데이트`;
    }
```

- [ ] **Step 2: 브라우저 콘솔에서 아래를 실행해 마커 텍스트가 실제 날씨로 바뀌는지 확인**

```js
fetchWeather().then(renderWeatherMarkers)
```

SVG 지도 위 5개 광산 마커 아래 `☀️ 26°` 형태의 텍스트가 보여야 함.

---

## Task 6: JS — 호버 툴팁 인터랙션

**Files:**
- Modify: `unloading_data.html` — `renderWeatherMarkers` 함수 아래

- [ ] **Step 1: `renderWeatherMarkers` 함수 다음 줄에 initWeatherTooltip 함수를 삽입한다**

```js
    function initWeatherTooltip() {
      const tooltip = document.getElementById('weather-tooltip');
      const mapArea = document.querySelector('.weather-map-area');

      document.querySelectorAll('.mine-marker').forEach(marker => {
        marker.addEventListener('mouseenter', e => {
          const raw = marker.dataset.weatherJson;
          if (!raw) return;
          const mine = JSON.parse(raw);

          // 광산명
          document.getElementById('wtt-name').textContent = `⛏ ${mine.name}`;

          // 3일 예보 채우기
          ['d0', 'd1', 'd2'].forEach((key, i) => {
            const day = mine.daily[i];
            if (!day) return;
            const { icon, label } = wmoInfo(day.code);
            document.getElementById(`wtt-${key}-icon`).textContent = icon;
            document.getElementById(`wtt-${key}-label`).textContent = label;
            document.getElementById(`wtt-${key}-temp`).textContent = `${day.temp}°`;
          });

          // 툴팁 위치: 마커 위 (mapArea 기준 상대좌표)
          const markerRect = marker.getBoundingClientRect();
          const areaRect = mapArea.getBoundingClientRect();
          let left = markerRect.left - areaRect.left - 65; // 툴팁 중앙 정렬
          let top  = markerRect.top  - areaRect.top  - 110;

          // 경계 벗어남 방지
          left = Math.max(0, Math.min(left, areaRect.width - 134));
          top  = Math.max(0, top);

          tooltip.style.left = left + 'px';
          tooltip.style.top  = top  + 'px';
          tooltip.classList.add('visible');

          // 호버된 마커 파란색 강조
          marker.querySelector('.marker-ring').setAttribute('stroke', '#3b82f6');
          marker.querySelector('.marker-ring').setAttribute('fill', 'rgba(59,130,246,0.15)');
          marker.querySelector('.marker-dot').setAttribute('fill', '#3b82f6');
        });

        marker.addEventListener('mouseleave', () => {
          tooltip.classList.remove('visible');
          // 마커 원래 색 복원
          marker.querySelector('.marker-ring').setAttribute('stroke', '#1a3a5c');
          marker.querySelector('.marker-ring').setAttribute('fill', 'rgba(26,58,92,0.1)');
          marker.querySelector('.marker-dot').setAttribute('fill', '#1a3a5c');
        });
      });
    }
```

- [ ] **Step 2: 브라우저에서 마커 위에 마우스를 올렸을 때 툴팁이 나타나고, 빠져나오면 사라지는지 확인. 마커가 파란색으로 강조되는지 확인.**

---

## Task 7: JS — init() 연결 + 30분 자동 갱신

**Files:**
- Modify: `unloading_data.html:1379` — `async function init()` 내부

- [ ] **Step 1: 기존 `init()` 함수 안에서 `initWeatherTooltip()` 호출과 날씨 fetch 루프를 추가한다**

기존:
```js
    async function init() {
      try {
        const meta = await fetchMeta();
```
를 아래로 교체한다:
```js
    async function init() {
      // 날씨 툴팁 이벤트 먼저 등록 (데이터 없어도 구조는 존재)
      initWeatherTooltip();

      // 날씨 초기 로드 + 30분 자동 갱신
      async function loadWeather() {
        try {
          const data = await fetchWeather();
          renderWeatherMarkers(data);
        } catch (err) {
          console.warn('날씨 로드 실패:', err);
        }
      }
      loadWeather();
      setInterval(loadWeather, 30 * 60 * 1000);

      try {
        const meta = await fetchMeta();
```

- [ ] **Step 2: 브라우저에서 새로고침 후 날씨 위젯 전체 동작 최종 확인**

체크리스트:
- [ ] SVG 지도 + 5개 마커 렌더링 정상
- [ ] 각 마커에 실제 기온·날씨 이모지 표시
- [ ] 마커 hover 시 3일 예보 툴팁 표시, 마우스 빠지면 사라짐
- [ ] footer에 업데이트 시각 `HH:MM 업데이트` 표시
- [ ] 브라우저 네트워크 탭에서 `api.open-meteo.com` 요청 5건 성공(200)
- [ ] 기존 대시보드 기능(KPI, 차트, 공급 이슈) 정상 작동

- [ ] **Step 3: Commit**

```bash
git add unloading_data.html
git commit -m "feat: 뉴칼레도니아 광산 날씨 현황 위젯 구현"
```

---

## 검증 명령

```bash
# 로컬 서버 실행
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 브라우저 접속
open http://localhost:8000/unloading-data
```

또는 `unloading_data.html` 파일을 브라우저에서 직접 열어도 날씨 API는 동작함 (CORS 없음).
