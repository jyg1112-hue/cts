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
