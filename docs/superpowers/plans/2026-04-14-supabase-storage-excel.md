# 하역 엑셀 Supabase Storage 이전 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render 파일시스템(ephemeral)에 저장되던 하역 엑셀 파일을 Supabase Storage로 이전해 재시작 후에도 데이터가 유지되도록 한다.

**Architecture:** `supabase-py` SDK를 추가하고, `backend/main.py`의 로컬 파일 조작 함수들을 Storage API 호출로 교체한다. 파싱 시엔 Storage에서 bytes를 다운로드해 `tempfile`에 저장 후 pandas로 읽고 즉시 삭제한다. 업로드 파일이 없을 때는 번들 fallback 파일(`backdata/(2025년) 7선석 하역률.xls`)을 그대로 사용한다.

**Tech Stack:** Python 3.11, FastAPI, supabase-py, pandas, pytest, unittest.mock

---

## 파일 변경 목록

| 파일 | 작업 |
|------|------|
| `requirements.txt` | `supabase` 패키지 추가 |
| `backend/main.py` | Storage 헬퍼 함수 추가 및 파일 조작 함수 교체 |
| `tests/test_storage.py` | 신규 — Storage 헬퍼 단위 테스트 |
| `render.yaml` | `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` env var 추가 (이미 추가됨, 확인만) |

---

### Task 1: supabase 패키지 추가

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: requirements.txt에 supabase 추가**

`requirements.txt`의 `# --- PostgreSQL` 섹션 위에 추가:

```
# --- Supabase Storage ---
supabase==2.15.1
```

- [ ] **Step 2: 로컬에서 설치 확인**

```bash
pip install supabase==2.15.1
python -c "from supabase import create_client; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: 커밋**

```bash
git add requirements.txt
git commit -m "deps: add supabase-py for Storage integration"
```

---

### Task 2: Supabase Storage 버킷 생성 (수동)

**Files:** 없음 (Supabase 대시보드 작업)

- [ ] **Step 1: 버킷 생성**

[Supabase 대시보드 → Storage](https://supabase.com/dashboard/project/tsxtukuemafrwegjorou/storage/buckets) 접속 후:

1. **New bucket** 클릭
2. Name: `unloading-excel`
3. **Public bucket: OFF** (private)
4. **Create bucket** 클릭

- [ ] **Step 2: Service Key 확인**

[Project Settings → API](https://supabase.com/dashboard/project/tsxtukuemafrwegjorou/settings/api) 에서:
- `SUPABASE_URL` = `https://tsxtukuemafrwegjorou.supabase.co`
- `SUPABASE_SERVICE_KEY` = `service_role` 키 (secret) 복사

---

### Task 3: Storage 헬퍼 함수 추가

**Files:**
- Modify: `backend/main.py`
- Create: `tests/test_storage.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_storage.py` 파일 생성:

```python
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _make_storage_file(name: str, size: int = 1024, updated_at: str = "2026-01-01T00:00:00") -> dict:
    return {"name": name, "metadata": {"size": size}, "updated_at": updated_at}


class TestUploadedStorageFiles:
    def test_returns_only_pattern_matched_files(self):
        mock_files = [
            _make_storage_file("2025_하역률.xlsx"),
            _make_storage_file("2024_하역률.xls"),
            _make_storage_file("readme.txt"),
            _make_storage_file("random.csv"),
        ]
        mock_bucket = MagicMock()
        mock_bucket.list.return_value = mock_files

        with patch("backend.main._storage_client", return_value=mock_bucket):
            from backend.main import _uploaded_storage_files
            result = _uploaded_storage_files()

        names = [f["name"] for f in result]
        assert "2025_하역률.xlsx" in names
        assert "2024_하역률.xls" in names
        assert "readme.txt" not in names
        assert "random.csv" not in names

    def test_returns_empty_on_exception(self):
        mock_bucket = MagicMock()
        mock_bucket.list.side_effect = Exception("network error")

        with patch("backend.main._storage_client", return_value=mock_bucket):
            from backend.main import _uploaded_storage_files
            result = _uploaded_storage_files()

        assert result == []


class TestUploadedExcelFileDetails:
    def test_returns_name_size_updated_at(self):
        mock_files = [
            _make_storage_file("2025_하역률.xlsx", size=2048, updated_at="2026-03-01T12:00:00"),
        ]
        mock_bucket = MagicMock()
        mock_bucket.list.return_value = mock_files

        with patch("backend.main._storage_client", return_value=mock_bucket):
            from backend.main import _uploaded_excel_file_details
            result = _uploaded_excel_file_details()

        assert len(result) == 1
        assert result[0]["name"] == "2025_하역률.xlsx"
        assert result[0]["size_bytes"] == 2048
        assert result[0]["updated_at"] == "2026-03-01T12:00:00"
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

```bash
cd /Users/jo/Desktop/프로젝트
pytest tests/test_storage.py -v
```

Expected: `ImportError` 또는 `AttributeError` — `_storage_client`, `_uploaded_storage_files` 미정의

- [ ] **Step 3: `backend/main.py`에 Storage 헬퍼 추가**

`main.py`의 `UNLOADING_XLS_PATH` 상수 아래(약 42번째 줄)에 추가:

```python
SUPABASE_BUCKET = "unloading-excel"
```

`_ensure_upload_dir` 함수(약 143번째 줄) 바로 위에 아래 함수들 추가:

```python
def _storage_client():
    """Supabase Storage 버킷 클라이언트 반환."""
    from supabase import create_client
    url = (os.environ.get("SUPABASE_URL") or "").strip()
    key = (os.environ.get("SUPABASE_SERVICE_KEY") or "").strip()
    if not url or not key:
        raise HTTPException(
            status_code=500,
            detail="SUPABASE_URL 또는 SUPABASE_SERVICE_KEY 환경변수가 설정되지 않았습니다.",
        )
    return create_client(url, key).storage.from_(SUPABASE_BUCKET)


def _uploaded_storage_files() -> list[dict[str, Any]]:
    """Storage 버킷에서 패턴에 맞는 파일 목록 반환. 오류 시 빈 리스트."""
    try:
        bucket = _storage_client()
        files = bucket.list()
        return [f for f in (files or []) if UPLOAD_NAME_PATTERN.match(f.get("name", ""))]
    except HTTPException:
        raise
    except Exception:
        return []
```

기존 `_uploaded_excel_file_details` 함수를 아래로 교체:

```python
def _uploaded_excel_file_details() -> list[dict[str, Any]]:
    files = sorted(_uploaded_storage_files(), key=lambda f: f.get("name", ""))
    return [
        {
            "name": f["name"],
            "size_bytes": (f.get("metadata") or {}).get("size", 0),
            "updated_at": f.get("updated_at", ""),
        }
        for f in files
    ]
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_storage.py -v
```

Expected: 4개 모두 PASS

- [ ] **Step 5: 커밋**

```bash
git add backend/main.py tests/test_storage.py
git commit -m "feat: add Supabase Storage helper functions"
```

---

### Task 4: 업로드·삭제·목록 엔드포인트 교체

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: `_uploaded_excel_files()` 함수를 Storage 버전으로 교체**

기존 `_uploaded_excel_files` 함수(약 147번째 줄) 전체를 아래로 교체:

```python
def _uploaded_excel_files() -> list[str]:
    """Storage 파일명 목록 반환 (하위 호환용 래퍼)."""
    return sorted(f["name"] for f in _uploaded_storage_files())
```

- [ ] **Step 2: 업로드 엔드포인트 교체**

기존 `upload_unloading_excel` 함수 전체를 아래로 교체:

```python
@app.post("/api/unloading-data/upload")
async def upload_unloading_excel(request: Request, file: UploadFile = File(...)) -> JSONResponse:
    u = _session_user(request)
    original_name = (file.filename or "").strip()
    if not original_name:
        raise HTTPException(status_code=400, detail="파일명이 비어 있습니다.")

    ext = Path(original_name).suffix.lower()
    if ext not in {".xls", ".xlsx"}:
        raise HTTPException(status_code=400, detail="엑셀 파일(.xls/.xlsx)만 업로드 가능합니다.")

    match = re.search(r"(\d{4})", original_name)
    if not match:
        raise HTTPException(status_code=400, detail="파일명에 연도(YYYY)가 포함되어야 합니다.")
    year = match.group(1)
    target_name = f"{year}_하역률{ext}"

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="빈 파일은 업로드할 수 없습니다.")

    bucket = _storage_client()
    try:
        bucket.upload(target_name, content, {"upsert": "true"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage 업로드 실패: {e}")

    if u:
        pa.audit_write(request, u, "api_unloading_upload", target_name)

    return JSONResponse(
        {
            "message": "업로드 완료",
            "saved_as": target_name,
            "uploaded_files": _uploaded_excel_files(),
            "uploaded_file_details": _uploaded_excel_file_details(),
        }
    )
```

- [ ] **Step 3: 삭제 엔드포인트 교체**

기존 `delete_uploaded_unloading_excel` 함수 전체를 아래로 교체:

```python
@app.delete("/api/unloading-data/upload/{file_name}")
def delete_uploaded_unloading_excel(request: Request, file_name: str) -> JSONResponse:
    if not UPLOAD_NAME_PATTERN.match(file_name):
        raise HTTPException(status_code=400, detail="허용되지 않은 파일명입니다.")

    bucket = _storage_client()
    try:
        bucket.remove([file_name])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage 삭제 실패: {e}")

    u = _session_user(request)
    if u:
        pa.audit_write(request, u, "api_unloading_delete", file_name)

    return JSONResponse(
        {
            "message": "삭제 완료",
            "deleted": file_name,
            "uploaded_files": _uploaded_excel_files(),
            "uploaded_file_details": _uploaded_excel_file_details(),
        }
    )
```

- [ ] **Step 4: `/api/unloading-data/meta` 엔드포인트 수정**

`unloading_data_meta` 함수 안의 `[p.name for p in _uploaded_excel_files()]` 부분을 `_uploaded_excel_files()`로 교체:

변경 전:
```python
"uploaded_files": [p.name for p in _uploaded_excel_files()],
```

변경 후:
```python
"uploaded_files": _uploaded_excel_files(),
```

- [ ] **Step 5: startup 이벤트에서 `_ensure_upload_dir()` 제거**

`debug_startup_trace` 함수에서 `_ensure_upload_dir()` 호출 줄 삭제:

변경 전:
```python
@app.on_event("startup")
def debug_startup_trace() -> None:
    _ensure_upload_dir()
    # region agent log
```

변경 후:
```python
@app.on_event("startup")
def debug_startup_trace() -> None:
    # region agent log
```

- [ ] **Step 6: 기존 테스트 통과 확인**

```bash
pytest tests/ -v
```

Expected: 모든 기존 테스트 PASS

- [ ] **Step 7: 커밋**

```bash
git add backend/main.py
git commit -m "feat: replace local file ops with Supabase Storage for excel upload/delete"
```

---

### Task 5: 데이터셋 파싱 함수 교체

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: `_get_unloading_dataset` 함수 교체**

기존 `_get_unloading_dataset` 함수 전체를 아래로 교체:

```python
def _get_unloading_dataset() -> list[dict[str, Any]]:
    import tempfile

    storage_files = _uploaded_storage_files()

    # Storage에 파일 없으면 번들 fallback 사용
    if not storage_files:
        if not UNLOADING_XLS_PATH.exists():
            return []
        all_rows: list[dict[str, Any]] = []
        for cargo, sheet in [("coal", UNLOADING_COAL_SHEET), ("nickel", UNLOADING_NICKEL_SHEET)]:
            try:
                all_rows.extend(_parse_unloading_sheet(cargo, sheet, UNLOADING_XLS_PATH))
            except Exception:
                pass
        return all_rows

    bucket = _storage_client()
    all_rows = []
    for f in sorted(storage_files, key=lambda x: x.get("name", "")):
        ext = Path(f["name"]).suffix.lower()
        tmp_path: Path | None = None
        try:
            data = bucket.download(f["name"])
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(data)
                tmp_path = Path(tmp.name)
            for cargo, sheet in [("coal", UNLOADING_COAL_SHEET), ("nickel", UNLOADING_NICKEL_SHEET)]:
                try:
                    all_rows.extend(_parse_unloading_sheet(cargo, sheet, tmp_path))
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
    return all_rows
```

- [ ] **Step 2: `_haeyang_source_fingerprint` 함수 교체**

기존 `_haeyang_source_fingerprint` 함수 전체를 아래로 교체:

```python
def _haeyang_source_fingerprint() -> str:
    """업로드/기본 엑셀 파일 변경 시 하역 챗봇 인덱스를 다시 빌드하기 위한 지문."""
    files = _uploaded_storage_files()
    if not files:
        if UNLOADING_XLS_PATH.exists():
            st = UNLOADING_XLS_PATH.stat()
            parts = [f"{UNLOADING_XLS_PATH.name}:{st.st_mtime_ns}:{st.st_size}"]
        else:
            parts = []
    else:
        parts = [
            f"{f['name']}:{f.get('updated_at', '')}:{(f.get('metadata') or {}).get('size', 0)}"
            for f in sorted(files, key=lambda x: x.get("name", ""))
        ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()
```

- [ ] **Step 3: 기존 테스트 통과 확인**

```bash
pytest tests/ -v
```

Expected: 모든 테스트 PASS

- [ ] **Step 4: 커밋**

```bash
git add backend/main.py
git commit -m "feat: parse excel from Supabase Storage via tempfile, fallback to bundled xls"
```

---

### Task 6: Render 환경변수 추가 및 배포 확인

**Files:**
- Modify: `render.yaml` (환경변수 선언 추가)

- [ ] **Step 1: render.yaml 확인**

`render.yaml`에 `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`가 없으면 추가:

```yaml
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_SERVICE_KEY
        sync: false
```

- [ ] **Step 2: Render 대시보드에 환경변수 입력**

[Render → port-ops-backend → Environment](https://dashboard.render.com) 에서:

| Key | Value |
|-----|-------|
| `SUPABASE_URL` | `https://tsxtukuemafrwegjorou.supabase.co` |
| `SUPABASE_SERVICE_KEY` | Supabase 대시보드 → Settings → API → `service_role` 키 |

- [ ] **Step 3: 변경사항 Push 후 배포 확인**

```bash
git add render.yaml
git commit -m "chore: add SUPABASE_URL and SUPABASE_SERVICE_KEY to render.yaml"
git push origin main
```

Render 대시보드에서 배포 로그 확인 — 에러 없이 `FastAPI startup executed` 출력되면 성공.

- [ ] **Step 4: 동작 검증**

1. 배포된 사이트에서 하역 데이터 엑셀 업로드
2. Render 서비스 수동 재시작 (Render 대시보드 → Manual Deploy 또는 Restart)
3. 재시작 후 하역 데이터 조회 → 업로드한 파일 데이터가 유지되는지 확인
4. Supabase Storage 버킷에 파일이 보이는지 확인: [Storage 대시보드](https://supabase.com/dashboard/project/tsxtukuemafrwegjorou/storage/buckets/unloading-excel)
