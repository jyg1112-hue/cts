from __future__ import annotations

from langchain_core.documents import Document

from haeyang.openai_json import chat_text_completion

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
5. 답변 마지막에 반드시 출처를 표기한다:
   형식: [출처: 선박명 (월, 품종)]
   예) [출처: HOANH SON STAR (1월, 석탄(러시아)), SM EMERALD (6월, 니켈)]

컨텍스트:
{context}

질문: {question}
"""


def run_rag_chain(question: str, documents: list[Document]) -> str:
    if not documents:
        return "관련 하역 기록을 찾지 못했습니다. 선박명, 월, 화물 종류를 더 구체적으로 입력해보세요."
    parts: list[str] = []
    for i, d in enumerate(documents, start=1):
        parts.append(f"[문서 {i}]\n{d.page_content.strip()}")
    context = "\n\n".join(parts)
    prompt = RAG_SYSTEM_TEMPLATE.format(context=context, question=question)
    out = chat_text_completion(
        "당신은 데이터 근거만 사용하는 하역 분석가입니다.",
        prompt,
    )
    return out if out is not None else ""
