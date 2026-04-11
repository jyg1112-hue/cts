from __future__ import annotations

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
- "sql": 수치 조회, 집계, 순위, 날짜 기반 쿼리
  예) "3월 평균 하역률", "하역량이 가장 많은 선박", "1월~3월 석탄 총 하역량", "하역률 상위 5개 선박"

- "rag": 이슈 내용, 원인 분석, 정비 내역, 화물 상태 쿼리
  예) "CSU2호 관련 정비 이슈", "수분이 높은 화물로 인한 문제", "철편검출이 많았던 사례", "돌발정비 발생 경위"

- "hybrid": 수치 + 이슈/원인을 함께 요구하는 쿼리
  예) "하역률이 낮았던 선박의 원인", "3월에 돌발정비가 발생한 선박의 하역률", "기상불량으로 지연된 선박의 실적"

필터 (언급이 없으면 반드시 null):
- month: 1~12 정수 또는 null
- year: 4자리 연도 정수 또는 null
- ship_name: 선박명 일부 문자열 또는 null
- cargo_type: "coal" | "nickel" | null
- 품종: 품종 문자열 일부(인니, 러시아, 호주 등) 또는 null

반환 형식 (JSON만, 설명 없이):
{"query_type":"sql"|"rag"|"hybrid","month":null,"year":null,"ship_name":null,"cargo_type":null,"품종":null}

질문:
"""


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
    filt: dict[str, Any] = {}
    if data:
        for key in ("month", "year", "ship_name", "cargo_type", "품종"):
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
        "하역 SQL 요약과 비고 근거를 합쳐 한국어로 간결히 답한다. 추측은 금지.",
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
