# Railway 배포 절차

이 저장소는 **FastAPI 하나**가 API와 루트의 `index.html`, `schedule.html` 등 정적 화면을 함께 서빙합니다. 프론트를 별도 빌드할 필요 없이 **웹 서비스 한 개**로 배포하면 됩니다.

## 사전 준비

1. [Railway](https://railway.com) 계정, [GitHub](https://github.com)에 이 프로젝트 푸시
2. (선택) 하역 SQL·챗봇 RAG에 PostgreSQL을 쓰려면 Railway에서 **PostgreSQL** 리소스 추가 후 `DATABASE_URL` 연결

## 1) 새 프로젝트·서비스 만들기

1. Railway 대시보드 → **New Project** → **Deploy from GitHub repo**
2. 이 저장소 선택
3. 생성된 **서비스**가 루트에서 빌드되도록 둠 (Root Directory 변경 불필요)

## 2) 빌드 방식

저장소 루트의 `railway.toml`이 **Dockerfile** 빌드를 사용하도록 되어 있습니다.

- `Dockerfile` → `requirements.txt` 설치 후 `uvicorn` 실행
- 컨테이너 시작 시 **`PORT` 환경변수**를 Railway가 주입하며, 이미지의 `CMD`가 이를 사용합니다.

로컬에서 이미지만 검증하려면:

```bash
docker build -t port-ops-app .
docker run --rm -p 8000:8000 -e PORT=8000 port-ops-app
```

브라우저에서 `http://localhost:8000/api/health` 확인.

## 3) 환경 변수 (서비스 → Variables)

필수는 없을 수 있으나 **운영에서는 꼭 설정**하는 것을 권장합니다.

| 변수 | 설명 |
|------|------|
| `SESSION_SECRET` | 세션 쿠키 서명용 임의 긴 문자열 |
| `PLATFORM_BOOTSTRAP_USER` / `PLATFORM_BOOTSTRAP_PASSWORD` | 최초 `data/platform_users.json` 없을 때만 적용되는 부트스트랩 계정 |
| `DATABASE_URL` | Railway Postgres 연결 문자열(플러그인 연결 시 자동 주입되는 경우 많음). 없으면 하역 SQL 경로는 SQLite 등 로컬 파일 쪽으로 동작 |
| `OPENAI_API_KEY`, `TAVILY_API_KEY` | 뉴스·챗봇 기능용(선택) |

`.env` 예시는 저장소의 `.env.example` 참고.

## 4) 헬스체크

`railway.toml`의 `healthcheckPath`는 `/api/health` 입니다. 배포 후 **Deployments** 로그에서 통과 여부를 확인하세요.

## 5) 배포 URL·도메인

서비스 → **Settings** → **Networking** → **Generate Domain** 으로 공개 URL을 발급합니다.  
커스텀 도메인은 같은 화면에서 연결합니다.

## 데이터 영속성 (중요)

스케줄·반출·야드 시뮌·플랫폼 사용자 등은 기본적으로 서버 디스크의 **`data/`** 및 **`backdata/uploads/`** 에 JSON·파일로 저장됩니다.

- Railway **기본 디스크는 재배포 시 초기화될 수 있어**, 중요 데이터는 **Volume**을 `/app/data` 등에 마운트하거나, `DATABASE_URL`로 SQL 저장소를 쓰는 방식을 검토하세요.
- 하역 엑셀 업로드는 `backdata/uploads/` 를 사용합니다. 동일하게 볼륨 또는 외부 스토리지 전략이 필요할 수 있습니다.

## CLI로 배포 (선택)

[Railway CLI](https://docs.railway.com/develop/cli) 설치 후:

```bash
railway login
railway link   # 프로젝트 연결
railway up    # 또는 Git 연동 시 push만으로 자동 배포
```

## 문제 해결

- **빌드 실패**: 로그에서 `pip install` 오류 확인. Python 버전은 `Dockerfile`의 베이스 이미지(`python:3.12-slim`) 기준입니다.
- **502 / 앱이 안 뜸**: `PORT`를 앱이 듣고 있는지 확인. 이 프로젝트 Dockerfile은 `${PORT:-8000}` 을 사용합니다.
- **정적 페이지 404**: 루트에 `index.html` 등이 포함되어 커밋되었는지, 빌드 컨텍스트가 저장소 루트인지 확인하세요.
