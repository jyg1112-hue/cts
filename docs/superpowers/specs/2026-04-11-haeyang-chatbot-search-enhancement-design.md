# 7선석 하역률 챗봇 검색 기능 강화 설계

**날짜**: 2026-04-11  
**접근 방식**: A — 기존 `src/haeyang/` 패키지 유지, 차이나는 부분만 타겟 수정  
**목표**: 지침 기반으로 이슈 파싱 정확도·LLM 프롬프트 품질·UI·테스트를 강화

---

## 1. 범위

기존 파일 6개를 수정한다. `db_builder.py`, `retriever.py`, `reranker.py`, `chatbot.py`는 변경하지 않는다.

| 파일 | 변경 유형 |
|------|----------|
| `src/haeyang/preprocess.py` | `parse_issues` 로직 재작성 |
| `src/haeyang/router.py` | `ROUTING_PROMPT` 교체 |
| `src/haeyang/rag_chain.py` | `RAG_SYSTEM_TEMPLATE` 교체 |
| `src/haeyang/sql_chain.py` | `SQL_SYSTEM_PROMPT` 보완 |
| `app.py` | 사이드바 필터 UI + 예시 질문 5개 |
| `tests/test_haeyang.py` | 테스트 케이스 3개 추가 |

---

## 2. preprocess.py — parse_issues 개선

### 문제
현재 구현은 비고 전체 텍스트를 대상으로 `parse_time_from_text`를 한 번만 호출한다.  
결과: 여러 이슈가 있을 때 모든 카테고리가 동일한 시간값을 공유한다.

```
입력: "돌발정비(CSU2 붐업 불가)(6:04)\nSNNC 설비트러블(1:30)"
현재: 돌발정비 → 6.07h, SNNC설비트러블 → 6.07h  (둘 다 첫 번째 시간 공유)
목표: 돌발정비 → 6.07h, SNNC설비트러블 → 1.5h   (줄별 개별 추출)
```

### 변경 방식
1. 비고 텍스트를 `\n` 및 `/` 기준으로 줄 단위 분리
2. 각 줄에서 이슈 카테고리 키워드 검색
3. 해당 줄에서만 `parse_time_from_text` 호출 → 개별 `duration_hours` 저장
4. 카테고리가 이미 등록된 경우 `duration_hours`를 누산

### 영향
- `total_delay_hours` 계산 정확도 향상
- `has_emergency_maintenance`, `has_cargo_issue`, `has_weather_delay` 플래그 신뢰도 향상
- ChromaDB Document 메타데이터 품질 향상 → 필터 검색 정확도 향상

---

## 3. router.py — ROUTING_PROMPT 교체

### 변경 내용
지침의 예시 기반 분류 기준으로 교체한다.

**SQL 경로 예시 추가**
- "3월 평균 하역률", "하역량이 가장 많은 선박", "1월~3월 석탄 총 하역량"

**RAG 경로 예시 추가**
- "CSU2호 관련 정비 이슈", "수분이 높은 화물로 인한 문제", "철편검출이 많았던 사례"

**Hybrid 경로 예시 추가**
- "하역률이 낮았던 선박의 원인", "3월에 돌발정비가 발생한 선박의 하역률"

**필터 추출 규칙**
- `year` 추출 명시 (4자리 연도)
- 없으면 `null` 반환 규칙 유지

---

## 4. rag_chain.py — RAG_SYSTEM_TEMPLATE 교체

### 변경 내용
시간 표기 해석 규칙과 이슈 카테고리 설명을 추가한다.

**시간 해석 규칙**
```
- '(4:05)' → 4시간 5분
- '(4:05/2=2:02)' → CSU 2기 운용 시 각 2시간 2분 (총 4시간 5분)
```

**이슈 카테고리 설명 5종**
```
- 돌발정비: 예상치 못한 설비 고장
- SNNC 설비트러블: 수전해 설비(고객사) 관련 트러블
- 화물이슈: 수분, 대형괴광, 점성 등 화물 품질 문제
- 기상불량: 우천, 한파 등 날씨 요인
- 철편검출: 금속 이물질 검출
```

**기존 규칙 유지**
- 컨텍스트에 없는 내용 추측 금지
- 선박명·월·품종·하역률·비고 구체적 인용

---

## 5. sql_chain.py — SQL_SYSTEM_PROMPT 보완

### 변경 내용
- 집계 시 `round(..., 1)` 명시 (소수점 1자리)
- 한글 컬럼명 큰따옴표 규칙 예시 추가: `"하역률"`, `"선박명"`
- `total_delay_hours` 컬럼 스키마 설명 추가

---

## 6. app.py — UI 보강

### 사이드바
```python
cargo_filter = st.selectbox("화물 종류", ["전체", "석탄", "니켈"])
month_filter = st.multiselect("월 선택", list(range(1, 13)))
```
- 표시 전용. 챗봇 호출 시 필터로 전달하지 않는다.
- 라우터가 질문 텍스트에서 자동 추출하는 현행 방식 유지.

### 예시 질문 (3개 → 5개)
```python
example_questions = [
    "3월 평균 하역률은?",
    "돌발정비가 발생한 선박 목록을 알려줘",
    "하역률이 가장 낮았던 선박의 원인은?",
    "CSU2호 관련 정비 이슈를 정리해줘",
    "수분이 높은 화물로 인한 하역 지연 사례는?",
]
```

---

## 7. tests/test_haeyang.py — 테스트 추가

### 추가 테스트 3개

**test_parse_issues_per_line**
- 입력: `"돌발정비(6:04)\nSNNC 설비트러블(1:30)"`
- 기대: 돌발정비 `duration_hours ≈ 6.07`, SNNC설비트러블 `duration_hours ≈ 1.5`
- 목적: 줄별 시간 개별 추출 확인

**test_rag_chain_returns_docs (monkeypatch)**
- 입력: `"CSU2호 feeder 관련 이슈"` 질문 + 더미 Document 목록
- 기대: `run_rag_chain` 호출 시 `chat_text_completion` 에 context 전달됨
- 목적: RAG 체인이 문서를 context로 사용하는지 확인

**test_router_classify_rag**
- 입력: `"수분이 높은 화물 문제"` 질문
- mock: `chat_json_completion` → `{"query_type": "rag", ...}`
- 기대: `_classify` 결과 `query_type == "rag"`
- 목적: 이슈 질문의 RAG 분류 확인

---

## 8. 적용하지 않는 것

- `db_builder.py` — 현행 유지
- `retriever.py` — BM25 0.3 / Semantic 0.7 가중치 현행과 일치, 변경 없음
- `reranker.py` — 현행 유지
- `chatbot.py` — 현행 유지
- `backend/main.py` — 연동 유지, 변경 없음
- 사이드바 필터 → 챗봇 전달 없음 (질문 텍스트 기반 자동 추출 유지)

---

## 9. 데이터 흐름 (변경 없음)

```
엑셀 → backend/main.py(_get_unloading_dataset)
       → preprocess.rows_to_dataframes + build_all_documents
       → db_builder.(build_sqlite + build_vector_db + build_bm25_index)
       → chatbot.get_or_build_context
       → router.build_router_graph
            ├─ SQL → sql_chain.run_sql_chain
            ├─ RAG → retriever.retrieve → reranker.rerank → rag_chain.run_rag_chain
            └─ Hybrid → SQL + RAG → LLM 종합
```
