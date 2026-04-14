# 설계: schedule/banchu localStorage → Supabase DB 연동

**날짜:** 2026-04-14  
**범위:** 3단계 — schedule, banchu 페이지 데이터 공유 저장소 이전

---

## 배경

`schedule.html`과 `banchu.html`은 데이터를 브라우저 `localStorage`에 저장한다. 이 방식은 컴퓨터마다 독립적이라 다른 기기에서 같은 데이터를 볼 수 없다. Supabase PostgreSQL에 저장해 어느 기기에서나 동일한 데이터를 공유한다.

편집자는 사실상 1명이며 동시 편집 충돌 처리는 불필요하다.

---

## 아키텍처

### DB (Supabase PostgreSQL — 기존 DATABASE_URL 재사용)

```sql
CREATE TABLE schedule_items (
    id TEXT PRIMARY KEY,
    data JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE banchu_items (
    id TEXT PRIMARY KEY,
    data JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

각 아이템은 기존 JS 객체 구조 그대로 `data` JSONB 컬럼에 저장한다.

### 백엔드 (backend/main.py) — 4개 엔드포인트 추가

| 메서드 | 경로 | 동작 |
|--------|------|------|
| GET | `/api/schedule` | schedule_items 전체 배열 반환 |
| PUT | `/api/schedule` | schedule_items 전체 교체 저장 |
| GET | `/api/banchu` | banchu_items 전체 배열 반환 |
| PUT | `/api/banchu` | banchu_items 전체 교체 저장 |

PUT은 트랜잭션으로 기존 행 전체 DELETE 후 새 행 INSERT (bulk replace).

### 프론트 (schedule.html, banchu.html)

- 페이지 로드: `localStorage.getItem()` → `await fetch('GET /api/...')`
- 저장: `localStorage.setItem()` → `fetch('PUT /api/...')` (비동기, 화면은 즉시 반영)

### 변경 없음

- `items` 배열 구조 및 필드 — 그대로 유지
- UI 로직, 렌더링, 모달 — 변경 없음

---

## 데이터 흐름

### 페이지 로드

```
페이지 열림
  → fetch GET /api/schedule (또는 /api/banchu)
  → 성공: items = 응답 배열 → render()
  → 실패: items = [] → 빈 화면으로 시작
```

### 저장

```
사용자 아이템 추가/수정/삭제
  → save() 호출
  → fetch PUT /api/schedule { body: JSON.stringify(items) }
  → 비동기 백그라운드 저장 (화면은 즉시 반영)
```

### PUT 백엔드 처리

```
PUT /api/schedule
  → body에서 items 배열 파싱
  → 트랜잭션: schedule_items 전체 DELETE → items INSERT
  → 200 응답
```

---

## 에러 처리

| 상황 | 처리 |
|------|------|
| 로드 실패 | items = [] 빈 배열로 시작, 콘솔 경고 |
| 저장 실패 | 콘솔 경고 (UX 방해 최소화) |
| DATABASE_URL 미설정 | 500 + 명확한 에러 메시지 |

---

## 아이템 필드 구조

### schedule_items

```json
{
  "id": "1234567890",
  "type": "ship",
  "name": "선명",
  "start": "2026-04-14T08:00",
  "end": "2026-04-15T12:00",
  "cargoType": "석탄",
  "color": "#3b82f6",
  "origin": "호주",
  "brand": "BHP",
  "bl": 50000,
  "rate": 5000,
  "blDate": "2026-04-14",
  "customer": "포스코"
}
```

type은 `ship` / `maint` / `jeonbi` 중 하나.

### banchu_items

```json
{
  "id": "1234567890",
  "cat": "CW1",
  "name": "슬라그",
  "start": "2026-04-14T08:00",
  "end": "2026-04-14T16:00",
  "color": "#fb923c"
}
```

---

## 구현 순서

1. Supabase에 `schedule_items`, `banchu_items` 테이블 생성 (마이그레이션)
2. `backend/main.py`에 4개 엔드포인트 추가
3. `schedule.html` 수정 — 로드/저장 API 연동
4. `banchu.html` 수정 — 로드/저장 API 연동
