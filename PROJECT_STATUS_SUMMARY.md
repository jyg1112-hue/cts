# 프로젝트 현황 정리 (2026-04-13)

## 1) 프로젝트 개요

이 프로젝트는 항만 운영 웹을 중심으로, 기존 정적 HTML 화면(`index.html`, `schedule.html`, `yard.html`, `banchu.html`, `unloading_data.html`)에 FastAPI 백엔드를 결합해 운영 데이터 조회/업로드/챗 질의를 처리하도록 확장한 통합 플랫폼입니다.

최근에는 다음 두 축이 동시에 진행되고 있습니다.

- 메인 운영 화면(HTML + FastAPI) 고도화
- React 기반 신규 프론트엔드 골격 + 인증 흐름 도입

---

## 2) 현재 아키텍처(요약)

- 백엔드: `backend/main.py` (FastAPI 단일 진입)
- 인증/계정 관리: `backend/platform_auth.py` + 세션 쿠키
- 뉴스 수집/요약: `backend/supply_news.py` (Tavily 우선, RSS fallback, OpenAI 한국어 요약)
- 데이터/AI 질의 엔진: `src/haeyang/` (RAG/SQL/라우팅 체인)
- 프론트:
  - 레거시 운영 화면: 루트 HTML 파일들
  - 신규 UI: `frontend/` (React + TypeScript + Vite)

---

## 3) 구현된 주요 기능

### 3-1. 인증 및 접근 제어

- 로그인 API: `/api/auth/login`, 로그아웃: `/api/auth/logout`, 세션 확인: `/api/auth/me`
- 계정 관리 API: 사용자 목록/추가/삭제, 비밀번호 변경
- 감사 로그: `data/platform_audit.jsonl` 기록
- 보호 라우팅:
  - 백엔드 HTML 라우트 접근 제어 (`/schedule`, `/yard` 등)
  - React 쪽 `ProtectedRoute` + `LoginPage` 도입

### 3-2. 하역 데이터 처리

- 업로드/삭제/메타: `/api/unloading-data/upload`, `/api/unloading-data/upload/{file_name}`, `/api/unloading-data/meta`
- 요약 집계: `/api/unloading-data/summary`
- 대화형 질의: `/api/unloading-data/chat`
- 업로드 엑셀 기반으로 집계/지연/이슈 관련 분석 로직이 `backend/main.py`에 집약됨

### 3-3. 공급망 뉴스 기능

- 엔드포인트: `/api/supply-news?cargo_type=nickel|coal`
- 수집 전략:
  - `TAVILY_API_KEY` 존재 시 Tavily 뉴스 검색
  - 미설정/결과 부족 시 Google News RSS fallback
- 요약 전략:
  - `OPENAI_API_KEY` 존재 시 한국어 제목/요약 생성
  - 실패 시 스니펫 기반 fallback
- 캐시 TTL(15분) 적용으로 호출 비용/속도 균형화

### 3-4. 신규 React 앱 상태

- 라우팅 골격: `frontend/src/App.tsx`
- 인증 컨텍스트: `frontend/src/auth/AuthContext.tsx`
- 로그인 페이지: `frontend/src/pages/LoginPage.tsx`
- 레이아웃/헤더/플레이스홀더 페이지로 확장 준비 상태

---

## 4) 최근 진행 흐름 (커밋 기준)

최근 커밋 로그를 보면, 아래 흐름으로 진화 중입니다.

- 야드 시뮬레이션/차트 기능 도입 및 안정화
- Haeyang 질의 체인(RAG/SQL/라우터) 규칙 개선
- 질의 라우팅/원인 분석 관련 버그 수정
- UI 보강(필터/예시 질문 확대)
- 문서(spec/plan)와 구현이 함께 업데이트되는 방식 정착

즉, 단순 UI 프로젝트가 아니라 **운영 데이터 + AI 질의 + 인증 통제**를 묶는 실무형 플랫폼으로 발전하고 있습니다.

---

## 5) 현재 워킹트리 상태 (미커밋 변경)

현재 저장소는 대규모 작업 중간 상태입니다.

- 수정 파일 다수: `backend/main.py`, `src/haeyang/*.py`, 주요 HTML, `frontend/src/*` 등
- 신규 파일: `backend/platform_auth.py`, React 인증 관련 컴포넌트, 테스트 파일 등
- 데이터/자산 파일 변경도 포함됨(엑셀, 이미지 등)
- 삭제 파일 1건 존재(PPTX)

정리하면, 인증 추가/프론트 확장/AI 질의 로직 개선이 한 브랜치에서 동시에 진행되고 있어, 기능 단위로 커밋 분리하면 추적성과 리뷰 효율이 크게 올라갈 상태입니다.

---

## 6) 지금 시점 권장 정리 순서

1. 인증(백엔드+프론트) 관련 변경을 1차 묶음으로 검증/커밋
2. 하역 챗봇/`src/haeyang` 로직 변경을 2차 묶음으로 분리
3. HTML 화면(야드/스케줄/하역) 수정을 3차 묶음으로 분리
4. 데이터/산출물(엑셀, 이미지, brainstorm 산출물) 커밋 대상 재검토
5. `README.md`를 현재 구조(HTML + React 이중 구조)에 맞게 최신화

---

## 7) 한 줄 결론

프로젝트는 이미 "정적 대시보드" 단계를 지나, **인증/감사/운영 데이터 분석/AI 질의**를 결합한 운영 플랫폼 형태로 확장되었고, 현재는 이를 React 기반 UI로 점진 이관하는 전환 구간입니다.
