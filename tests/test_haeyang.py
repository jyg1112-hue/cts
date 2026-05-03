"""하역 챗봇 단위 테스트 (라우터·전처리는 모킹/경량 데이터)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
import sys

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def test_rows_to_dataframes_smoke():
    from haeyang.preprocess import rows_to_dataframes

    rows = [
        {
            "cargo_type": "coal",
            "year": 2025,
            "month": 3,
            "vessel_name": "TEST-A",
            "brand": "호주",
            "volume_ton": 10000,
            "unloading_rate": 30000,
            "remark": "돌발정비(1:00)",
            "issue_tags": ["돌발정비"],
            "remark_durations": [{"total_minutes": 60, "label": "돌발정비", "time_hhmm": "1:00"}],
        }
    ]
    coal, nickel = rows_to_dataframes(rows)
    assert len(coal) == 1
    assert coal.iloc[0]["하역률"] == 30000


def test_router_classify_sql(monkeypatch):
    from haeyang.router import _classify

    monkeypatch.setattr(
        "haeyang.router.chat_json_completion",
        lambda *a, **k: {
            "query_type": "sql",
            "month": 3,
            "year": None,
            "ship_name": None,
            "cargo_type": "coal",
            "품종": None,
        },
    )
    out = _classify({"query": "3월 석탄 평균 하역률"})
    assert out["query_type"] == "sql"
    assert out["metadata_filter"].get("month") == 3


def test_router_classify_hybrid(monkeypatch):
    from haeyang.router import _classify

    monkeypatch.setattr(
        "haeyang.router.chat_json_completion",
        lambda *a, **k: {"query_type": "hybrid", "month": None, "year": None, "ship_name": None, "cargo_type": None, "품종": None},
    )
    out = _classify({"query": "하역률이 낮은 이유"})
    assert out["query_type"] == "hybrid"


def test_parse_time_from_text():
    from haeyang.preprocess import parse_time_from_text

    assert parse_time_from_text("(4:05/2=2:02)") is not None
    assert parse_time_from_text("(1:30)") == pytest.approx(1.5, rel=1e-3)


def test_parse_issues_per_line():
    from haeyang.preprocess import parse_issues

    raw = "돌발정비(CSU2 붐업 불가)(6:04)\nSNNC 설비트러블(1:30)"
    issues = parse_issues(raw)

    cats = {i["category"]: i["duration_hours"] for i in issues}
    assert "돌발정비" in cats
    assert "SNNC설비트러블" in cats
    # 줄별로 다른 시간이 추출되어야 한다
    assert abs(cats["돌발정비"] - (6 + 4 / 60)) < 0.01
    assert abs(cats["SNNC설비트러블"] - 1.5) < 0.01


def test_parse_issues_slash_keyword():
    from haeyang.preprocess import parse_issues

    # "돌발/일상 정비" 키워드가 슬래시 분리자에 의해 파괴되지 않아야 한다
    raw = "돌발/일상 정비(2:00)"
    issues = parse_issues(raw)
    cats = {i["category"]: i["duration_hours"] for i in issues}
    assert "돌발정비" in cats
    assert abs(cats["돌발정비"] - 2.0) < 0.01


def test_router_classify_rag_issue(monkeypatch):
    from haeyang.router import _classify

    monkeypatch.setattr(
        "haeyang.router.chat_json_completion",
        lambda *a, **k: {
            "query_type": "rag",
            "month": None,
            "year": None,
            "ship_name": None,
            "cargo_type": None,
            "품종": None,
        },
    )
    out = _classify({"query": "수분이 높은 화물로 인한 문제"})
    assert out["query_type"] == "rag"
    assert out["metadata_filter"] == {}


def test_rag_chain_passes_context(monkeypatch):
    from langchain_core.documents import Document
    from haeyang.rag_chain import run_rag_chain

    captured = {}

    def fake_completion(system_prompt, user_prompt, model=None):
        captured["user_prompt"] = user_prompt
        return "테스트 답변"

    monkeypatch.setattr("haeyang.rag_chain.chat_text_completion", fake_completion)

    docs = [
        Document(page_content="선박명: TEST-A\n[이슈 및 비고]\n돌발정비(6:04)", metadata={}),
    ]
    result = run_rag_chain("CSU2호 feeder 관련 이슈", docs)

    assert result == "테스트 답변"
    assert "TEST-A" in captured["user_prompt"]
    assert "돌발정비" in captured["user_prompt"]
