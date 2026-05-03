# 하역 챗봇 검색 기능 강화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 `src/haeyang/` 패키지의 이슈 파싱·LLM 프롬프트·UI·테스트를 지침에 맞게 강화해 챗봇 검색 품질을 높인다.

**Architecture:** 기존 `backend/main.py` ↔ `src/haeyang/` 연동은 그대로 유지하며, `preprocess.py`의 `parse_issues`를 줄 단위 파싱으로 재작성하고, `router/rag/sql` 체인의 프롬프트를 교체한다. `app.py`에 표시 전용 사이드바 필터와 예시 질문 5개를 추가한다.

**Tech Stack:** Python 3.11+, LangChain, LangGraph, ChromaDB, rank-bm25, sentence-transformers, OpenAI API, Streamlit, pytest

---

### Task 1: preprocess.py — parse_issues 줄별 시간 추출 재작성

**Files:**
- Modify: `src/haeyang/preprocess.py`
- Test: `tests/test_haeyang.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_haeyang.py` 파일 맨 아래에 다음 테스트를 추가한다:

```python
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
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

```bash
cd /Users/jo/Desktop/프로젝트
python -m pytest tests/test_haeyang.py::test_parse_issues_per_line -v
```

Expected: FAIL — `AssertionError` (현재는 모든 카테고리가 첫 번째 시간값 공유)

- [ ] **Step 3: parse_issues 재작성**

`src/haeyang/preprocess.py`의 `parse_issues` 함수를 아래로 교체한다:

```python
def parse_issues(raw_remark: str) -> list[dict[str, Any]]:
    """
    비고를 줄 단위로 분리해 카테고리별로 시간을 개별 추출한다.
    같은 카테고리가 여러 줄에 걸쳐 있으면 duration_hours를 누산한다.
    """
    if not raw_remark:
        return []
    text = unicodedata.normalize("NFKC", raw_remark)
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
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python -m pytest tests/test_haeyang.py::test_parse_issues_per_line -v
```

Expected: PASS

- [ ] **Step 5: 기존 테스트도 모두 통과 확인**

```bash
python -m pytest tests/test_haeyang.py -v
```

Expected: 모든 테스트 PASS

- [ ] **Step 6: 커밋**

```bash
git add src/haeyang/preprocess.py tests/test_haeyang.py
git commit -m "feat: parse_issues 줄별 시간 개별 추출로 재작성 + 테스트 추가"
```

---

### Task 2: router.py — ROUTING_PROMPT 강화

**Files:**
- Modify: `src/haeyang/router.py`
- Test: `tests/test_haeyang.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_haeyang.py`에 추가:

```python
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
```

- [ ] **Step 2: 테스트 실행 (현재도 통과할 수 있음을 확인)**

```bash
python -m pytest tests/test_haeyang.py::test_router_classify_rag_issue -v
```

Expected: PASS (monkeypatch이므로 프롬프트 내용 무관하게 통과. 프롬프트 변경 후에도 유지되는지 확인용)

- [ ] **Step 3: ROUTING_PROMPT 교체**

`src/haeyang/router.py`의 `ROUTING_PROMPT` 상수를 아래로 교체한다:

```python
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
```

- [ ] **Step 4: 테스트 재실행**

```bash
python -m pytest tests/test_haeyang.py -v
```

Expected: 모든 테스트 PASS

- [ ] **Step 5: 커밋**

```bash
git add src/haeyang/router.py tests/test_haeyang.py
git commit -m "feat: ROUTING_PROMPT 예시 기반 분류 기준으로 강화"
```

---

### Task 3: rag_chain.py — RAG_SYSTEM_TEMPLATE 강화

**Files:**
- Modify: `src/haeyang/rag_chain.py`
- Test: `tests/test_haeyang.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_haeyang.py`에 추가:

```python
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
```

- [ ] **Step 2: 테스트 실행 (현재 구현으로 통과 여부 확인)**

```bash
python -m pytest tests/test_haeyang.py::test_rag_chain_passes_context -v
```

Expected: PASS (context 전달 로직은 이미 존재. 프롬프트 변경 후에도 유지 확인용)

- [ ] **Step 3: RAG_SYSTEM_TEMPLATE 교체**

`src/haeyang/rag_chain.py`의 `RAG_SYSTEM_TEMPLATE` 상수를 아래로 교체한다:

```python
RAG_SYSTEM_TEMPLATE = """
당신은 항만 하역 운영 전문가이다.
제공된 컨텍스트(하역 기록 및 이슈 비고)만 사용해 답한다.

답변 규칙:
1. 컨텍스트에 없는 내용은 절대 추측하지 않는다.
2. 선박명, 월, 품종, 하역률, 비고 요지를 구체적으로 인용한다.
3. 시간 표기를 정확히 해석한다:
   - '(4:05)' → 4시간 5분
   - '(4:05/2=2:02)' → CSU 2기 운용 시 각 2시간 2분 (총 4시간 5분)
4. 이슈 카테고리를 명확히 구분한다:
   - 돌발정비: 예상치 못한 설비 고장
   - SNNC 설비트러블: 수전해 설비(고객사) 관련 트러블
   - 화물이슈: 수분, 대형괴광, 점성 등 화물 품질 문제
   - 기상불량: 우천, 한파 등 날씨 요인
   - 철편검출: 금속 이물질 검출

컨텍스트:
{context}

질문: {question}
"""
```

- [ ] **Step 4: 테스트 재실행**

```bash
python -m pytest tests/test_haeyang.py -v
```

Expected: 모든 테스트 PASS

- [ ] **Step 5: 커밋**

```bash
git add src/haeyang/rag_chain.py tests/test_haeyang.py
git commit -m "feat: RAG_SYSTEM_TEMPLATE 시간 해석·이슈 카테고리 규칙 추가"
```

---

### Task 4: sql_chain.py — SQL_SYSTEM_PROMPT 보완

**Files:**
- Modify: `src/haeyang/sql_chain.py`

- [ ] **Step 1: SQL_SYSTEM_PROMPT 교체**

`src/haeyang/sql_chain.py`의 `SQL_SYSTEM_PROMPT` 상수를 아래로 교체한다:

```python
SQL_SYSTEM_PROMPT = """
당신은 하역률 SQLite DB용 SELECT 쿼리만 생성한다.

테이블 스키마:
- coal_records: 석탄 하역 데이터
  컬럼: 척수, 월, year, 선박명, 품종, 하역량_톤, 착수, 완료, 소요일, 조정, 최종소요일,
        하역률, 현장교대, raw_비고, issue_categories, total_delay_hours,
        has_emergency_maintenance, has_cargo_issue, has_weather_delay, cargo_type
- nickel_records: 니켈 하역 데이터 (coal_records 컬럼 + 항차, 작업시간, 작업대기시간, 조업율, TH)

규칙:
1. 반드시 SELECT 한 문장만. 세미콜론 금지.
2. 하역률 단위는 톤/일 (컬럼명: "하역률").
3. 월은 1~12 정수 컬럼 `월`. 연도는 4자리 정수 컬럼 `year`.
4. 집계 결과는 round(..., 1)로 소수점 1자리 반올림.
5. 한글 컬럼명은 큰따옴표로 감싼다: "하역률", "선박명", "하역량_톤", "raw_비고" 등.
6. 이슈 여부는 has_emergency_maintenance, has_cargo_issue, has_weather_delay 컬럼(0/1)으로 필터링.
7. total_delay_hours: 해당 항차의 총 지연 시간 합계(시간 단위).

응답은 JSON만: {"sql": "SELECT ...", "explanation_hint": "한 줄 요약"}
"""
```

- [ ] **Step 2: 기존 테스트 모두 통과 확인**

```bash
python -m pytest tests/test_haeyang.py -v
```

Expected: 모든 테스트 PASS

- [ ] **Step 3: 커밋**

```bash
git add src/haeyang/sql_chain.py
git commit -m "feat: SQL_SYSTEM_PROMPT 스키마·규칙 보완"
```

---

### Task 5: app.py — 사이드바 필터 UI + 예시 질문 5개

**Files:**
- Modify: `app.py`

- [ ] **Step 1: app.py 수정**

`app.py` 전체를 아래로 교체한다:

```python
"""
로컬에서 Streamlit으로 하역 챗봇을 시험할 때 사용합니다.
실서비스 UI는 FastAPI `unloading_data.html` + `/api/unloading-data/chat` 입니다.

실행: streamlit run app.py  (프로젝트 루트, .venv 활성화)
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _load_rows():
    from backend.main import _get_unloading_dataset, _haeyang_source_fingerprint

    return _get_unloading_dataset(), _haeyang_source_fingerprint()


st.set_page_config(page_title="7선석 하역률 챗봇", layout="wide")
st.title("7선석 하역률 챗봇 (Streamlit)")

with st.sidebar:
    st.header("검색 필터")
    st.caption("필터는 참고용 표시입니다. 챗봇은 질문 내용을 기준으로 답변합니다.")
    cargo_filter = st.selectbox("화물 종류", ["전체", "석탄", "니켈"])
    month_filter = st.multiselect("월 선택", list(range(1, 13)), format_func=lambda m: f"{m}월")
    st.divider()
    st.header("안내")
    st.caption(
        "질문에 연도·화종(석탄/니켈)·월·선명이 포함되면 라우터가 검색 필터로 반영합니다. "
        "OPENAI_API_KEY와 의존성 설치가 필요합니다."
    )

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

example_questions = [
    "3월 평균 하역률은?",
    "돌발정비가 발생한 선박 목록을 알려줘",
    "하역률이 가장 낮았던 선박의 원인은?",
    "CSU2호 관련 정비 이슈를 정리해줘",
    "수분이 높은 화물로 인한 하역 지연 사례는?",
]

cols = st.columns(len(example_questions))
for col, q in zip(cols, example_questions):
    if col.button(q, key=f"btn_{hash(q) % 100000}"):
        st.session_state["_pending_example"] = q

prompt = st.chat_input("질문을 입력하세요")
prompt = st.session_state.pop("_pending_example", None) or prompt

if prompt:
    from haeyang.chatbot import enhanced_chat_answer

    st.session_state.messages.append({"role": "user", "content": prompt})
    rows, fp = _load_rows()
    with st.spinner("답변 생성 중…"):
        ans = enhanced_chat_answer(prompt, None, ROOT, rows, fp)
        if not ans:
            ans = (
                "강화 챗봇을 실행할 수 없습니다. "
                "OPENAI_API_KEY, `pip install -r requirements.txt`, 하역 엑셀 데이터를 확인하세요."
            )
    st.session_state.messages.append({"role": "assistant", "content": ans})
    st.rerun()
```

- [ ] **Step 2: Streamlit 문법 확인 (import 오류 없는지)**

```bash
python -c "import ast; ast.parse(open('app.py').read()); print('syntax ok')"
```

Expected: `syntax ok`

- [ ] **Step 3: 커밋**

```bash
git add app.py
git commit -m "feat: app.py 사이드바 필터 UI + 예시 질문 5개"
```

---

### Task 6: 전체 테스트 최종 확인

**Files:**
- Test: `tests/test_haeyang.py`

- [ ] **Step 1: 전체 테스트 실행**

```bash
python -m pytest tests/test_haeyang.py -v
```

Expected output (7개 테스트 모두 PASS):
```
tests/test_haeyang.py::test_rows_to_dataframes_smoke PASSED
tests/test_haeyang.py::test_router_classify_sql PASSED
tests/test_haeyang.py::test_router_classify_hybrid PASSED
tests/test_haeyang.py::test_parse_time_from_text PASSED
tests/test_haeyang.py::test_parse_issues_per_line PASSED
tests/test_haeyang.py::test_router_classify_rag_issue PASSED
tests/test_haeyang.py::test_rag_chain_passes_context PASSED
```

- [ ] **Step 2: 최종 커밋**

```bash
git add -A
git commit -m "chore: 하역 챗봇 검색 강화 구현 완료"
```
