# schedule/banchu DB 연동 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** schedule.html과 banchu.html의 localStorage 데이터를 Supabase PostgreSQL(DATABASE_URL)에 저장해 어느 기기에서나 같은 데이터를 공유한다.

**Architecture:** FastAPI 백엔드에 GET/PUT 엔드포인트 4개를 추가하고(`/api/schedule`, `/api/banchu`), 각 HTML 파일의 `save()` 함수와 초기화 로직을 API 호출로 교체한다. 저장은 fire-and-forget 비동기, 로드는 페이지 시작 시 await.

**Tech Stack:** Python 3.11, FastAPI, psycopg3, PostgreSQL(Supabase), vanilla JS fetch API

---

## 파일 변경 목록

| 파일 | 작업 |
|------|------|
| `backend/main.py` | DB 테이블 생성 함수, GET/PUT 엔드포인트 4개 추가 |
| `schedule.html` | `save()` 함수 교체, 초기화 async로 변경 |
| `banchu.html` | `save()` 함수 교체, 초기화 async로 변경 |
| `tests/test_schedule_banchu_api.py` | 신규 — API 엔드포인트 단위 테스트 |

---

### Task 1: DB 테이블 생성 및 백엔드 헬퍼

**Files:**
- Modify: `backend/main.py`
- Create: `tests/test_schedule_banchu_api.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_schedule_banchu_api.py` 파일 생성:

```python
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from backend.main import app
    return TestClient(app, raise_server_exceptions=False)


class TestScheduleApi:
    def test_get_schedule_returns_list(self, client):
        mock_rows = [
            ({"id": "1", "type": "ship", "name": "테스트선", "start": "2026-04-01T08:00", "end": "2026-04-02T08:00"},),
        ]
        with patch("backend.main._db_fetch_items", return_value=mock_rows):
            res = client.get("/api/schedule")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        assert data[0]["id"] == "1"

    def test_get_schedule_returns_empty_list_on_db_error(self, client):
        with patch("backend.main._db_fetch_items", side_effect=Exception("db error")):
            res = client.get("/api/schedule")
        assert res.status_code == 200
        assert res.json() == []

    def test_put_schedule_saves_items(self, client):
        items = [{"id": "1", "type": "ship", "name": "테스트선", "start": "2026-04-01T08:00", "end": "2026-04-02T08:00"}]
        with patch("backend.main._db_save_items") as mock_save:
            res = client.put("/api/schedule", json=items)
        assert res.status_code == 200
        mock_save.assert_called_once()


class TestBanchuApi:
    def test_get_banchu_returns_list(self, client):
        mock_rows = [
            ({"id": "2", "cat": "CW1", "name": "슬라그", "start": "2026-04-01T08:00", "end": "2026-04-01T16:00"},),
        ]
        with patch("backend.main._db_fetch_items", return_value=mock_rows):
            res = client.get("/api/banchu")
        assert res.status_code == 200
        data = res.json()
        assert data[0]["id"] == "2"

    def test_put_banchu_saves_items(self, client):
        items = [{"id": "2", "cat": "CW1", "name": "슬라그", "start": "2026-04-01T08:00", "end": "2026-04-01T16:00"}]
        with patch("backend.main._db_save_items") as mock_save:
            res = client.put("/api/banchu", json=items)
        assert res.status_code == 200
        mock_save.assert_called_once()
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

```bash
cd /Users/jo/Desktop/프로젝트
python3 -m pytest tests/test_schedule_banchu_api.py -v
```

Expected: `AttributeError` 또는 404 — `_db_fetch_items`, `/api/schedule` 미정의

- [ ] **Step 3: DB 헬퍼 함수 및 테이블 생성 로직 추가**

`backend/main.py`에서 `SUPABASE_BUCKET` 상수 근처(약 44번째 줄 이후)에 아래 함수 추가:

```python
def _db_dsn() -> str | None:
    u = (os.environ.get("DATABASE_URL") or "").strip()
    return u or None


def _ensure_schedule_banchu_tables() -> None:
    """schedule_items, banchu_items 테이블이 없으면 생성."""
    dsn = _db_dsn()
    if not dsn:
        return
    import psycopg
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS schedule_items (
                    id TEXT PRIMARY KEY,
                    data JSONB NOT NULL,
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS banchu_items (
                    id TEXT PRIMARY KEY,
                    data JSONB NOT NULL,
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
        conn.commit()


def _db_fetch_items(table: str) -> list[tuple]:
    """테이블에서 모든 아이템 data 컬럼 반환."""
    dsn = _db_dsn()
    if not dsn:
        return []
    import psycopg
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT data FROM {table} ORDER BY updated_at")
            return cur.fetchall()


def _db_save_items(table: str, items: list[dict[str, Any]]) -> None:
    """테이블 전체를 items로 교체 저장 (DELETE → INSERT)."""
    dsn = _db_dsn()
    if not dsn:
        return
    import psycopg
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {table}")
            for item in items:
                item_id = str(item.get("id") or "")
                if not item_id:
                    continue
                cur.execute(
                    f"INSERT INTO {table} (id, data, updated_at) VALUES (%s, %s, NOW())",
                    (item_id, json.dumps(item, ensure_ascii=False)),
                )
        conn.commit()
```

- [ ] **Step 4: startup 이벤트에 테이블 생성 호출 추가**

`debug_startup_trace` 함수에서 `# region agent log` 바로 위에 추가:

```python
    _ensure_schedule_banchu_tables()
```

- [ ] **Step 5: GET/PUT 엔드포인트 4개 추가**

`backend/main.py`의 `/api/config` 엔드포인트 바로 앞에 추가:

```python
@app.get("/api/schedule")
def get_schedule() -> JSONResponse:
    try:
        rows = _db_fetch_items("schedule_items")
        items = [row[0] for row in rows]
    except Exception:
        items = []
    return JSONResponse(items)


@app.put("/api/schedule")
async def put_schedule(request: Request) -> JSONResponse:
    try:
        items = await request.json()
        if not isinstance(items, list):
            raise HTTPException(status_code=400, detail="배열 형식이어야 합니다.")
        _db_save_items("schedule_items", items)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"저장 실패: {e}")
    return JSONResponse({"ok": True, "count": len(items)})


@app.get("/api/banchu")
def get_banchu() -> JSONResponse:
    try:
        rows = _db_fetch_items("banchu_items")
        items = [row[0] for row in rows]
    except Exception:
        items = []
    return JSONResponse(items)


@app.put("/api/banchu")
async def put_banchu(request: Request) -> JSONResponse:
    try:
        items = await request.json()
        if not isinstance(items, list):
            raise HTTPException(status_code=400, detail="배열 형식이어야 합니다.")
        _db_save_items("banchu_items", items)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"저장 실패: {e}")
    return JSONResponse({"ok": True, "count": len(items)})
```

- [ ] **Step 6: 테스트 통과 확인**

```bash
cd /Users/jo/Desktop/프로젝트
python3 -m pytest tests/test_schedule_banchu_api.py -v
```

Expected: 5개 모두 PASS

- [ ] **Step 7: 전체 테스트 통과 확인**

```bash
python3 -m pytest tests/ -v 2>&1 | tail -5
```

Expected: `XX passed`

- [ ] **Step 8: 커밋**

```bash
git add backend/main.py tests/test_schedule_banchu_api.py
git commit -m "feat: add schedule/banchu DB tables and GET/PUT API endpoints"
```

---

### Task 2: schedule.html DB 연동

**Files:**
- Modify: `schedule.html`

- [ ] **Step 1: `let items` 선언 교체**

`schedule.html`에서 아래 줄을 찾아:

```javascript
let items      = JSON.parse(localStorage.getItem(KEY) || '[]');
```

다음으로 교체:

```javascript
let items      = [];
```

- [ ] **Step 2: `save()` 함수 교체**

`schedule.html`에서 아래 함수를 찾아:

```javascript
function save() { localStorage.setItem(KEY, JSON.stringify(items)); }
```

다음으로 교체:

```javascript
function save() {
  fetch('/api/schedule', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(items),
  }).catch(err => console.warn('스케줄 저장 실패:', err));
}
```

- [ ] **Step 3: INIT 섹션 async로 교체**

`schedule.html` 맨 아래 INIT 섹션을 찾아:

```javascript
// ══════════════════════════════════════════
//  DATA MIGRATION
// ══════════════════════════════════════════
// 정기정비 → 정비 마이그레이션
let migrated = false;
items.forEach(i => {
  if (i.type === 'jeonbi' && (i.label === '정기정비' || i.name === '정기정비')) {
    i.label = '정비'; i.name = '정비'; migrated = true;
  }
});
if (migrated) save();

// ══════════════════════════════════════════
//  INIT
// ══════════════════════════════════════════
resolveBerthNonOverlap();
save();
initRange(); render(); scrollToToday();
window.addEventListener('resize', render);
```

다음으로 교체:

```javascript
// ══════════════════════════════════════════
//  INIT (async — DB에서 로드)
// ══════════════════════════════════════════
(async function init() {
  try {
    const res = await fetch('/api/schedule');
    if (res.ok) items = await res.json();
  } catch (e) {
    console.warn('스케줄 로드 실패:', e);
  }

  // 정기정비 → 정비 마이그레이션
  let migrated = false;
  items.forEach(i => {
    if (i.type === 'jeonbi' && (i.label === '정기정비' || i.name === '정기정비')) {
      i.label = '정비'; i.name = '정비'; migrated = true;
    }
  });
  if (migrated) save();

  resolveBerthNonOverlap();
  save();
  initRange(); render(); scrollToToday();
  window.addEventListener('resize', render);
})();
```

- [ ] **Step 4: 동작 확인 (로컬)**

```bash
cd /Users/jo/Desktop/프로젝트
python3 -m uvicorn backend.main:app --reload --port 8000
```

브라우저에서 `http://localhost:8000/schedule` 열기 → 아이템 추가 → 다른 브라우저/탭에서 같은 URL 열어 데이터 공유 확인.

- [ ] **Step 5: 커밋**

```bash
git add schedule.html
git commit -m "feat: schedule.html localStorage → /api/schedule DB 연동"
```

---

### Task 3: banchu.html DB 연동

**Files:**
- Modify: `banchu.html`

- [ ] **Step 1: `let items` 선언 교체**

`banchu.html`에서 아래 줄을 찾아:

```javascript
let items      = JSON.parse(localStorage.getItem(KEY) || '[]');
```

다음으로 교체:

```javascript
let items      = [];
```

- [ ] **Step 2: `save()` 함수 교체**

`banchu.html`에서 아래 함수를 찾아:

```javascript
function save() { localStorage.setItem(KEY, JSON.stringify(items)); }
```

다음으로 교체:

```javascript
function save() {
  fetch('/api/banchu', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(items),
  }).catch(err => console.warn('반출 저장 실패:', err));
}
```

- [ ] **Step 3: INIT 섹션 async로 교체**

`banchu.html` 맨 아래 INIT 섹션을 찾아:

```javascript
// ══════════════════════════════════════════
//  INIT
// ══════════════════════════════════════════
initRange(); render(); scrollToToday();
window.addEventListener('resize', render);
```

다음으로 교체:

```javascript
// ══════════════════════════════════════════
//  INIT (async — DB에서 로드)
// ══════════════════════════════════════════
(async function init() {
  try {
    const res = await fetch('/api/banchu');
    if (res.ok) items = await res.json();
  } catch (e) {
    console.warn('반출 로드 실패:', e);
  }
  initRange(); render(); scrollToToday();
  window.addEventListener('resize', render);
})();
```

- [ ] **Step 4: 동작 확인 (로컬)**

브라우저에서 `http://localhost:8000/banchu` 열기 → 아이템 추가 → 다른 브라우저/탭에서 같은 URL 열어 데이터 공유 확인.

- [ ] **Step 5: 커밋**

```bash
git add banchu.html
git commit -m "feat: banchu.html localStorage → /api/banchu DB 연동"
```

---

### Task 4: Push 및 배포 확인

**Files:** 없음 (git push)

- [ ] **Step 1: 전체 테스트 최종 확인**

```bash
cd /Users/jo/Desktop/프로젝트
python3 -m pytest tests/ -v 2>&1 | tail -5
```

Expected: `XX passed`

- [ ] **Step 2: Push**

```bash
git push origin main
```

Render 자동 재배포 트리거됨 (`autoDeploy: true`).

- [ ] **Step 3: 배포 후 검증**

1. `https://cts-1-38qw.onrender.com/schedule` 에서 아이템 추가
2. 다른 기기/브라우저에서 같은 URL 열어 아이템이 보이는지 확인
3. `https://cts-1-38qw.onrender.com/banchu` 동일하게 확인
4. Supabase 대시보드 → Table Editor → `schedule_items`, `banchu_items` 테이블에 데이터 있는지 확인:
   [https://supabase.com/dashboard/project/tsxtukuemafrwegjorou/editor](https://supabase.com/dashboard/project/tsxtukuemafrwegjorou/editor)
