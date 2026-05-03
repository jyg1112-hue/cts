# 야드 시뮬레이션 차트 기능 — 설계 문서

**날짜:** 2026-04-12  
**파일:** `yard.html` (기존 파일 수정)

---

## 1. 목표

`yard.html` 시뮬레이션 테이블에 총재고 추이를 선 그래프로 볼 수 있는 토글 차트를 추가한다.

---

## 2. 화면 구성

### 2-1. 헤더 툴바 변경

기존 툴바에 토글 버튼 추가:

```
[반입 데이터 불러오기]  [상세 설정]  [📈 차트 보기]  |  마지막 업데이트: HH:MM
```

- 클릭 시 차트 영역 펼침 → 버튼 텍스트 "📈 차트 닫기"로 변경
- 다시 클릭 시 차트 영역 접힘 → 버튼 텍스트 "📈 차트 보기"로 복원
- 기본 상태: 접힘(hidden)

### 2-2. 차트 영역

- **위치:** 헤더 툴바 아래, 시뮬레이션 테이블 위
- **차트 유형:** 선 그래프 (Chart.js line)
- **데이터:** 총재고 1개 선 (파랑 `#2563eb`, 면적 채우기)
- **x축:** 날짜 (오늘 ~ 60일, `MM/DD` 형식, 최대 15개 틱)
- **y축:** 재고(t), `XX만t` 또는 `XXX,XXXt` 형식
- **포인트:** 표시 안 함 (radius: 0), 호버 시만 표시
- **애니메이션:** 없음 (refresh 시 즉시 갱신)

---

## 3. 기술 구현

### 라이브러리
- Chart.js 4.4.3 CDN: `https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js`
- 다른 페이지(`issue.html`)에서 이미 동일 버전 사용 중

### 추가할 코드 (yard.html 단일 파일)

**HTML 추가:**
1. `<head>`에 Chart.js `<script>` 태그
2. 툴바에 `<button id="btnChart">📈 차트 보기</button>`
3. 툴바 아래 `<div id="chartWrap" hidden><canvas id="stockChart"></canvas></div>`

**JS 추가:**
- `let stockChart = null` — Chart.js 인스턴스
- `toggleChart()` — `chartWrap` hidden 토글, 버튼 텍스트 전환, 차트 없으면 `initChart()` 호출
- `initChart(rows)` — Chart.js 인스턴스 생성, `rows`에서 날짜·총재고 추출
- `updateChart(rows)` — `stockChart.data` 갱신 후 `stockChart.update('none')`
- `refresh()` 수정 — 차트가 열려 있으면(`!chartWrap.hidden`) `updateChart(rows)` 호출

### 데이터 흐름

```
refresh()
  → rows = runCalc()
  → renderTable(rows)
  → if (!chartWrap.hidden) updateChart(rows)
```

`toggleChart()` 첫 호출 시:
```
toggleChart()
  → rows = runCalc()   // 이미 최신 데이터
  → initChart(rows)
  → chartWrap 표시
```

---

## 4. 제약 사항

- `berth7_v6`, `yard_sim_v1` 데이터 구조 변경 없음
- 차트 상태(열림/닫힘)는 localStorage에 저장하지 않음 — 페이지 새로고침 시 항상 접힌 상태
- 기존 `refresh()` 함수 시그니처 유지
