# 설계: 하역 엑셀 파일 저장소 → Supabase Storage 이전

**날짜:** 2026-04-14  
**범위:** 2단계 — 하역 엑셀 파일 휘발 문제 해결

---

## 배경

Render free plan은 파일시스템이 ephemeral(임시)이라 서비스 재시작 시 `backdata/uploads/`에 올린 엑셀 파일이 모두 사라진다. 이를 Supabase Storage로 이전해 영구 보존한다.

---

## 아키텍처

### 추가

| 항목 | 내용 |
|------|------|
| Python 패키지 | `supabase` (supabase-py) |
| Supabase 버킷 | `unloading-excel` (private) |
| 환경변수 (Render) | `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` |

### 변경 (backend/main.py)

| 기존 함수 | 변경 내용 |
|-----------|-----------|
| `_ensure_upload_dir()` | Supabase Storage 클라이언트 헬퍼로 교체 |
| `_uploaded_excel_files()` | Storage bucket list로 교체 |
| `_uploaded_excel_file_details()` | Storage 메타 기반으로 교체 |
| `_get_unloading_dataset()` | bytes 다운로드 → tempfile → pandas 파싱 |
| `upload_unloading_excel()` | Storage upload로 교체 |
| `delete_uploaded_unloading_excel()` | Storage remove로 교체 |

### 변경 없음

- 기본 번들 파일 `backdata/(2025년) 7선석 하역률.xls` — 업로드 파일 없을 때 fallback 유지
- API 경로 및 요청·응답 형식 — 프론트엔드 변경 없음
- 파일명 패턴 `YYYY_하역률.xls|xlsx` — 유지

---

## 데이터 흐름

### 업로드

```
프론트 → POST /api/unloading-data/upload
  → 파일명 검증 (YYYY_하역률.xlsx 패턴)
  → supabase.storage.from_('unloading-excel').upload(target_name, content)
  → 감사 로그 기록
  → 버킷 파일 목록 반환
```

### 파싱 (조회/챗봇 호출 시)

```
GET /api/unloading-data/summary or /chat
  → Storage 파일 목록 조회
  → 없으면 로컬 fallback 파일 사용
  → 있으면 각 파일을 bytes로 다운로드
     → tempfile.NamedTemporaryFile에 저장
     → pandas로 파싱
     → 임시 파일 삭제
```

### 삭제

```
DELETE /api/unloading-data/upload/{file_name}
  → 파일명 패턴 검증
  → supabase.storage.from_('unloading-excel').remove([file_name])
  → 감사 로그 기록
  → 버킷 파일 목록 반환
```

---

## 에러 처리

| 상황 | 처리 |
|------|------|
| `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` 미설정 | 500 + 명확한 에러 메시지 |
| Storage 업로드 실패 | 기존 HTTPException 패턴 유지 |
| 파싱 중 Storage 연결 실패 | 로컬 fallback 파일로 대체 |

---

## 구현 순서

1. `requirements.txt`에 `supabase` 추가
2. Supabase 대시보드에서 `unloading-excel` 버킷 생성
3. `backend/main.py` 수정
   - Storage 클라이언트 헬퍼 함수 추가
   - 파일 목록/업로드/삭제 함수 교체
   - 데이터셋 파싱 함수에서 tempfile 방식 적용
4. Render 환경변수 `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` 추가
5. 동작 확인 (업로드 → 재시작 → 데이터 유지 여부)
