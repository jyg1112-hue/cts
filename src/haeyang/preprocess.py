from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

import pandas as pd

# 스펙 기준 이슈 키워드 (비고 파싱 보조)
ISSUE_CATEGORIES_SPEC: dict[str, list[str]] = {
    "돌발정비": ["돌발정비", "돌발/일상 정비"],
    "SNNC설비트러블": ["SNNC 설비트러블", "SNNC 설비 트러블", "snnc"],
    "화물이슈": ["화물이슈", "화물상태", "고 수분", "대형괴광", "점성"],
    "기상불량": ["기상불량", "우천", "한파"],
    "철편검출": ["철편검출"],
    "본선관련": ["본선관련 대기", "홋줄풀림", "선박트림"],
    "일상정비": ["일상정비", "계획정비"],
}


def parse_time_from_text(text: str) -> float | None:
    """
    비고에서 '(1:30)', '(4:05/2=2:02)' 형태의 시간을 파싱해 시간(float) 반환.
    '(4:05/2=2:02)' → 등호 뒤 2:02 기준(각 호기)으로 해석.
    """
    if not text:
        return None
    t = unicodedata.normalize("NFKC", text)
    # (4:05/2=2:02) — 등호 뒤 세그먼트 우선
    m_eq = re.search(
        r"=\s*(?P<h>\d{1,3})\s*:\s*(?P<m>\d{1,2})\s*\)",
        t,
    )
    if m_eq:
        h, mi = int(m_eq.group("h")), int(m_eq.group("m"))
        if 0 <= mi < 60:
            return h + mi / 60.0
    m = re.search(r"\(\s*(?P<h>\d{1,3})\s*:\s*(?P<m>\d{1,2})\s*\)", t)
    if m:
        h, mi = int(m.group("h")), int(m.group("m"))
        if 0 <= mi < 60:
            return h + mi / 60.0
    return None


def parse_issues(raw_remark: str) -> list[dict[str, Any]]:
    """
    비고를 줄 단위로 분리해 카테고리별로 시간을 개별 추출한다.
    같은 카테고리가 여러 줄에 걸쳐 있으면 duration_hours를 누산한다.
    """
    if not raw_remark:
        return []
    text = unicodedata.normalize("NFKC", raw_remark)
    # 슬래시 포함 키워드를 분리 전에 정규화한다
    text = text.replace("돌발/일상 정비", "돌발정비")
    # 줄 구분: 줄바꿈 또는 '/'로 분리 (단, 시간 표기 내부 '/'는 제외)
    lines = re.split(r"\n|(?<!\d)/(?!\d)", text)

    accumulated: dict[str, dict[str, Any]] = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        lower = line.lower()
        for category, kws in ISSUE_CATEGORIES_SPEC.items():
            if not any(kw.lower() in lower for kw in kws):
                continue
            dur = parse_time_from_text(line) or 0.0
            if category in accumulated:
                accumulated[category]["duration_hours"] += dur
                # 상세 텍스트는 첫 번째 줄 유지
            else:
                snippet = line if len(line) <= 120 else line[:120] + "…"
                accumulated[category] = {
                    "category": category,
                    "detail": snippet,
                    "duration_hours": dur,
                }
    return list(accumulated.values())


def _flags_from_tags(issue_tags: list[str]) -> tuple[bool, bool, bool]:
    """기존 main.py issue_tags 기반 플래그."""
    tags = issue_tags or []
    emergency = any(t in tags for t in ("돌발정비",))
    cargo = any(t in tags for t in ("화물상태", "품질/검출"))
    weather = "기상불량" in tags
    return emergency, cargo, weather


def rows_to_dataframes(rows: list[dict[str, Any]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    backend main의 언로딩 row dict 목록을 coal / nickel DataFrame으로 변환.
    스키마는 SQLite 및 RAG 메타데이터용.
    """
    coal_rows: list[dict[str, Any]] = []
    nickel_rows: list[dict[str, Any]] = []
    seq = 0
    for _, r in enumerate(rows):
        cargo = str(r.get("cargo_type") or "")
        month = int(r.get("month") or 0)
        year = int(r.get("year") or 0)
        vessel = str(r.get("vessel_name") or "")
        species = str(r.get("brand") or "")
        vol = float(r.get("volume_ton") or 0)
        rate = float(r.get("unloading_rate") or 0)
        raw = str(r.get("remark") or "")
        tags = list(r.get("issue_tags") or [])
        issue_cats = json.dumps(tags, ensure_ascii=False)
        durations = r.get("remark_durations") or []
        total_delay_hours = 0.0
        for d in durations:
            tm = int(d.get("total_minutes") or 0)
            total_delay_hours += tm / 60.0
        em, cg, w = _flags_from_tags(tags)
        seq += 1
        base = {
            "id": seq,
            "척수": seq,
            "월": month,
            "year": year,
            "선박명": vessel,
            "품종": species,
            "하역량_톤": vol,
            "착수": f"{year}-{month:02d}-01 00:00:00",
            "완료": f"{year}-{month:02d}-28 23:59:59",
            "소요일": None,
            "조정": None,
            "최종소요일": None,
            "하역률": rate,
            "현장교대": "",
            "raw_비고": raw,
            "issue_categories": issue_cats,
            "total_delay_hours": round(total_delay_hours, 4),
            "has_emergency_maintenance": bool(em),
            "has_cargo_issue": bool(cg),
            "has_weather_delay": bool(w),
            "cargo_type": cargo,
        }
        if cargo == "coal":
            coal_rows.append(base)
        elif cargo == "nickel":
            nickel_rows.append(
                {
                    **base,
                    "항차": "",
                    "작업시간": None,
                    "작업대기시간": None,
                    "조업율": None,
                    "TH": None,
                }
            )
    coal_df = pd.DataFrame(coal_rows)
    nickel_df = pd.DataFrame(nickel_rows)
    return coal_df, nickel_df


def build_document(row: pd.Series, cargo_type: str) -> Any:
    from langchain_core.documents import Document

    raw = row.get("raw_비고") or ""
    month = int(row.get("월") or 0)
    rate = float(row.get("하역률") or 0)
    vol = float(row.get("하역량_톤") or 0)
    final_days = row.get("최종소요일")
    try:
        fd = float(final_days) if final_days is not None and str(final_days) != "nan" else 0.0
    except (TypeError, ValueError):
        fd = 0.0
    page_content = f"""
선박명: {row.get('선박명', '')}
화물 품종: {row.get('품종', '')}
하역 월: {month}월
연도: {row.get('year', '')}
하역량: {vol:,.0f}톤
하역률: {rate:.1f}톤/일
착수: {row.get('착수', '')}
완료: {row.get('완료', '')}
소요일: {fd:.2f}일

[이슈 및 비고]
{raw}
""".strip()
    meta = {
        "cargo_type": cargo_type,
        "ship_name": str(row.get("선박명") or ""),
        "month": month,
        "year": int(row.get("year") or 0),
        "품종": str(row.get("품종") or ""),
        "하역률": rate,
        "has_emergency": bool(row.get("has_emergency_maintenance")),
        "has_cargo_issue": bool(row.get("has_cargo_issue")),
        "has_weather_delay": bool(row.get("has_weather_delay")),
        "issue_categories": str(row.get("issue_categories") or "[]"),
        "척수": int(row.get("척수") or 0),
    }
    return Document(page_content=page_content, metadata=meta)


def build_all_documents(coal_df: pd.DataFrame, nickel_df: pd.DataFrame) -> list[Any]:
    docs: list[Any] = []
    for _, row in coal_df.iterrows():
        docs.append(build_document(row, "coal"))
    for _, row in nickel_df.iterrows():
        docs.append(build_document(row, "nickel"))
    return docs
