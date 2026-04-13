from __future__ import annotations

"""LangGraph 기반 쿼리 라우터.

사용자 질문을 SQL / RAG / Hybrid 세 경로로 분류하고,
각 경로에 맞는 체인을 실행해 최종 답변을 반환한다.

주요 진입점: build_router_graph(db_path, retriever, reranker)
"""

from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from haeyang.openai_json import chat_json_completion, chat_text_completion
from haeyang.rag_chain import run_rag_chain
from haeyang.reranker import Reranker
from haeyang.retriever import HybridRetriever
from haeyang.sql_chain import run_sql_chain

ROUTING_PROMPT = """
사용자 질문을 분석해 처리 경로와 필터를 JSON으로만 반환한다.

경로 query_type 분류 기준:
- "sql": 수치 집계·순위 쿼리, 또는 조건에 맞는 선박·품종 목록 조회
  핵심 판단 기준: 답이 "숫자" 또는 "목록(선박명/품종명)" 이면 sql
  예) "3월 평균 하역률", "하역량이 가장 많은 선박", "1월~3월 석탄 총 하역량", "하역률 상위 5개 선박",
      "2025년 니켈에서 하역률이 가장 낮은 품종", "연도별 니켈 품종별 평균 하역률 순위", "석탄 품종 중 최저 하역률",
      "수분 이슈가 있었던 니켈 품종은?"    ← 이슈 조건이 있어도 답이 품종 목록이면 sql
      "죽광 이슈가 있었던 품종 목록"       ← 이슈 조건이 있어도 답이 품종 목록이면 sql
      "수분, 죽광 이슈가 있었던 니켈 품종은?" ← 복수 이슈 조건 + 품종 목록 → sql
      "돌발정비가 발생한 선박은?"          ← 이슈 조건이 있어도 답이 선박 목록이면 sql
      "기상불량이 있었던 월은?"            ← 이슈 조건 + 월 목록 → sql

- "rag": 이슈 내용, 원인 분석, 정비 내역, 화물 상태 쿼리 (수치 집계 없음)
  예) "CSU2호 관련 정비 이슈", "수분이 높은 화물로 인한 문제", "철편검출이 많았던 사례", "돌발정비 발생 경위"

- "hybrid": 이슈/조건으로 대상을 좁힌 뒤 수치(평균·합계·순위 등)를 묻는 쿼리 ← 반드시 hybrid
  예) "수분 이슈가 있었던 선박의 평균 하역률"      ← 이슈 조건 + 수치 집계
      "화물이슈가 발생한 석탄 선박의 하역률 평균"   ← 이슈 조건 + 수치 집계
      "돌발정비 선박들의 평균 소요일"               ← 이슈 조건 + 수치 집계
      "기상불량으로 지연된 선박의 하역률"            ← 이슈 조건 + 수치 조회
      "하역률이 낮았던 선박의 원인"                 ← 수치 + 원인 설명
      "3월에 돌발정비가 발생한 선박의 하역률"        ← 이슈 조건 + 수치
      "기상불량으로 지연된 선박의 실적"              ← 이슈 조건 + 실적 조회

필터 (언급이 없으면 반드시 null):
- month: 1~12 정수 또는 null
- year: 4자리 연도 정수 또는 null
- ship_name: 선박명 일부 문자열 또는 null
- cargo_type: "coal" | "nickel" | null
- 품종: 품종 문자열 일부(인니, 러시아, 호주 등) 또는 null
- has_cargo_issue: 1 (수분·점성·대형괴광 등 화물이슈 언급 시) 또는 null
- has_emergency_maintenance: 1 (돌발정비 언급 시) 또는 null
- has_weather_delay: 1 (기상불량·우천·한파 언급 시) 또는 null
- issue_keyword: 이슈 관련 핵심 키워드 문자열(수분, 점성, 철편, SNNC 등) 또는 null

반환 형식 (JSON만, 설명 없이):
{"query_type":"sql"|"rag"|"hybrid","month":null,"year":null,"ship_name":null,"cargo_type":null,"품종":null,"has_cargo_issue":null,"has_emergency_maintenance":null,"has_weather_delay":null,"issue_keyword":null}

질문:
"""

SQL_KEYWORDS = [
    "평균",
    "합계",
    "총",
    "최대",
    "최소",
    "최고",
    "최저",
    "가장",
    "몇 척",
    "순위",
    "상위",
    "하위",
    "얼마",
    "품종별",
    "품종은",
    "품종이",
    "광종",
    "목록",
    "어느 선박",
    "어떤 선박",
    "어느 품종",
    "어떤 품종",
]
RAG_KEYWORDS = ["이슈", "원인", "정비", "트러블", "지연 사유", "왜", "사례", "비고"]
HYBRID_KEYWORDS = [
    "이슈가 있었던",
    "문제가 있었던",
    "발생한 선박",
    "지연된 선박",
    "트러블 선박",
    "수분",
    "점성",
    "돌발정비",
    "기상불량",
    "철편",
]


class ChatState(TypedDict, total=False):
    query: str
    query_type: Literal["sql", "rag", "hybrid"]
    metadata_filter: dict[str, Any]
    sql_result: str | None
    rag_result: str | None
    final_answer: str | None


def _classify(state: ChatState) -> ChatState:
    q = state.get("query") or ""
    data = chat_json_completion(
        "JSON만 출력한다.",
        ROUTING_PROMPT + q,
        temperature=0.0,
    )
    qt: Literal["sql", "rag", "hybrid"] = "rag"
    if data:
        raw = str(data.get("query_type") or "rag").lower()
        if raw in ("sql", "rag", "hybrid"):
            qt = raw  # type: ignore[assignment]
    else:
        # LLM 실패 시 키워드 기반 fallback
        has_sql = any(k in q for k in SQL_KEYWORDS)
        has_rag = any(k in q for k in RAG_KEYWORDS)
        has_hybrid = any(k in q for k in HYBRID_KEYWORDS)
        if has_hybrid and has_sql:
            qt = "hybrid"
        elif has_sql:
            qt = "sql"
        elif has_rag or has_hybrid:
            qt = "rag"
    filt: dict[str, Any] = {}
    if data:
        for key in ("month", "year", "ship_name", "cargo_type", "품종",
                    "has_cargo_issue", "has_emergency_maintenance", "has_weather_delay",
                    "issue_keyword"):
            v = data.get(key)
            if v is not None and str(v).lower() not in ("null", "none", ""):
                filt[key] = v
    return {"query_type": qt, "metadata_filter": filt}


def _sql_node(state: ChatState, db_path: Any) -> ChatState:
    from pathlib import Path

    p = Path(db_path)
    ans = run_sql_chain(state.get("query") or "", p)
    return {"sql_result": ans, "final_answer": ans}


def _rag_node(state: ChatState, retriever: HybridRetriever, reranker: Reranker) -> ChatState:
    q = state.get("query") or ""
    flt = state.get("metadata_filter") or {}
    docs = retriever.retrieve(q, top_k=12, filter_metadata=flt)
    docs = reranker.rerank(q, docs, top_k=5)
    ans = run_rag_chain(q, docs)
    if not docs:
        ans = "검색 결과가 없습니다. 질문을 바꿔서 다시 시도해보세요."
    return {"rag_result": ans, "final_answer": ans}


def _hybrid_node(state: ChatState, db_path: Any, retriever: HybridRetriever, reranker: Reranker) -> ChatState:
    from pathlib import Path

    p = Path(db_path)
    q = state.get("query") or ""
    flt = state.get("metadata_filter") or {}
    sql_ans = run_sql_chain(q, p) or "(SQL 요약 없음)"
    docs = retriever.retrieve(q, top_k=12, filter_metadata=flt)
    docs = reranker.rerank(q, docs, top_k=5)
    rag_ans = run_rag_chain(q, docs) or "(문서 근거 없음)"
    merged = chat_text_completion(
        (
            "하역 SQL 요약과 비고 근거를 합쳐 한국어로 간결히 답한다. 추측은 금지.\n"
            "출력 규칙:\n"
            "1) 내부 필드명/키(bySpecies, byVessel, totalBL, avgRate, count, entry 등)를 절대 노출하지 않는다.\n"
            "2) 숫자는 사용자 친화 표현으로만 제시한다(예: 물량 104,686톤).\n"
            "3) 질문이 니켈 품종 결과를 요구하면 품종명과 물량(톤)만 제시하고, 평균/건수/기술 키워드는 생략한다.\n"
            "4) 응답은 1~3문장으로 짧게 작성한다."
        ),
        f"질문: {q}\n\n[SQL 요약]\n{sql_ans}\n\n[RAG]\n{rag_ans}",
    )
    final = merged or f"{sql_ans}\n\n{rag_ans}"
    return {"sql_result": sql_ans, "rag_result": rag_ans, "final_answer": final}


def build_router_graph(db_path: Any, retriever: HybridRetriever, reranker: Reranker):
    g = StateGraph(ChatState)

    g.add_node("classify", _classify)

    def _sql(s: ChatState) -> ChatState:
        return _sql_node(s, db_path)

    def _rag(s: ChatState) -> ChatState:
        return _rag_node(s, retriever, reranker)

    def _hybrid(s: ChatState) -> ChatState:
        return _hybrid_node(s, db_path, retriever, reranker)

    g.add_node("sql", _sql)
    g.add_node("rag", _rag)
    g.add_node("hybrid", _hybrid)

    g.add_edge(START, "classify")

    def _route(s: ChatState) -> str:
        t = s.get("query_type") or "rag"
        if t == "sql":
            return "sql"
        if t == "hybrid":
            return "hybrid"
        return "rag"

    g.add_conditional_edges("classify", _route, {"sql": "sql", "rag": "rag", "hybrid": "hybrid"})
    g.add_edge("sql", END)
    g.add_edge("rag", END)
    g.add_edge("hybrid", END)

    return g.compile()
