# Port Operation Web App

기존 `index.html`, `schedule.html` 기반 화면에 FastAPI 백엔드를 붙여서
프론트엔드 + 백엔드 통합 배포가 가능하도록 구성한 프로젝트입니다.

## 프로젝트 구조

- `index.html`: 메인 화면
- `schedule.html`: 하역 스케줄 화면
- `backend/main.py`: API + 페이지 라우팅 서버
- `api/index.py`: Vercel Serverless Function 진입점
- `vercel.json`: Vercel 빌드/라우팅 설정
- `requirements.txt`: Python 의존성
- `Dockerfile`: 컨테이너 배포 설정

## 로컬 실행

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

브라우저 접속:

- 메인: `http://localhost:8000/`
- 스케줄: `http://localhost:8000/schedule`
- 헬스체크: `http://localhost:8000/api/health`

### 하역 대시보드 · 공급 이슈(뉴스)

- `GET /api/supply-news?cargo_type=nickel` 또는 `cargo_type=coal`
- **`.env` 로딩**: `backend/main.py` 시작 시 프로젝트 루트의 `.env`를 `python-dotenv`로 읽습니다.
- **`TAVILY_API_KEY`** 가 있으면 [Tavily Search](https://tavily.com/)(`topic=news`, 최근 한 달)로 기사를 가져옵니다. 없거나 결과가 없으면 **Google News RSS**로 대체합니다.
- **`OPENAI_API_KEY`** 가 있으면 제목·스니펫을 바탕으로 **한국어 제목 + 2문장 요약**을 생성합니다. 없으면 영문 스니펫 위주로 표시합니다.
- (선택) `OPENAI_SUPPLY_NEWS_MODEL`(기본 `gpt-4o-mini`), `TAVILY_SEARCH_DEPTH`(기본 `basic`, `advanced`는 크레딧 2배).

`.env` 는 저장소에 커밋하지 마세요. 키가 유출되면 즉시 재발급하세요.

## Docker 실행

```bash
docker build -t port-ops-app .
docker run -p 8000:8000 port-ops-app
```

## 배포 (Vercel)

1. 이 폴더를 GitHub 저장소로 푸시
2. Vercel에서 프로젝트 Import
3. Framework Preset은 `Other`로 둬도 무방
4. Root Directory는 저장소 루트(`0327_2`) 선택
5. Deploy 실행

`vercel.json`이 모든 요청을 `api/index.py`로 전달하고, FastAPI가 `/`, `/schedule`, `/api/health`를 처리합니다.

### Vercel CLI 배포

```bash
npm i -g vercel
vercel
vercel --prod
```
