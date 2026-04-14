# 설계: yard.html localStorage → Supabase DB 연동

**날짜:** 2026-04-14  
**범위:** 4단계 — yard.html 시뮬 설정 DB 저장 + 선석 스케줄 반입 계획 연동

---

## 배경

`yard.html`은 야드 재고 시뮬레이션 페이지로, 두 가지 localStorage 의존성이 있다:

1. **SIM 설정** (`yard_sim_v2_overall`, `yard_sim_v2_import`) — 시뮬 파라미터 전체. 기기마다 독립 저장돼 공유 불가.
2. **선석 스케줄 참조** (`berth7_v6`) — `calcAutoInbound()`에서 읽어 자동 반입량 계산. schedule.html이 DB로 이전되면서 이 키는 항상 `[]`를 반환해 반입 계획 기능이 깨진 상태.

---

## 아키텍처

### DB 추가 (Supabase PostgreSQL — 기존 DATABASE_URL)

```sql
CREATE TABLE yard_sim_settings (
    mode TEXT PRIMARY KEY,        -- 'overall' 또는 'import'
    data JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 백엔드 (backend/main.py) — 2개 엔드포인트 추가

| 메서드 | 경로 | 동작 |
|--------|------|------|
| GET | `/api/yard-sim?mode=overall` | 해당 모드 SIM 설정 반환 (없으면 `null`) |
| PUT | `/api/yard-sim?mode=overall` | 해당 모드 SIM 설정 저장 |

`mode`는 `overall` 또는 `import`만 허용.

### yard.html 변경

**추가되는 전역 캐시 변수:**
```javascript
let _scheduleCache = [];                          // /api/schedule 결과
let _simCache = { overall: null, import: null };  // /api/yard-sim 결과
```

**변경되는 것:**

| 함수 | 변경 내용 |
|------|-----------|
| `loadSimSettings(mode)` | `_simCache[mode]` 읽기 (sync 유지) |
| `saveSimSettings(s)` | `_simCache[mode]` 업데이트 + `fetch PUT /api/yard-sim?mode=` fire-and-forget |
| `calcAutoInbound()` | `localStorage.getItem(BERTH_KEY)` → `_scheduleCache` 사용 |
| `let SIM = loadSimSettings()` (line 603) | 제거 → INIT async IIFE에서 설정 |
| INIT 섹션 (맨 하단) | async IIFE로 교체 |

**변경 없는 것:**
- `getPageMode()` / `setPageMode()` — localStorage 유지 (UI 설정)
- `isImportOutCollapsed()` / `setImportOutCollapsed()` — localStorage 유지 (UI 설정)
- `refresh()`, `withResolvedAutoInbound()`, `runCalc()` — 동기 유지
- `onPageModeChange()` — 동기 유지 (캐시에서 읽음)

---

## 데이터 흐름

### 페이지 로드 (async IIFE)

```
yard.html 열림
  → 병렬 fetch:
      GET /api/yard-sim?mode=overall
      GET /api/yard-sim?mode=import
      GET /api/schedule
  → _simCache.overall = 응답 or DEFAULT_SETTINGS
  → _simCache.import  = 응답 or DEFAULT_SETTINGS
  → _scheduleCache    = 응답 or []
  → SIM = loadSimSettings(getPageMode())  ← 캐시에서 읽기 (sync)
  → document.getElementById('pageSelect').value = getPageMode()
  → refresh()
```

### SIM 설정 저장

```
saveSimSettings(s) 호출 시
  → _simCache[현재모드] = s  (즉시 캐시 업데이트)
  → fetch PUT /api/yard-sim?mode={모드} { body: JSON.stringify(s) }  (fire-and-forget)
```

### 자동 반입 계산

```
calcAutoInbound(mode) 호출 시
  → _scheduleCache 사용  (localStorage 읽기 없음)
  → 선박 타입/화물/날짜 필터링 후 일별 반입량 계산
  → 결과 반환 (sync 유지)
```

### 모드 전환 (onPageModeChange)

```
사용자가 overall ↔ import 전환
  → saveSimSettings(SIM)  (현재 모드 저장)
  → setPageMode(mode)
  → SIM = loadSimSettings(mode)  ← _simCache에서 읽기 (sync)
  → refresh()
```

---

## 에러 처리

| 상황 | 처리 |
|------|------|
| SIM 로드 실패 | `DEFAULT_SETTINGS` fallback |
| `/api/schedule` 실패 | `_scheduleCache = []` (반입 계획 빈 값) |
| `DATABASE_URL` 미설정 | 500 + 에러 메시지 |
| `mode` 파라미터 이상값 | 400 에러 |

---

## 구현 순서

1. `backend/main.py` — `yard_sim_settings` 테이블 생성 함수, `/api/yard-sim` GET/PUT 추가
2. `yard.html` — 캐시 변수 추가, `loadSimSettings`/`saveSimSettings`/`calcAutoInbound` 교체, INIT async 변환
