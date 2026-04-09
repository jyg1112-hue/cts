from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles


BASE_DIR = Path(__file__).resolve().parent.parent
INDEX_HTML = BASE_DIR / "index.html"
SCHEDULE_HTML = BASE_DIR / "schedule.html"
BANCHU_HTML = BASE_DIR / "banchu.html"
YARD_HTML = BASE_DIR / "yard.html"
UNLOADING_DATA_HTML = BASE_DIR / "unloading_data.html"
PUBLIC_DIR = BASE_DIR / "public"
DEBUG_LOG_PATH = BASE_DIR / "debug-34636b.log"
UNLOADING_XLS_PATH = BASE_DIR / "backdata" / "(2025년) 7선석 하역률.xls"
UNLOADING_UPLOAD_DIR = BASE_DIR / "backdata" / "uploads"
UNLOADING_COAL_SHEET = "석탄(년)"
UNLOADING_NICKEL_SHEET = "니켈(년)"

app = FastAPI(title="0327_2 Web App", version="1.0.0")
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
    "기상불량": ["기상", "우천", "한파", "강풍", "악천후", "폭우"],
    "화물상태": ["화물상태", "수분", "점성", "괴광"],
    "작업대기": ["작업대기", "대기", "본선관련", "야드부족", "재고부족", "착수지연"],
    "운영변경": ["야드변경", "브랜드 변경", "이항양하", "선적", "연동"],
    "품질/검출": ["철편검출", "검출", "슈트막힘", "청소", "목고작업"],
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


def _ensure_upload_dir() -> None:
    UNLOADING_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _uploaded_excel_files() -> list[Path]:
    _ensure_upload_dir()
    files = sorted(
        [p for p in UNLOADING_UPLOAD_DIR.iterdir() if p.is_file() and UPLOAD_NAME_PATTERN.match(p.name)],
        key=lambda p: p.name,
    )
    return files


def _uploaded_excel_file_details() -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for path in _uploaded_excel_files():
        stat = path.stat()
        details.append(
            {
                "name": path.name,
                "size_bytes": stat.st_size,
                "updated_at": int(stat.st_mtime),
            }
        )
    return details


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
    lower_text = text.lower()
    tags: list[str] = []
    for category, keywords in ISSUE_CATEGORY_RULES.items():
        if any(keyword.lower() in lower_text for keyword in keywords):
            tags.append(category)
    return tags or ["기타"]


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


def _safe_month(value: Any) -> Optional[int]:
    numeric = _parse_float(value)
    if numeric is None:
        return None
    month = int(numeric)
    if 1 <= month <= 12:
        return month
    return None


def _safe_year(start_dt: Any) -> Optional[int]:
    if pd.isna(start_dt):
        return None
    if hasattr(start_dt, "year"):
        return int(start_dt.year)
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

        month = _safe_month(row.get("월"))
        start_dt = pd.to_datetime(row.get("착수"), errors="coerce")
        year = _safe_year(start_dt)
        if year is None:
            continue

        if cargo_type == "coal":
            volume = _parse_float(row.get("하역량(톤)"))
            brand = _normalize_coal_brand(raw_brand)
        else:
            volume = _parse_float(row.get("B/L량(톤)"))
            brand = _normalize_nickel_brand(raw_brand)
        if volume is None:
            continue

        remark = _normalize_text(row.get("비고"))
        issue_tags = _classify_issue_tags(remark)
        rows.append(
            {
                "cargo_type": cargo_type,
                "year": year,
                "month": month or int(start_dt.month),
                "vessel_name": vessel_name,
                "brand": brand,
                "volume_ton": volume,
                "unloading_rate": rate,
                "remark": remark,
                "issue_tags": issue_tags,
                "source_file": source_path.name,
            }
        )
    return rows


def _get_unloading_dataset() -> list[dict[str, Any]]:
    source_files = _uploaded_excel_files()
    if not source_files:
        if not UNLOADING_XLS_PATH.exists():
            return []
        source_files = [UNLOADING_XLS_PATH]

    all_rows: list[dict[str, Any]] = []
    for source in source_files:
        try:
            all_rows.extend(_parse_unloading_sheet("coal", UNLOADING_COAL_SHEET, source))
        except Exception:
            pass
        try:
            all_rows.extend(_parse_unloading_sheet("nickel", UNLOADING_NICKEL_SHEET, source))
        except Exception:
            pass
    return all_rows


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
            "brand_table": [],
        }

    vessel_names = {r["vessel_name"] for r in rows}
    total_volume = sum(r["volume_ton"] for r in rows)
    avg_rate = sum(r["unloading_rate"] for r in rows) / len(rows)

    monthly_map: dict[tuple[int, int], dict[str, Any]] = {}
    issue_counter = {c: 0 for c in ISSUE_CATEGORIES}
    brand_map: dict[str, dict[str, Any]] = {}
    for r in rows:
        ym = (r["year"], r["month"])
        if ym not in monthly_map:
            monthly_map[ym] = {"year": r["year"], "month": r["month"], "volume_ton": 0.0, "rates": []}
        monthly_map[ym]["volume_ton"] += r["volume_ton"]
        monthly_map[ym]["rates"].append(r["unloading_rate"])

        tags = r["issue_tags"] or []
        if not tags:
            issue_counter["기타"] += 1
        for tag in tags:
            issue_counter[tag if tag in issue_counter else "기타"] += 1

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

    return {
        "kpis": {
            "total_volume_ton": round(total_volume, 2),
            "total_vessels": len(vessel_names),
            "avg_unloading_rate": round(avg_rate, 2),
            "issue_count": sum(issue_counter.values()),
        },
        "monthly": monthly,
        "issue_breakdown": issue_breakdown,
        "brand_table": brand_table,
    }


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
    _ensure_upload_dir()
    # region agent log
    _debug_log(
        "H2",
        "backend/main.py:startup",
        "FastAPI startup executed",
        {"routes": [route.path for route in app.routes]},
    )
    # endregion


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
            "uploaded_files": [p.name for p in _uploaded_excel_files()],
            "uploaded_file_details": _uploaded_excel_file_details(),
        }
    )


@app.post("/api/unloading-data/upload")
async def upload_unloading_excel(file: UploadFile = File(...)) -> JSONResponse:
    _ensure_upload_dir()
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
    target_path = UNLOADING_UPLOAD_DIR / target_name

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="빈 파일은 업로드할 수 없습니다.")
    target_path.write_bytes(content)

    return JSONResponse(
        {
            "message": "업로드 완료",
            "saved_as": target_name,
            "uploaded_files": [p.name for p in _uploaded_excel_files()],
            "uploaded_file_details": _uploaded_excel_file_details(),
        }
    )


@app.delete("/api/unloading-data/upload/{file_name}")
def delete_uploaded_unloading_excel(file_name: str) -> JSONResponse:
    _ensure_upload_dir()
    if not UPLOAD_NAME_PATTERN.match(file_name):
        raise HTTPException(status_code=400, detail="허용되지 않은 파일명입니다.")

    target_path = UNLOADING_UPLOAD_DIR / file_name
    if not target_path.exists() or not target_path.is_file():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    target_path.unlink()

    return JSONResponse(
        {
            "message": "삭제 완료",
            "deleted": file_name,
            "uploaded_files": [p.name for p in _uploaded_excel_files()],
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


@app.get("/")
@app.get("/index.html")
def serve_index() -> FileResponse:
    if not INDEX_HTML.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(INDEX_HTML)


@app.get("/schedule")
@app.get("/schedule.html")
def serve_schedule() -> FileResponse:
    if not SCHEDULE_HTML.exists():
        raise HTTPException(status_code=404, detail="schedule.html not found")
    return FileResponse(SCHEDULE_HTML)


@app.get("/banchu")
@app.get("/banchu.html")
def serve_banchu() -> FileResponse:
    # region agent log
    _debug_log(
        "H3",
        "backend/main.py:serve_banchu",
        "Entered /banchu handler",
        {"banchu_exists": BANCHU_HTML.exists(), "banchu_path": str(BANCHU_HTML)},
    )
    # endregion
    if not BANCHU_HTML.exists():
        raise HTTPException(status_code=404, detail="banchu.html not found")
    return FileResponse(BANCHU_HTML)


@app.get("/yard")
@app.get("/yard.html")
def serve_yard() -> FileResponse:
    if not YARD_HTML.exists():
        raise HTTPException(status_code=404, detail="yard.html not found")
    return FileResponse(YARD_HTML)


@app.get("/unloading-data")
@app.get("/unloading_data")
@app.get("/unloading_data.html")
@app.get("/unloading-data.html")
def serve_unloading_data() -> FileResponse:
    if not UNLOADING_DATA_HTML.exists():
        raise HTTPException(status_code=404, detail="unloading_data.html not found")
    return FileResponse(UNLOADING_DATA_HTML)
