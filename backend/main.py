from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional, Union
from uuid import uuid4

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

BASE_DIR = Path(__file__).resolve().parent.parent
_SRC = BASE_DIR / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
load_dotenv(BASE_DIR / ".env")

from backend import platform_auth as pa
from backend.supply_news import get_supply_news_payload
INDEX_HTML = BASE_DIR / "index.html"
SCHEDULE_HTML = BASE_DIR / "schedule.html"
BANCHU_HTML = BASE_DIR / "banchu.html"
YARD_HTML = BASE_DIR / "yard.html"
UNLOADING_DATA_HTML = BASE_DIR / "unloading_data.html"
MAINTENANCE_PLACEHOLDER_HTML = BASE_DIR / "maintenance_placeholder.html"
PUBLIC_DIR = BASE_DIR / "public"
DEBUG_LOG_PATH = BASE_DIR / "debug-34636b.log"
UNLOADING_XLS_PATH = BASE_DIR / "backdata" / "(2025년) 7선석 하역률.xls"
UNLOADING_UPLOAD_DIR = BASE_DIR / "backdata" / "uploads"
SUPABASE_BUCKET = "unloading-excel"
_ALLOWED_ITEM_TABLES = frozenset({"schedule_items", "banchu_items"})
_ALLOWED_SIM_MODES = frozenset({"overall", "import"})


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
    if table not in _ALLOWED_ITEM_TABLES:
        raise ValueError(f"허용되지 않은 테이블: {table}")
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
    if table not in _ALLOWED_ITEM_TABLES:
        raise ValueError(f"허용되지 않은 테이블: {table}")
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


def _ensure_yard_sim_table() -> None:
    """yard_sim_settings 테이블이 없으면 생성."""
    dsn = _db_dsn()
    if not dsn:
        return
    import psycopg
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS yard_sim_settings (
                    mode TEXT PRIMARY KEY,
                    data JSONB NOT NULL,
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
        conn.commit()


def _db_get_yard_sim(mode: str) -> dict | None:
    """해당 모드 SIM 설정 반환. 없으면 None."""
    dsn = _db_dsn()
    if not dsn:
        return None
    import psycopg
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT data FROM yard_sim_settings WHERE mode = %s", (mode,))
            row = cur.fetchone()
            return row[0] if row else None


def _db_save_yard_sim(mode: str, data: dict) -> None:
    """해당 모드 SIM 설정 저장 (upsert)."""
    dsn = _db_dsn()
    if not dsn:
        return
    import psycopg
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO yard_sim_settings (mode, data, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (mode) DO UPDATE SET data = EXCLUDED.data, updated_at = NOW()
                """,
                (mode, json.dumps(data, ensure_ascii=False)),
            )
        conn.commit()


UNLOADING_COAL_SHEET = "석탄(년)"
UNLOADING_NICKEL_SHEET = "니켈(년)"

app = FastAPI(title="0327_2 Web App", version="1.0.0")


class PlatformApiAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/"):
            if path == "/api/health":
                return await call_next(request)
            if path == "/api/auth/me" and request.method == "GET":
                return await call_next(request)
            if path == "/api/auth/login" and request.method == "POST":
                return await call_next(request)
            if path == "/api/unloading-data/meta" and request.method == "GET":
                return await call_next(request)
            if path == "/api/unloading-data/summary" and request.method == "GET":
                return await call_next(request)
            if path == "/api/unloading-data/chat" and request.method == "POST":
                return await call_next(request)
            if path == "/api/schedule":
                return await call_next(request)
            if path == "/api/banchu":
                return await call_next(request)
            if path == "/api/yard-sim":
                return await call_next(request)
            u = request.session.get("user")
            if not u or not isinstance(u, str) or not str(u).strip():
                return JSONResponse({"detail": "로그인이 필요합니다."}, status_code=401)
        return await call_next(request)


app.add_middleware(PlatformApiAuthMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=pa.session_secret(),
    session_cookie="platform_session",
    same_site="lax",
    https_only=False,
    max_age=86400 * 7,
)

NO_CACHE_HTML_PATHS = {
    "/",
    "/index.html",
    "/schedule",
    "/schedule.html",
    "/banchu",
    "/banchu.html",
    "/yard",
    "/yard.html",
    "/unloading-data",
    "/unloading_data",
    "/unloading_data.html",
    "/unloading-data.html",
    "/maintenance/equipment",
    "/maintenance/history",
}

NICKEL_BRAND_MAP = {
    "ngo(mkm, nmc)": "Ngo",
    "ngo(mkm)": "Ngo",
    "karembe(smt)": "Karembe",
    "poya,ouaco": "Poya/Ouaco",
    "poya, ouaco": "Poya/Ouaco",
}

ISSUE_CATEGORY_RULES = {
    "돌발정비": ["돌발정비", "고장", "파손", "정비", "소손"],
    "설비트러블": ["설비트러블", "트러블", "비상", "사행", "trip", "r/s", "r/d", "통신에러"],
    "기상불량": ["기상", "우천", "한파", "강풍", "악천후", "폭우", "결빙", "동파"],
    "화물상태": ["화물상태", "수분", "점성", "괴광"],
    "작업대기": ["작업대기", "대기", "본선관련", "야드부족", "재고부족", "착수지연"],
    "운영변경": ["야드변경", "브랜드 변경", "이항양하", "선적", "연동"],
    "품질/검출": [
        "철편검출",
        "검출",
        "슈트막힘",
        "청소",
        "목고작업",
        "미분탄",
        "낙탄",
        "분탄",
    ],
}
ISSUE_CATEGORIES = list(ISSUE_CATEGORY_RULES.keys()) + ["기타"]
UPLOAD_NAME_PATTERN = re.compile(r"^(?P<year>\d{4})_하역률\.(?P<ext>xls|xlsx)$", re.IGNORECASE)


def _debug_log(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    payload = {
        "sessionId": "34636b",
        "runId": "pre-fix",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
        "id": f"log_{uuid4().hex}",
    }
    with DEBUG_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=True) + "\n")


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


def _ensure_upload_dir() -> None:
    UNLOADING_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _uploaded_excel_files() -> list[str]:
    """Storage 파일명 목록 반환 (하위 호환용 래퍼)."""
    return sorted(f["name"] for f in _uploaded_storage_files())


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


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def _normalize_key(value: str) -> str:
    text = re.sub(r"\s+", "", value.lower())
    return text.replace("\n", "")


def _normalize_nickel_brand(raw_brand: str) -> str:
    cleaned = _normalize_text(raw_brand).replace("\n", " ")
    compact = re.sub(r"\s+", " ", cleaned).strip()
    mapped = NICKEL_BRAND_MAP.get(_normalize_key(compact))
    if mapped:
        return mapped
    # 괄호가 있는 경우 대표 키워드만 사용해 브랜드명 정규화
    if "(" in compact:
        compact = compact.split("(")[0].strip()
    return compact or "미분류"


def _normalize_coal_brand(raw_brand: str) -> str:
    text = _normalize_text(raw_brand).replace("\n", " ")
    compact = re.sub(r"\s+", " ", text).strip()
    lower_compact = compact.lower()

    if "p-coke" in lower_compact:
        return "P-COKE"
    if "석고" in compact:
        return "석고"
    # 예: 석탄(인니), 석탄(러시아), 석탄(호주) -> 인니/러시아/호주
    matched = re.search(r"석탄\s*\(([^)]+)\)", compact)
    if matched:
        return matched.group(1).strip()
    # 괄호가 있으면 내부 라벨만 사용
    if "(" in compact and ")" in compact:
        inner = compact.split("(", 1)[1].split(")", 1)[0].strip()
        if inner:
            return inner
    return compact or "미분류"


def _classify_issue_tags(remark: str) -> list[str]:
    text = _normalize_text(remark)
    if not text:
        return []
    text = unicodedata.normalize("NFKC", text)
    lower_text = text.lower()
    tags: list[str] = []
    for category, keywords in ISSUE_CATEGORY_RULES.items():
        if any(keyword.lower() in lower_text for keyword in keywords):
            tags.append(category)
    return tags or ["기타"]


def _clean_issue_text(text: str) -> str:
    cleaned = _normalize_text(text)
    if not cleaned:
        return ""
    cleaned = unicodedata.normalize("NFKC", cleaned)
    # 시간/시각성 표현 제거 (예: 14:30, 14시, 14시30분, 2025-01-10 08:00)
    cleaned = re.sub(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", " ", cleaned)
    cleaned = re.sub(r"\b\d{1,2}\s*시(?:\s*\d{1,2}\s*분)?\b", " ", cleaned)
    cleaned = re.sub(r"\b\d{4}[./-]\d{1,2}[./-]\d{1,2}\b", " ", cleaned)
    cleaned = re.sub(r"\([^)]*\)", " ", cleaned)
    cleaned = re.sub(r"[○●■□▶▷]+", " ", cleaned)
    cleaned = re.sub(r"\b\d+\s*[=.)-]?", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.;:-")
    return cleaned


def _extract_category_issue_examples(remark: str, category: str) -> list[str]:
    cleaned = _clean_issue_text(remark)
    if not cleaned:
        return []

    # 문장을 잘게 나눠 마이너/잡다한 문구를 줄임
    parts = [
        p.strip(" ,.;:-")
        for p in re.split(r"[,\n;/]+|(?:\s+및\s+)|(?:\s+그리고\s+)", cleaned)
        if p.strip()
    ]
    if not parts:
        parts = [cleaned]

    # 카테고리별 키워드가 포함된 문구만 채택
    keywords = ISSUE_CATEGORY_RULES.get(category, [])
    selected: list[str] = []
    if keywords:
        for part in parts:
            lower = part.lower()
            if any(k.lower() in lower for k in keywords):
                selected.append(part)
    elif category == "기타":
        selected = parts

    # 기타만 완화 규칙을 허용하고, 나머지 카테고리는 엄격하게 비워둔다.
    if not selected and category == "기타":
        selected = [cleaned]

    # 너무 짧거나 정보량이 적은 문구 제거 + 중복 제거
    normalized_seen: set[str] = set()
    result: list[str] = []
    skip_tokens = ("계획정비", "일상", "재 착수", "재착수", "정기점검")
    for item in selected:
        compact = re.sub(r"\s+", " ", item).strip()
        compact = compact.strip(" ,.;:-")
        if len(compact) < 4:
            continue
        if any(tok in compact for tok in skip_tokens):
            continue
        if len(compact) > 56:
            compact = compact[:56].rstrip() + "…"
        key = compact.lower()
        if key in normalized_seen:
            continue
        normalized_seen.add(key)
        result.append(compact)
    return result


def _extract_remark_durations(remark: str) -> list[dict[str, Any]]:
    text = _normalize_text(remark)
    if not text:
        return []
    text = unicodedata.normalize("NFKC", text)

    # 예: 기상불량(우천대기) : 2:10, 일상정비(2:57), 계획정비 ... (40:00)
    pattern = re.compile(r"(?P<label>[^()\n]{0,80}?)\(\s*(?P<hour>\d{1,3})\s*:\s*(?P<minute>\d{1,2})\s*\)")
    matches: list[dict[str, Any]] = []
    for m in pattern.finditer(text):
        try:
            hour = int(m.group("hour"))
            minute = int(m.group("minute"))
        except (TypeError, ValueError):
            continue
        if minute < 0 or minute >= 60:
            continue
        label = re.sub(r"\s+", " ", (m.group("label") or "")).strip(" :-,")
        total_minutes = hour * 60 + minute
        if total_minutes <= 0:
            continue
        matches.append(
            {
                "label": label,
                "hours": hour,
                "minutes": minute,
                "total_minutes": total_minutes,
                "time_hhmm": f"{hour}:{minute:02d}",
            }
        )
    return matches


def _parse_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)
    text = str(value).replace(",", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _reference_datetime_for_unloading_row(row: Any) -> Optional[pd.Timestamp]:
    """실적·이슈 집계 기준 시각. 완료 시점 우선, 없으면 착수(미기재·타 년도 파일 호환)."""
    end_dt = pd.to_datetime(row.get("완료"), errors="coerce")
    if pd.notna(end_dt):
        return pd.Timestamp(end_dt)
    start_dt = pd.to_datetime(row.get("착수"), errors="coerce")
    if pd.notna(start_dt):
        return pd.Timestamp(start_dt)
    return None


def _parse_unloading_sheet(cargo_type: str, sheet_name: str, source_path: Path) -> list[dict[str, Any]]:
    engine = "xlrd" if source_path.suffix.lower() == ".xls" else "openpyxl"
    df = pd.read_excel(source_path, sheet_name=sheet_name, header=1, engine=engine)
    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        vessel_name = _normalize_text(row.get("선박명"))
        raw_brand = _normalize_text(row.get("품종"))
        rate = _parse_float(row.get("하역율"))
        if not vessel_name or not raw_brand or rate is None:
            continue

        ref_dt = _reference_datetime_for_unloading_row(row)
        if ref_dt is None:
            continue
        year = int(ref_dt.year)
        month = int(ref_dt.month)

        if cargo_type == "coal":
            volume = _parse_float(row.get("하역량(톤)"))
            brand = _normalize_coal_brand(raw_brand)
        else:
            volume = _parse_float(row.get("B/L량(톤)"))
            brand = _normalize_nickel_brand(raw_brand)
        if volume is None:
            continue

        remark = _normalize_text(row.get("비고"))
        if remark:
            remark = unicodedata.normalize("NFKC", remark)
        issue_tags = _classify_issue_tags(remark)
        remark_durations = _extract_remark_durations(remark)
        rows.append(
            {
                "cargo_type": cargo_type,
                "year": year,
                "month": month,
                "vessel_name": vessel_name,
                "brand": brand,
                "volume_ton": volume,
                "unloading_rate": rate,
                "remark": remark,
                "issue_tags": issue_tags,
                "remark_durations": remark_durations,
                "source_file": source_path.name,
            }
        )
    return rows


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


def _filter_rows(
    rows: list[dict[str, Any]],
    cargo_type: str,
    start_year: Optional[int],
    end_year: Optional[int],
    brands: Optional[list[str]],
) -> list[dict[str, Any]]:
    filtered = [r for r in rows if r["cargo_type"] == cargo_type]
    if start_year is not None:
        filtered = [r for r in filtered if r["year"] >= start_year]
    if end_year is not None:
        filtered = [r for r in filtered if r["year"] <= end_year]
    if brands:
        brand_keywords = [b.strip().lower() for b in brands if b.strip()]
        filtered = [
            r for r in filtered if any(keyword in str(r["brand"]).lower() for keyword in brand_keywords)
        ]
    return filtered


def _aggregate_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "kpis": {"total_volume_ton": 0, "total_vessels": 0, "avg_unloading_rate": 0, "issue_count": 0},
            "monthly": [],
            "issue_breakdown": [{"category": c, "count": 0} for c in ISSUE_CATEGORIES],
            "issue_examples": {},
            "brand_table": [],
            "duration_overview": {
                "count": 0,
                "total_minutes": 0,
                "avg_minutes": 0,
                "avg_time_hhmm": "0:00",
                "max_minutes": 0,
                "max_time_hhmm": "0:00",
                "top_duration_samples": [],
            },
        }

    vessel_names = {r["vessel_name"] for r in rows}
    total_volume = sum(r["volume_ton"] for r in rows)
    avg_rate = sum(r["unloading_rate"] for r in rows) / len(rows)

    monthly_map: dict[tuple[int, int], dict[str, Any]] = {}
    issue_counter = {c: 0 for c in ISSUE_CATEGORIES}
    issue_examples: dict[str, set[str]] = {c: set() for c in ISSUE_CATEGORIES}
    brand_map: dict[str, dict[str, Any]] = {}
    all_durations: list[dict[str, Any]] = []
    for r in rows:
        ym = (r["year"], r["month"])
        if ym not in monthly_map:
            monthly_map[ym] = {"year": r["year"], "month": r["month"], "volume_ton": 0.0, "rates": []}
        monthly_map[ym]["volume_ton"] += r["volume_ton"]
        monthly_map[ym]["rates"].append(r["unloading_rate"])

        tags = r["issue_tags"] or []
        if not tags:
            issue_counter["기타"] += 1
            if r["remark"]:
                for ex in _extract_category_issue_examples(r["remark"], "기타"):
                    issue_examples["기타"].add(ex)
        for tag in tags:
            resolved_tag = tag if tag in issue_counter else "기타"
            issue_counter[resolved_tag] += 1
            if r["remark"]:
                for ex in _extract_category_issue_examples(r["remark"], resolved_tag):
                    issue_examples[resolved_tag].add(ex)

        brand = r["brand"]
        if brand not in brand_map:
            brand_map[brand] = {"brand": brand, "volume_ton": 0.0, "rates": [], "vessels": set(), "issue_count": 0, "issues": {}}
        brand_row = brand_map[brand]
        brand_row["volume_ton"] += r["volume_ton"]
        brand_row["rates"].append(r["unloading_rate"])
        brand_row["vessels"].add(r["vessel_name"])
        brand_row["issue_count"] += len(tags)
        for tag in tags:
            brand_row["issues"][tag] = brand_row["issues"].get(tag, 0) + 1
        for d in r.get("remark_durations") or []:
            all_durations.append(
                {
                    "cargo_type": r.get("cargo_type"),
                    "year": r.get("year"),
                    "month": r.get("month"),
                    "brand": r.get("brand"),
                    "label": d.get("label") or "",
                    "time_hhmm": d.get("time_hhmm"),
                    "hours": d.get("hours"),
                    "minutes": d.get("minutes"),
                    "total_minutes": d.get("total_minutes"),
                    "remark": r.get("remark"),
                }
            )

    monthly = []
    for _, item in sorted(monthly_map.items(), key=lambda x: (x[0][0], x[0][1])):
        monthly.append(
            {
                "year": item["year"],
                "month": item["month"],
                "volume_ton": round(item["volume_ton"], 2),
                "avg_unloading_rate": round(sum(item["rates"]) / len(item["rates"]), 2) if item["rates"] else 0,
            }
        )

    issue_breakdown = [{"category": c, "count": issue_counter[c]} for c in ISSUE_CATEGORIES]
    issue_examples_payload = {
        category: sorted(list(examples))[:5]
        for category, examples in issue_examples.items()
        if examples
    }

    brand_table = []
    for b in brand_map.values():
        top_issue = "없음"
        if b["issues"]:
            top_issue = sorted(b["issues"].items(), key=lambda x: x[1], reverse=True)[0][0]
        brand_table.append(
            {
                "brand": b["brand"],
                "volume_ton": round(b["volume_ton"], 2),
                "avg_unloading_rate": round(sum(b["rates"]) / len(b["rates"]), 2) if b["rates"] else 0,
                "vessel_count": len(b["vessels"]),
                "issue_count": b["issue_count"],
                "top_issue": top_issue,
            }
        )
    brand_table.sort(key=lambda x: x["volume_ton"], reverse=True)

    duration_count = len(all_durations)
    duration_total_minutes = sum(int(d.get("total_minutes") or 0) for d in all_durations)
    duration_avg_minutes = (duration_total_minutes / duration_count) if duration_count else 0
    duration_max_minutes = max((int(d.get("total_minutes") or 0) for d in all_durations), default=0)
    top_duration_samples = sorted(all_durations, key=lambda x: int(x.get("total_minutes") or 0), reverse=True)[:12]

    def to_hhmm(total_minutes: float) -> str:
        mins = int(round(total_minutes))
        h = mins // 60
        m = mins % 60
        return f"{h}:{m:02d}"

    return {
        "kpis": {
            "total_volume_ton": round(total_volume, 2),
            "total_vessels": len(vessel_names),
            "avg_unloading_rate": round(avg_rate, 2),
            "issue_count": sum(issue_counter.values()),
        },
        "monthly": monthly,
        "issue_breakdown": issue_breakdown,
        "issue_examples": issue_examples_payload,
        "brand_table": brand_table,
        "duration_overview": {
            "count": duration_count,
            "total_minutes": duration_total_minutes,
            "avg_minutes": round(duration_avg_minutes, 2),
            "avg_time_hhmm": to_hhmm(duration_avg_minutes),
            "max_minutes": duration_max_minutes,
            "max_time_hhmm": to_hhmm(duration_max_minutes),
            "top_duration_samples": top_duration_samples,
        },
    }


def _build_dashboard_chat_context(
    summary: dict[str, Any],
    cargo_type: str,
    start_year: Optional[int],
    end_year: Optional[int],
    brands: str,
    cargo_summaries: Optional[dict[str, Any]] = None,
) -> str:
    kpis = summary.get("kpis", {})
    top_brands = summary.get("brand_table", [])[:8]
    monthly = summary.get("monthly", [])
    latest_monthly = monthly[-6:] if len(monthly) > 6 else monthly
    issue_breakdown = summary.get("issue_breakdown", [])
    issue_examples = summary.get("issue_examples", {})
    duration_overview = summary.get("duration_overview", {})
    context = {
        "filter": {
            "cargo_type": cargo_type,
            "start_year": start_year,
            "end_year": end_year,
            "brands": brands,
        },
        "kpis": kpis,
        "kpis_rounded_for_chat": {
            "total_volume_ton": int(round(float(kpis.get("total_volume_ton", 0) or 0))),
            "total_vessels": int(round(float(kpis.get("total_vessels", 0) or 0))),
            "avg_unloading_rate": int(round(float(kpis.get("avg_unloading_rate", 0) or 0))),
            "issue_count": int(round(float(kpis.get("issue_count", 0) or 0))),
        },
        "latest_monthly": latest_monthly,
        "top_brands": top_brands,
        "issue_breakdown": issue_breakdown,
        "issue_examples": issue_examples,
        "duration_overview": duration_overview,
        "cargo_summaries": cargo_summaries or {},
    }
    return json.dumps(context, ensure_ascii=False)


def _chat_completion_with_openai(
    question: str,
    context_json: str,
    history: list[dict[str, str]] | None = None,
    force_hybrid_style: bool = False,
) -> Optional[str]:
    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return None
    user_prompt = (
        "응답은 반드시 JSON 객체 형식으로만 반환하세요:\n"
        '{"found": true|false, "answer": "한국어 답변", "evidence": ["근거1", "근거2"]}\n\n'
        f"질문: {question}"
    )
    hybrid_style_rules = ""
    if force_hybrid_style:
        hybrid_style_rules = (
            "\n"
            "## 하이브리드 응답 스타일(강제)\n"
            "9. bySpecies, byVessel, totalBL, avgRate, count, entry 같은 내부 키워드는 답변/근거에 노출하지 않는다.\n"
            "10. 질문이 니켈 품종 결과를 요구하면 품종명 + 물량(톤)만 노출한다. 평균/건수/내부 키는 생략한다.\n"
            "11. 근거(evidence)도 자연어로만 작성하고 내부 키명은 포함하지 않는다.\n"
        )

    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": (
                "당신은 7선석 항만 하역 운영 데이터를 분석하는 전문 어시스턴트입니다.\n\n"
                "## 사전 집계된 통계 데이터\n"
                "아래 JSON은 원본 데이터를 코드로 집계한 정확한 수치입니다.\n"
                "이 수치를 기준으로 답변하십시오. 절대 추측하거나 직접 계산하지 마십시오.\n\n"
                f"{context_json}\n\n"
                "## 답변 규칙\n"
                "1. 수치는 반드시 위 JSON 데이터에서 조회하여 인용한다.\n"
                "2. 랭킹 질문(몇 번째로 많은/적은)은 bySpecies, byVessel 배열의 인덱스를 사용한다.\n"
                "3. 이전 대화의 조건(연도, 품종, 월 등)을 이어받아 답변한다.\n"
                "4. 모르는 정보는 found=false로 반환하고 answer에는 '해당 데이터가 없습니다'를 사용한다. 추측하지 않는다.\n"
                "5. 숫자는 천 단위 쉼표를 붙여 가독성 있게 표시한다 (예: 1,076,568 t).\n"
                "6. 답변은 간결하게 1~3문장으로 한다.\n"
                "7. DB(업로드 데이터)에 없는 사실, 외부 지식, 일반 상식으로 내용을 보충하지 않는다.\n"
                "8. 질문이 애매하면 의도를 확인하는 한 문장을 answer에 넣고 found=false로 반환한다."
                f"{hybrid_style_rules}"
            ),
        },
    ]
    for turn in history or []:
        role = str(turn.get("role") or "")
        content = str(turn.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_prompt})

    body = json.dumps(
        {
            "model": "gpt-5-mini",
            "messages": messages,
            "response_format": {"type": "json_object"},
            "max_completion_tokens": 2000,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
        content = str(content).strip()
        if not content:
            return None
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start >= 0 and end > start:
                parsed = json.loads(content[start : end + 1])
            else:
                return None

        found = bool(parsed.get("found"))
        answer = str(parsed.get("answer") or "").strip()
        evidence = parsed.get("evidence")
        evidence_lines: list[str] = []
        if isinstance(evidence, list):
            for ev in evidence[:3]:
                txt = str(ev).strip()
                if txt:
                    evidence_lines.append(txt)
        if not found:
            return "현재 업로드된 데이터에서 확인되지 않습니다."
        if not answer:
            return None
        if evidence_lines:
            return f"{answer}\n근거: " + " / ".join(evidence_lines)
        return answer
    except (urllib.error.URLError, OSError, TimeoutError, KeyError, TypeError, json.JSONDecodeError):
        return None


def _format_numbers_with_commas(text: str) -> str:
    def format_int(value: int, raw_token: str) -> str:
        # 연도(1900~2100)처럼 보이는 4자리 수는 콤마 처리하지 않음
        if 1900 <= value <= 2100 and len(raw_token) == 4:
            return raw_token
        return f"{value:,}"

    def repl_decimal(match: re.Match[str]) -> str:
        token = match.group(0)
        try:
            rounded = int(round(float(token)))
            return format_int(rounded, str(rounded))
        except ValueError:
            return token

    def repl(match: re.Match[str]) -> str:
        token = match.group(0)
        try:
            value = int(token)
            return format_int(value, token)
        except ValueError:
            return token

    # 소수점 숫자는 반올림 정수로 변환 후 표기
    text = re.sub(r"(?<![\d.])\d+\.\d+(?![\d.])", repl_decimal, text)
    # 소수점이 없는 4자리 이상 정수는 천 단위 콤마 적용
    return re.sub(r"(?<![\d.])\d{4,}(?![\d.])", repl, text)


def _is_ambiguous_chat_question(question: str) -> bool:
    q = _normalize_text(question)
    if not q:
        return True
    # 한 글자 입력(예: "ㅇ", "작")이나 지나치게 짧은 토큰은 의도 파악이 어려움
    stripped = re.sub(r"\s+", "", q)
    if len(stripped) <= 1:
        return True
    # 숫자/기호 위주 짧은 입력은 질문으로 보기 어려움
    if re.fullmatch(r"[\W_0-9]+", stripped):
        return True
    return False


def _should_force_hybrid_question(question: str) -> bool:
    """
    이슈 조건 + 수치/집계를 함께 묻는 질문은 rule-based를 건너뛰고
    하이브리드 체인(SQL+RAG)으로 우선 라우팅한다.
    """
    q = _normalize_text(question).lower()
    if not q:
        return False

    issue_keywords = (
        "수분",
        "점성",
        "대형괴광",
        "죽광",
        "철편",
        "돌발정비",
        "기상불량",
        "우천",
        "한파",
        "snnc",
        "트러블",
        "지연",
        "이슈",
        "문제",
    )
    metric_keywords = (
        "평균",
        "합계",
        "총",
        "최대",
        "최소",
        "최고",
        "최저",
        "상위",
        "하위",
        "순위",
        "몇",
        "얼마",
        "하역률",
        "소요일",
        "지연시간",
        "실적",
        "건수",
    )
    list_only_tokens = ("목록", "리스트", "품종은", "선박은", "어떤 선박", "어느 선박", "어떤 품종", "어느 품종")
    detail_only_tokens = ("원인", "이유", "왜", "사례", "정리", "설명", "경위", "자세히", "상세")

    has_issue = any(k in q for k in issue_keywords)
    has_metric = any(k in q for k in metric_keywords)
    if not (has_issue and has_metric):
        return False

    # 목록형/상세원인형은 각각 SQL/RAG로 보내는 기존 정책 유지
    if any(t in q for t in list_only_tokens):
        return False
    if any(t in q for t in detail_only_tokens) and not any(t in q for t in ("평균", "합계", "총", "순위", "하역률", "소요일", "지연시간")):
        return False
    return True


def _infer_scope_from_question(question: str) -> tuple[Optional[str], Optional[int]]:
    q = _normalize_text(question).lower()
    cargo: Optional[str] = None
    if any(k in q for k in ("니켈", "nickel")):
        cargo = "nickel"
    elif any(k in q for k in ("석탄", "coal")):
        cargo = "coal"

    year: Optional[int] = None
    m = re.search(r"(20\d{2})\s*년", q)
    if not m:
        m = re.search(r"\b(20\d{2})\b", q)
    if m:
        y = int(m.group(1))
        if 2000 <= y <= 2100:
            year = y
    return cargo, year


def _detect_request_type(q: str) -> str:
    if re.search(r"랭킹|순위|많[이은]|적[은이]|높[은이]|낮[은이]|상위|하위|번째", q):
        return "ranking"
    if re.search(r"평균|평균값", q):
        return "average"
    if re.search(r"합계|총|전체", q):
        return "total"
    if re.search(r"월별|월마다", q):
        return "monthly"
    if re.search(r"연도별|년도별|연간", q):
        return "yearly"
    if re.search(r"선박|배", q):
        return "vessel"
    if re.search(r"품종|광종|브랜드", q):
        return "species"
    return "general"


def _parse_query(question: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    q = _normalize_text(question)
    q_lower = q.lower()
    cargo_type, year = _infer_scope_from_question(question)

    month: Optional[int] = None
    month_match = re.search(r"(\d{1,2})\s*월", q_lower)
    if month_match:
        m = int(month_match.group(1))
        if 1 <= m <= 12:
            month = m

    species: Optional[str] = None
    vessel: Optional[str] = None

    def norm_text(value: str) -> str:
        return re.sub(r"[^0-9a-z가-힣]+", "", (value or "").lower())
    all_species = sorted({str((r.get("brand") or "")).strip() for r in rows if str((r.get("brand") or "")).strip()}, key=len, reverse=True)
    all_vessels = sorted(
        {str((r.get("vessel_name") or "")).strip() for r in rows if str((r.get("vessel_name") or "")).strip()},
        key=len,
        reverse=True,
    )
    q_fold = q_lower.casefold()
    q_norm = norm_text(q_lower)
    for s in all_species:
        s_fold = s.casefold()
        s_norm = norm_text(s)
        if s_fold in q_fold or (s_norm and s_norm in q_norm):
            species = s
            break
    for v in all_vessels:
        v_fold = v.casefold()
        v_norm = norm_text(v)
        if v_fold in q_fold or (v_norm and v_norm in q_norm):
            vessel = v
            break

    return {
        "year": year,
        "month": month,
        "species": species,
        "vessel": vessel,
        "cargo_type": cargo_type,
        "request_type": _detect_request_type(q_lower),
    }


def _merge_query_with_history(parsed: dict[str, Any], history: list[dict[str, str]], rows: list[dict[str, Any]]) -> dict[str, Any]:
    merged = dict(parsed)
    for turn in reversed(history):
        if turn.get("role") != "user":
            continue
        prev = _parse_query(turn.get("content") or "", rows)
        for key in ("year", "month", "species", "vessel", "cargo_type"):
            if merged.get(key) is None and prev.get(key) is not None:
                merged[key] = prev[key]
        if all(merged.get(k) is not None for k in ("year", "month", "species", "vessel", "cargo_type")):
            break
    return merged


def _compute_dynamic_chat_summary(rows: list[dict[str, Any]], filters: dict[str, Any]) -> dict[str, Any]:
    year = filters.get("year")
    month = filters.get("month")
    species = filters.get("species")
    vessel = filters.get("vessel")
    cargo_type = filters.get("cargo_type")

    data = rows
    if cargo_type in {"coal", "nickel"}:
        data = [r for r in data if r.get("cargo_type") == cargo_type]
    if year is not None:
        data = [r for r in data if int(r.get("year") or 0) == int(year)]
    if month is not None:
        data = [r for r in data if int(r.get("month") or 0) == int(month)]
    if species:
        data = [r for r in data if str(r.get("brand") or "") == str(species)]
    if vessel:
        data = [r for r in data if str(r.get("vessel_name") or "") == str(vessel)]

    def sum_key(items: list[dict[str, Any]], key: str) -> float:
        return sum(float(i.get(key) or 0) for i in items)

    def avg_key(items: list[dict[str, Any]], key: str) -> float:
        return (sum_key(items, key) / len(items)) if items else 0.0

    def avg_duration_minutes(items: list[dict[str, Any]]) -> int:
        vals: list[int] = []
        for row in items:
            for d in row.get("remark_durations") or []:
                mins = int(d.get("total_minutes") or 0)
                if mins > 0:
                    vals.append(mins)
        return int(round(sum(vals) / len(vals))) if vals else 0

    def group(items: list[dict[str, Any]], key: str, sort_name_asc: bool = False) -> list[dict[str, Any]]:
        g: dict[str, list[dict[str, Any]]] = {}
        for row in items:
            k = str(row.get(key) or "").strip()
            if not k:
                continue
            g.setdefault(k, []).append(row)
        result: list[dict[str, Any]] = []
        for name, grp in g.items():
            result.append(
                {
                    "rank": 0,
                    "name": name,
                    "count": len(grp),
                    "totalBL": int(round(sum_key(grp, "volume_ton"))),
                    "avgRate": int(round(avg_key(grp, "unloading_rate"))),
                }
            )
        if sort_name_asc:
            result.sort(key=lambda x: x["name"])
        else:
            result.sort(key=lambda x: x.get("totalBL", 0), reverse=True)
        for i, row in enumerate(result):
            row["rank"] = i + 1
        return result

    by_species = group(data, "brand", sort_name_asc=False)
    by_vessel = group(data, "vessel_name", sort_name_asc=False)
    by_month = group(data, "month", sort_name_asc=True)
    by_year = group(data, "year", sort_name_asc=True)
    top_unloading_rate = sorted(data, key=lambda r: float(r.get("unloading_rate") or 0), reverse=True)[:5]
    bottom_unloading_rate = sorted(data, key=lambda r: float(r.get("unloading_rate") or 0))[:5]

    return {
        "meta": {
            "totalCount": len(data),
            "totalBL": int(round(sum_key(data, "volume_ton"))),
            "avgUnloadingRate": int(round(avg_key(data, "unloading_rate"))),
            "avgDurationMinutes": avg_duration_minutes(data),
            "filters": {
                "year": year,
                "month": month,
                "species": species,
                "vessel": vessel,
                "cargo_type": cargo_type,
            },
        },
        "bySpecies": by_species,
        "byVessel": by_vessel,
        "byMonth": by_month,
        "byYear": by_year,
        "topUnloadingRate": [
            {
                "vessel": r.get("vessel_name"),
                "species": r.get("brand"),
                "year": r.get("year"),
                "month": r.get("month"),
                "unloading_rate": int(round(float(r.get("unloading_rate") or 0))),
                "volume_ton": int(round(float(r.get("volume_ton") or 0))),
            }
            for r in top_unloading_rate
        ],
        "bottomUnloadingRate": [
            {
                "vessel": r.get("vessel_name"),
                "species": r.get("brand"),
                "year": r.get("year"),
                "month": r.get("month"),
                "unloading_rate": int(round(float(r.get("unloading_rate") or 0))),
                "volume_ton": int(round(float(r.get("volume_ton") or 0))),
            }
            for r in bottom_unloading_rate
        ],
    }


def _normalize_chat_history(history_raw: Any) -> list[dict[str, str]]:
    history: list[dict[str, str]] = []
    if not isinstance(history_raw, list):
        return history
    # 최근 10턴(사용자/어시스턴트 20개 메시지)만 유지
    for item in history_raw[-20:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "")
        content = str(item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            history.append({"role": role, "content": content})
    return history


def _infer_scope_from_history(history: list[dict[str, str]]) -> tuple[Optional[str], Optional[int]]:
    cargo: Optional[str] = None
    year: Optional[int] = None
    # 최근 맥락 우선
    for turn in reversed(history):
        if turn.get("role") != "user":
            continue
        c, y = _infer_scope_from_question(turn.get("content") or "")
        if cargo is None and c is not None:
            cargo = c
        if year is None and y is not None:
            year = y
        if cargo is not None and year is not None:
            break
    return cargo, year


def _infer_rank_from_question(question: str) -> Optional[int]:
    q = _normalize_text(question).lower()
    if not q:
        return None

    # 숫자 + 번째 (예: 2번째, 3 번째)
    m = re.search(r"(\d+)\s*번째", q)
    if m:
        rank = int(m.group(1))
        return rank if rank >= 1 else None

    # 서수 표현
    ordinal_map = {
        "첫번째": 1,
        "첫째": 1,
        "한번째": 1,
        "두번째": 2,
        "둘째": 2,
        "세번째": 3,
        "셋째": 3,
        "네번째": 4,
        "넷째": 4,
        "다섯번째": 5,
        "여섯번째": 6,
        "일곱번째": 7,
        "여덟번째": 8,
        "아홉번째": 9,
        "열번째": 10,
    }
    for token, rank in ordinal_map.items():
        if token in q:
            return rank

    if any(t in q for t in ("가장 많이", "최다", "top")):
        return 1
    return None


def _is_brand_rank_question(question: str) -> bool:
    q = _normalize_text(question).lower()
    if not q:
        return False
    return any(t in q for t in ("품종", "브랜드")) and any(
        t in q for t in ("많이", "최다", "top", "번째", "다음", "그 다음")
    )


def _infer_rank_from_history(history: list[dict[str, str]]) -> Optional[int]:
    for turn in reversed(history):
        if turn.get("role") != "user":
            continue
        content = turn.get("content") or ""
        if not _is_brand_rank_question(content):
            continue
        rank = _infer_rank_from_question(content)
        if rank is not None:
            return rank
        if any(t in content for t in ("그 다음", "다음", "next")):
            # 과거 질문이 "그 다음" 형태면 최소 2위로 간주
            return 2
    return None


def _build_rule_based_chat_answer(
    question: str,
    rows: list[dict[str, Any]],
    history: Optional[list[dict[str, str]]] = None,
    parsed_filters: Optional[dict[str, Any]] = None,
) -> Optional[str]:
    q = _normalize_text(question).lower()
    cargo, year = _infer_scope_from_question(question)
    hist_cargo, hist_year = _infer_scope_from_history(history or [])
    month = (parsed_filters or {}).get("month")
    species = (parsed_filters or {}).get("species")
    vessel = (parsed_filters or {}).get("vessel")

    # 명시적 여집합/제외 질의는 현재 질문을 우선 해석
    has_exclusion = any(t in q for t in ("제외", "빼고", "-", "차집합", "여집합"))
    if not has_exclusion:
        if cargo is None:
            cargo = hist_cargo
        if year is None:
            year = hist_year

    # 예: "석탄-니켈", "니켈 제외" 같은 명시 질의는 반대 화종으로 해석(현재 데이터는 coal/nickel 2개 범주)
    if has_exclusion:
        if ("석탄" in q and "니켈" in q and "-" in q) or ("니켈" in q and "제외" in q):
            cargo = "coal"
        elif ("니켈" in q and "석탄" in q and "-" in q) or ("석탄" in q and "제외" in q):
            cargo = "nickel"

    scoped = rows
    if cargo in {"coal", "nickel"}:
        scoped = [r for r in scoped if r.get("cargo_type") == cargo]
    if year is not None:
        scoped = [r for r in scoped if int(r.get("year") or 0) == year]
    if month is not None:
        scoped = [r for r in scoped if int(r.get("month") or 0) == int(month)]
    if species:
        scoped = [r for r in scoped if str(r.get("brand") or "") == str(species)]
    if vessel:
        scoped = [r for r in scoped if str(r.get("vessel_name") or "") == str(vessel)]
    if not scoped:
        return "현재 업로드된 데이터에서 확인되지 않습니다."

    summary = _aggregate_summary(scoped)
    k = summary.get("kpis", {})
    brand_table = summary.get("brand_table", [])
    scope_parts: list[str] = []
    if year is not None:
        scope_parts.append(f"{year}년")
    if month is not None:
        scope_parts.append(f"{int(month)}월")
    if cargo == "nickel":
        scope_parts.append("니켈")
    elif cargo == "coal":
        scope_parts.append("석탄")
    if species:
        scope_parts.append(str(species))
    if vessel:
        scope_parts.append(str(vessel))
    scope_label = (" ".join(scope_parts) + " 기준") if scope_parts else "업로드된 전체 데이터 기준"

    def asks_average_rate(text: str) -> bool:
        # 원인·이유·분석·이슈사항·순위 맥락은 평균 조회가 아님
        if any(kw in text for kw in ("원인", "이유", "왜", "분석", "때문", "이슈사항", "이슈 사항", "이슈내용", "이슈 내용")):
            return False
        if any(t in text for t in ("평균 하역률", "평균하역률", "평균 t/d", "평균 td")):
            return True
        if "하역률" in text:
            ranking_signals = ("가장", "제일", "최고", "최저", "낮", "높", "순위", "랭킹", "상위", "하위")
            if any(s in text for s in ranking_signals):
                return False
            return True
        return False

    def asks_total_volume(text: str) -> bool:
        # 구어체/동사형 질의 포함: "반입했어", "얼마나 들어왔", "몇 톤"
        direct_tokens = (
            "총 하역량",
            "반입량",
            "물량",
            "volume",
            "톤수",
            "몇톤",
            "몇 톤",
            "얼마나",
        )
        action_tokens = ("반입", "들어왔", "들어온", "입항", "실렸", "적재")
        if any(t in text for t in direct_tokens):
            return True
        if any(a in text for a in action_tokens) and ("톤" in text or "물량" in text or "얼마" in text):
            return True
        return False

    def to_hhmm(total_minutes: int) -> str:
        safe = max(0, int(total_minutes))
        h = safe // 60
        m = safe % 60
        return f"{h}:{m:02d}"

    def asks_issue_details(text: str) -> bool:
        detail_tokens = (
            "이슈사항",
            "어떤 이슈",
            "무슨 이슈",
            "이슈 내용",
            "이슈 상세",
            "상세 이슈",
            "상세 내용",
            "세부 내용",
            "내역",
            "어떤 문제가",
            "문제사항",
        )
        if any(t in text for t in detail_tokens):
            return True
        # '이슈'라는 단어가 없더라도 상세 조회 뉘앙스면 상세 응답 경로로 유도
        nuance_tokens = ("알려줘", "보여줘", "뭐야", "무엇", "어떤", "자세히", "상세히")
        category_hint = any(cat in text for cat in ISSUE_CATEGORY_RULES.keys()) or any(
            kw in text for kws in ISSUE_CATEGORY_RULES.values() for kw in kws
        )
        if category_hint and any(n in text for n in nuance_tokens):
            return True
        if any(n in text for n in nuance_tokens) and any(k in text for k in ("이슈", "문제", "트러블")):
            return True
        return False

    def infer_requested_issue_category(text: str) -> Optional[str]:
        """질문에 특정 이슈 유형이 하나만 드러날 때만 카테고리를 좁힌다. 비고 전문을 붙여 넣어
        여러 유형(기상+품질 등)이 동시에 매칭되면 None을 반환해 요약에 모두 노출한다."""
        folded = unicodedata.normalize("NFKC", _normalize_text(text)).lower()
        matched: list[str] = []
        seen: set[str] = set()
        for category, keywords in ISSUE_CATEGORY_RULES.items():
            hit = category.lower() in folded
            if not hit:
                hit = any(unicodedata.normalize("NFKC", k).lower() in folded for k in keywords)
            if hit and category not in seen:
                matched.append(category)
                seen.add(category)
        if len(matched) == 1:
            return matched[0]
        return None

    def summarize_issue_details(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # 카테고리별 시간/건수 집계: "돌발정비 총 6:45 (2건)" 형태를 만들기 위함
        bucket: dict[str, dict[str, Any]] = {}
        for row in items:
            remark_durations = row.get("remark_durations") or []
            if remark_durations:
                for d in remark_durations:
                    label = str(d.get("label") or "")
                    mins = int(d.get("total_minutes") or 0)
                    hhmm = str(d.get("time_hhmm") or to_hhmm(mins))
                    tags = _classify_issue_tags(label) or row.get("issue_tags") or ["기타"]
                    tag = next((t for t in tags if t and t != "기타"), tags[0] if tags else "기타")
                    if tag not in bucket:
                        bucket[tag] = {"minutes": 0, "count": 0, "details": [], "seen": set()}
                    bucket[tag]["minutes"] += max(0, mins)
                    bucket[tag]["count"] += 1
                    detail_label = re.sub(r"^[\-\u2022○●■□▶▷\s:]+", "", label).strip()
                    if not detail_label:
                        detail_label = tag
                    detail_text = f"{detail_label} ({hhmm})"
                    key = detail_text.lower()
                    if key not in bucket[tag]["seen"]:
                        bucket[tag]["seen"].add(key)
                        bucket[tag]["details"].append(detail_text)
            else:
                tags = row.get("issue_tags") or ["기타"]
                remark = str(row.get("remark") or "")
                for tag in tags:
                    resolved = tag or "기타"
                    if resolved not in bucket:
                        bucket[resolved] = {"minutes": 0, "count": 0, "details": [], "seen": set()}
                    bucket[resolved]["count"] += 1
                    examples = _extract_category_issue_examples(remark, resolved)
                    for ex in examples:
                        key = ex.lower()
                        if key not in bucket[resolved]["seen"]:
                            bucket[resolved]["seen"].add(key)
                            bucket[resolved]["details"].append(ex)
                    if remark and not examples:
                        fallback = _clean_issue_text(remark)
                        if len(fallback) >= 4:
                            fb_key = fallback.lower()
                            if fb_key not in bucket[resolved]["seen"]:
                                bucket[resolved]["seen"].add(fb_key)
                                label = fallback if len(fallback) <= 80 else fallback[:80].rstrip() + "…"
                                bucket[resolved]["details"].append(label)

        rows_out = [
            {
                "category": cat,
                "total_minutes": v["minutes"],
                "count": v["count"],
                "details": v["details"],
            }
            for cat, v in bucket.items()
            if v["count"] > 0
        ]
        rows_out.sort(key=lambda x: (x["total_minutes"], x["count"]), reverse=True)
        return rows_out

    # 이슈사항 상세 조회는 평균 하역률 조회보다 먼저 처리 (우선순위 충돌 방지)
    if asks_issue_details(q):
        issue_rows = summarize_issue_details(scoped)
        requested_category = infer_requested_issue_category(q)
        if requested_category:
            issue_rows = [r for r in issue_rows if r.get("category") == requested_category]
        if not issue_rows:
            return f"{scope_label} 이슈사항은 확인되지 않습니다."
        if requested_category and issue_rows:
            row = issue_rows[0]
            lines = [f"{scope_label} {row['category']} 총 {to_hhmm(int(row['total_minutes']))} ({int(row['count'])}건)"]
            for d in row.get("details", [])[:5]:
                lines.append(f"- {d}")
            return "\n".join(lines)

        lines = [f"{scope_label} 주요 이슈 상세입니다."]
        for row in issue_rows[:5]:
            lines.append(f"{row['category']} 총 {to_hhmm(int(row['total_minutes']))} ({int(row['count'])}건)")
            for d in row.get("details", [])[:3]:
                lines.append(f"- {d}")
        return "\n".join(lines)

    # 최저/최고 하역률 + 원인 질의: 규칙 기반으로 선박 특정 후 이슈 반환
    CAUSE_KEYWORDS = ("원인", "이유", "왜", "때문에", "어떤 문제", "무슨 문제")
    RANKING_CAUSE_SIGNALS = ("가장", "제일", "최고", "최저")
    LOW_SIGNALS = ("낮", "최저", "최소")

    has_cause = any(kw in q for kw in CAUSE_KEYWORDS)
    has_ranking = any(rs in q for rs in RANKING_CAUSE_SIGNALS) and "하역률" in q

    if has_cause and has_ranking:
        has_low = any(ls in q for ls in LOW_SIGNALS)
        if scoped:
            if has_low:
                best = min(scoped, key=lambda r: float(r.get("unloading_rate") or float("inf")))
            else:
                best = max(scoped, key=lambda r: float(r.get("unloading_rate") or 0.0))
            vessel = best.get("vessel_name") or "미확인"
            rate = int(round(float(best.get("unloading_rate") or 0)))
            year_v = best.get("year")
            month_v = best.get("month")
            remark = str(best.get("remark") or "")
            issues = best.get("issue_tags") or []
            direction = "낮았던" if has_low else "높았던"
            period = f"{year_v}년 {month_v}월" if year_v and month_v else ""
            period_str = f"({period}, " if period else "("
            lines = [f"{scope_label} 하역률이 가장 {direction} 선박은 {vessel}{period_str}{rate:,} t/d)입니다."]
            if issues:
                lines.append(f"주요 이슈: {', '.join(issues)}")
            if remark:
                clean = remark.strip()
                if clean:
                    lines.append(f"비고: {clean[:300]}")
            return "\n".join(lines)
    elif has_cause:
        # 순수 원인 질의는 규칙 기반으로 답할 수 없으므로 enhanced_chat_answer에 위임
        return None

    if asks_average_rate(q):
        v = int(round(float(k.get("avg_unloading_rate", 0) or 0)))
        return f"{scope_label} 평균 하역률은 {v:,} t/d 입니다."
    if asks_total_volume(q):
        v = int(round(float(k.get("total_volume_ton", 0) or 0)))
        return f"{scope_label} 총 하역량은 {v:,} t 입니다."
    if any(t in q for t in ("총 척수", "척수", "선박 수", "vessel")):
        v = int(round(float(k.get("total_vessels", 0) or 0)))
        return f"{scope_label} 총 척수는 {v:,} 척 입니다."
    issue_count_signals = (
        "이슈 건수",
        "장애 건수",
        "트러블 건수",
        "총 건수",
        "몇 건",
        "몇건",
        "건수",
    )
    if any(sig in q for sig in issue_count_signals):
        v = int(round(float(k.get("issue_count", 0) or 0)))
        return f"{scope_label} 이슈 건수는 {v:,} 건 입니다."
    if _is_brand_rank_question(question) and brand_table:
        rank = _infer_rank_from_question(question)
        if rank is None and any(t in q for t in ("그 다음", "다음", "next")):
            previous_rank = _infer_rank_from_history(history or [])
            rank = (previous_rank + 1) if previous_rank else 2
        if rank is None:
            rank = 1

        idx = rank - 1
        if idx < 0 or idx >= len(brand_table):
            return f"{scope_label}에서 {rank}번째로 많이 들어온 품종은 확인되지 않습니다. (총 {len(brand_table)}개 품종)"

        item = brand_table[idx]
        b = str(item.get("brand") or "미확인")
        v = int(round(float(item.get("volume_ton", 0) or 0)))
        if rank == 1:
            return f"{scope_label} 가장 많이 들어온 품종은 {b}이며 물량은 {v:,} t 입니다."
        return f"{scope_label} {rank}번째로 많이 들어온 품종은 {b}이며 물량은 {v:,} t 입니다."

    return None


if PUBLIC_DIR.exists():
    app.mount("/public", StaticFiles(directory=PUBLIC_DIR), name="public")

JS_DIR = BASE_DIR / "js"
CSS_DIR = BASE_DIR / "css"

if JS_DIR.exists():
    app.mount("/js", StaticFiles(directory=JS_DIR), name="js")
if CSS_DIR.exists():
    app.mount("/css", StaticFiles(directory=CSS_DIR), name="css")


@app.on_event("startup")
def debug_startup_trace() -> None:
    try:
        _ensure_schedule_banchu_tables()
        _ensure_yard_sim_table()
    except Exception as _e:
        print(f"[startup] DB 테이블 생성 실패 (DATABASE_URL 확인 필요): {_e}", flush=True)
    # region agent log
    _debug_log(
        "H2",
        "backend/main.py:startup",
        "FastAPI startup executed",
        {"routes": [route.path for route in app.routes]},
    )
    # endregion


def _session_user(request: Request) -> Optional[str]:
    u = request.session.get("user")
    if isinstance(u, str) and u.strip():
        return u.strip()
    return None


def _require_logged_in(request: Request) -> str:
    u = _session_user(request)
    if not u:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return u


def _require_platform_admin(request: Request) -> str:
    u = _require_logged_in(request)
    if u != pa.platform_admin_username():
        raise HTTPException(status_code=403, detail="플랫폼 관리자만 사용할 수 있습니다.")
    return u


def _require_html_user_or_redirect(request: Request) -> Optional[RedirectResponse]:
    u = _session_user(request)
    if u:
        pa.audit_write(request, u, "page_view", request.url.path)
        return None
    return RedirectResponse(url="/", status_code=302)


@app.middleware("http")
async def debug_request_trace(request: Request, call_next) -> Response:
    # region agent log
    _debug_log(
        "H1",
        "backend/main.py:middleware_entry",
        "Incoming request",
        {"method": request.method, "path": request.url.path},
    )
    # endregion
    response = await call_next(request)
    if request.method == "GET" and request.url.path in NO_CACHE_HTML_PATHS:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    # region agent log
    _debug_log(
        "H1",
        "backend/main.py:middleware_exit",
        "Completed request",
        {"method": request.method, "path": request.url.path, "status_code": response.status_code},
    )
    # endregion
    return response


@app.get("/api/health")
def health_check() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.post("/api/auth/login")
async def auth_login(request: Request) -> JSONResponse:
    body = await request.json()
    username = str(body.get("username") or "").strip()
    password = str(body.get("password") or "")
    if pa.verify_user_credentials(username, password):
        request.session["user"] = username
        pa.audit_write(request, username, "login_ok", "")
        return JSONResponse(
            {
                "ok": True,
                "username": username,
                "is_platform_admin": username == pa.platform_admin_username(),
            }
        )
    pa.audit_write(request, None, "login_fail", username[:120] if username else "")
    raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")


@app.post("/api/auth/logout")
def auth_logout(request: Request) -> JSONResponse:
    u = _session_user(request)
    request.session.clear()
    if u:
        pa.audit_write(request, u, "logout", "")
    return JSONResponse({"ok": True})


@app.get("/api/auth/me")
def auth_me(request: Request) -> JSONResponse:
    u = _session_user(request)
    admin_un = pa.platform_admin_username()
    return JSONResponse(
        {
            "username": u,
            "is_platform_admin": u == admin_un,
            "platform_admin_username": admin_un,
        }
    )


@app.get("/api/auth/users")
def auth_users_list(request: Request) -> JSONResponse:
    _require_platform_admin(request)
    pa.require_admin_header(request)
    return JSONResponse({"users": pa.list_usernames()})


@app.post("/api/auth/users")
async def auth_users_create(request: Request) -> JSONResponse:
    actor = _require_platform_admin(request)
    pa.require_admin_header(request)
    body = await request.json()
    un = str(body.get("username") or "").strip()
    pw = str(body.get("password") or "")
    pa.add_user(un, pw)
    pa.audit_write(request, actor, "admin_user_create", un)
    return JSONResponse({"ok": True})


@app.patch("/api/auth/users/{username}")
async def auth_users_patch_password(request: Request, username: str) -> JSONResponse:
    actor = _require_platform_admin(request)
    pa.require_admin_header(request)
    body = await request.json()
    pw = str(body.get("password") or "")
    pa.set_user_password(username, pw)
    pa.audit_write(request, actor, "admin_user_password_change", username)
    return JSONResponse({"ok": True})


@app.delete("/api/auth/users/{username}")
def auth_users_delete(request: Request, username: str) -> JSONResponse:
    actor = _require_platform_admin(request)
    pa.require_admin_header(request)
    pa.delete_user(username)
    pa.audit_write(request, actor, "admin_user_delete", username)
    return JSONResponse({"ok": True})


@app.get("/api/auth/audit")
def auth_audit(request: Request, limit: int = 300) -> JSONResponse:
    _require_platform_admin(request)
    pa.require_admin_header(request)
    lim = max(1, min(limit, 2000))
    return JSONResponse({"entries": pa.read_audit_tail(lim)})


@app.get("/api/supply-news")
def supply_news(cargo_type: str = "nickel") -> JSONResponse:
    ct = (cargo_type or "nickel").strip().lower()
    if ct not in ("nickel", "coal"):
        raise HTTPException(status_code=400, detail="cargo_type은 nickel 또는 coal 이어야 합니다.")
    return JSONResponse(get_supply_news_payload(ct))


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


@app.get("/api/yard-sim")
def get_yard_sim(mode: str) -> JSONResponse:
    if mode not in _ALLOWED_SIM_MODES:
        raise HTTPException(status_code=400, detail="mode는 'overall' 또는 'import'여야 합니다.")
    try:
        data = _db_get_yard_sim(mode)
    except Exception:
        data = None
    return JSONResponse(data)


@app.put("/api/yard-sim")
async def put_yard_sim(request: Request, mode: str) -> JSONResponse:
    if mode not in _ALLOWED_SIM_MODES:
        raise HTTPException(status_code=400, detail="mode는 'overall' 또는 'import'여야 합니다.")
    try:
        data = await request.json()
        if not isinstance(data, dict):
            raise HTTPException(status_code=400, detail="객체 형식이어야 합니다.")
        _db_save_yard_sim(mode, data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"저장 실패: {e}")
    return JSONResponse({"ok": True})


@app.get("/api/config")
def app_config() -> JSONResponse:
    return JSONResponse(
        {
            "app_name": "Port Operation Web App",
            "frontend_routes": ["/", "/schedule", "/banchu", "/yard", "/unloading-data", "/unloading_data"],
        }
    )


@app.get("/api/unloading-data/meta")
def unloading_data_meta() -> JSONResponse:
    rows = _get_unloading_dataset()
    years = sorted({r["year"] for r in rows})
    coal_brands = sorted({r["brand"] for r in rows if r["cargo_type"] == "coal"})
    nickel_brands = sorted({r["brand"] for r in rows if r["cargo_type"] == "nickel"})
    return JSONResponse(
        {
            "years": years,
            "brands": {"coal": coal_brands, "nickel": nickel_brands},
            "issue_categories": ISSUE_CATEGORIES,
            "uploaded_files": _uploaded_excel_files(),
            "uploaded_file_details": _uploaded_excel_file_details(),
        }
    )


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
    target_name = f"{year}_unloading{ext}"

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="빈 파일은 업로드할 수 없습니다.")

    content_type = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if ext == ".xlsx"
        else "application/vnd.ms-excel"
    )
    bucket = _storage_client()
    try:
        bucket.upload(
            path=target_name,
            file=content,
            file_options={"content-type": content_type, "upsert": "true"},
        )
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


@app.get("/api/unloading-data/summary")
def unloading_data_summary(
    cargo_type: str = "coal",
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    brands: Optional[str] = None,
) -> JSONResponse:
    if cargo_type not in {"coal", "nickel"}:
        raise HTTPException(status_code=400, detail="cargo_type must be coal or nickel")
    rows = _get_unloading_dataset()
    parsed_brands = [b.strip() for b in (brands or "").split(",") if b.strip()]
    filtered = _filter_rows(rows, cargo_type, start_year, end_year, parsed_brands or None)
    return JSONResponse(_aggregate_summary(filtered))


@app.post("/api/unloading-data/chat")
async def unloading_data_chat(request: Request) -> JSONResponse:
    payload = await request.json()
    question = str(payload.get("question") or "").strip()
    history_raw = payload.get("history")
    if not question:
        raise HTTPException(status_code=400, detail="질문(question)이 필요합니다.")
    u_chat = _session_user(request)
    if u_chat:
        pa.audit_write(request, u_chat, "api_unloading_chat", question[:500])
    if _is_ambiguous_chat_question(question):
        return JSONResponse(
            {
                "answer": (
                    "질문의 의도를 정확히 파악하기 어려워요. "
                    "예: '2025년도 니켈 평균 하역률', '기상불량(우천대기) 총 시간', "
                    "'가장 많이 들어온 품종과 물량'처럼 구체적으로 물어봐 주세요."
                ),
                "summary": {},
            }
        )

    # 챗봇은 화면 필터와 무관하게 업로드된 엑셀 전체 데이터를 기준으로 답변한다.
    rows = _get_unloading_dataset()
    history = _normalize_chat_history(history_raw)
    parsed_query = _parse_query(question, rows)
    merged_query = _merge_query_with_history(parsed_query, history, rows)
    force_hybrid = _should_force_hybrid_question(question)
    if not force_hybrid:
        rule_based_answer = _build_rule_based_chat_answer(question, rows, history=history, parsed_filters=merged_query)
        if rule_based_answer:
            return JSONResponse({"answer": _format_numbers_with_commas(rule_based_answer), "summary": {}})

    try:
        from haeyang.chatbot import enhanced_chat_answer

        fp = _haeyang_source_fingerprint()
        enhanced = enhanced_chat_answer(question, history, BASE_DIR, rows, fp)
        if enhanced:
            summary = _aggregate_summary(rows)
            return JSONResponse({"answer": _format_numbers_with_commas(enhanced), "summary": summary})
    except Exception:
        pass

    summary = _aggregate_summary(rows)
    dynamic_summary = _compute_dynamic_chat_summary(rows, merged_query)
    context_json = json.dumps(dynamic_summary, ensure_ascii=False)
    answer = _chat_completion_with_openai(question, context_json, history=history, force_hybrid_style=force_hybrid)
    if not answer:
        answer = (
            "요청하신 내용을 업로드된 데이터에서 명확히 찾지 못했습니다. "
            "질문 대상을 조금 더 구체적으로 알려주세요. "
            "(예: 화종/연도/지표/브랜드)"
        )
    answer = _format_numbers_with_commas(answer)
    return JSONResponse({"answer": answer, "summary": summary})


@app.get("/")
@app.get("/index.html")
def serve_index() -> FileResponse:
    if not INDEX_HTML.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(INDEX_HTML)


@app.get("/schedule", response_model=None)
@app.get("/schedule.html", response_model=None)
def serve_schedule(request: Request) -> Union[FileResponse, RedirectResponse]:
    redir = _require_html_user_or_redirect(request)
    if redir is not None:
        return redir
    if not SCHEDULE_HTML.exists():
        raise HTTPException(status_code=404, detail="schedule.html not found")
    return FileResponse(SCHEDULE_HTML)


@app.get("/banchu", response_model=None)
@app.get("/banchu.html", response_model=None)
def serve_banchu(request: Request) -> Union[FileResponse, RedirectResponse]:
    # region agent log
    _debug_log(
        "H3",
        "backend/main.py:serve_banchu",
        "Entered /banchu handler",
        {"banchu_exists": BANCHU_HTML.exists(), "banchu_path": str(BANCHU_HTML)},
    )
    # endregion
    redir = _require_html_user_or_redirect(request)
    if redir is not None:
        return redir
    if not BANCHU_HTML.exists():
        raise HTTPException(status_code=404, detail="banchu.html not found")
    return FileResponse(BANCHU_HTML)


@app.get("/yard", response_model=None)
@app.get("/yard.html", response_model=None)
def serve_yard(request: Request) -> Union[FileResponse, RedirectResponse]:
    redir = _require_html_user_or_redirect(request)
    if redir is not None:
        return redir
    if not YARD_HTML.exists():
        raise HTTPException(status_code=404, detail="yard.html not found")
    return FileResponse(YARD_HTML)


@app.get("/unloading-data", response_model=None)
@app.get("/unloading_data", response_model=None)
@app.get("/unloading_data.html", response_model=None)
@app.get("/unloading-data.html", response_model=None)
def serve_unloading_data(request: Request) -> Union[FileResponse, RedirectResponse]:
    redir = _require_html_user_or_redirect(request)
    if redir is not None:
        return redir
    if not UNLOADING_DATA_HTML.exists():
        raise HTTPException(status_code=404, detail="unloading_data.html not found")
    return FileResponse(UNLOADING_DATA_HTML)


@app.get("/maintenance/equipment", response_model=None)
def serve_maintenance_equipment(request: Request) -> Union[FileResponse, RedirectResponse]:
    redir = _require_html_user_or_redirect(request)
    if redir is not None:
        return redir
    if not MAINTENANCE_PLACEHOLDER_HTML.exists():
        raise HTTPException(status_code=404, detail="maintenance_placeholder.html not found")
    return FileResponse(MAINTENANCE_PLACEHOLDER_HTML)


@app.get("/maintenance/history", response_model=None)
def serve_maintenance_history(request: Request) -> Union[FileResponse, RedirectResponse]:
    redir = _require_html_user_or_redirect(request)
    if redir is not None:
        return redir
    if not MAINTENANCE_PLACEHOLDER_HTML.exists():
        raise HTTPException(status_code=404, detail="maintenance_placeholder.html not found")
    return FileResponse(MAINTENANCE_PLACEHOLDER_HTML)
