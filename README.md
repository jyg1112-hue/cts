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
