# Keyword_Forge

수익성 중심 키워드 워크플로우를 위한 모듈형 백엔드 프로젝트입니다.  
키워드를 수집하고, 확장하고, 수익성 기준으로 분석한 뒤, 골든 키워드만 선별하는 흐름을 FastAPI 기반 API로 구성합니다.

## 현재 구현 상태

- 이 프로젝트는 현재 `개인 로컬 실행 도구`를 기준으로 설계합니다.
- Creator Advisor 인증이 필요한 수집은 서버형 SaaS보다 로컬 브라우저 세션 재사용 흐름을 우선합니다.
- `collector`
  - 고정 카테고리 목록을 선택해 실시간 네이버 검색 데이터를 수집합니다.
  - category 모드에서는 Creator Advisor 주제별 인기 유입 검색어를 우선 조회합니다.
  - 자동완성이 비면 네이버 검색 결과 페이지를 긁어 키워드 후보를 보강합니다.
  - `category` 모드와 `seed` 모드를 지원합니다.
- `expander`
  - 다중 엔진 구조(`autocomplete`, `related`, `combinator`)로 확장합니다.
  - 분석 JSON을 전략 가이드로만 사용합니다.
  - 다중 깊이 확장, 필터링, 중복 제거, origin별 제한을 적용합니다.
- `analyzer`
  - 수익성 중심 점수 엔진을 구현했습니다.
  - `profit = cpc * bid`, `opportunity = volume / competition` 구조를 사용합니다.
  - 낮은 점수와 무의미한 키워드를 제거합니다.
- `selector`
  - 분석 결과 중 골든 키워드만 최종 선별합니다.
- `title_gen`
  - 선별된 골든 키워드를 기반으로 네이버 홈형, 블로그형 제목을 생성합니다.
  - `template` 모드와 `AI` 모드를 지원합니다.
  - AI 모드는 `OpenAI`, `Gemini`, `Vertex AI Express Mode`, `Anthropic` provider를 지원합니다.
  - `Vertex AI Express Mode`는 Google Cloud API key 기준으로 붙도록 구현했습니다.
  - 롱테일 `가이드`, `체크리스트`는 기본 강제 후보가 아니라 선택형 의도 토큰으로 다시 조합합니다.
- `pipeline`
  - 수집부터 제목 생성까지 전 단계를 서버에서 한 번에 실행합니다.
- `scheduler / queue`
  - 시드 키워드 배치를 Queue로 등록해 순차 실행할 수 있습니다.
  - 일일 카테고리 루틴을 등록하면 정해진 시각에 Queue 작업을 자동 생성합니다.
  - 실행 결과는 서버에서 `.xlsx` 파일로 내보내 `Status/queue_exports` 아래에 저장합니다.

## 처리 흐름

1. `collector`가 키워드를 수집합니다.
2. `expander`가 실데이터와 규칙 기반으로 키워드를 확장합니다.
3. `analyzer`가 CPC, bid, volume, competition을 바탕으로 점수를 계산합니다.
4. `selector`가 실제 수익 가능성이 높은 골든 키워드만 남깁니다.
5. `title_gen`이 채널별 제목 후보를 생성합니다.

## 기술 스택

- Python
- FastAPI
- Pydantic Settings
- SQLAlchemy
- PostgreSQL
- BeautifulSoup4
- pytest
- Docker / Docker Compose

## API 엔드포인트

- `POST /collect`
- `POST /expand`
- `POST /analyze`
- `POST /select`
- `POST /generate-title`
- `POST /pipeline`
- `POST /local/naver-session`
- `POST /local/naver-login-browser`
- `GET /queue/snapshot`
- `POST /queue/jobs/seed-batch`
- `GET /queue/jobs/{job_id}`
- `GET /queue/jobs/{job_id}/artifact`
- `POST /queue/jobs/{job_id}/cancel`
- `POST /queue/runner/pause`
- `POST /queue/runner/resume`
- `POST /queue/routines/daily-category`
- `DELETE /queue/routines/{routine_id}`

## 실행 메모

각 모듈은 개별 실행 예시를 포함합니다.

- `python app/collector/main.py`
- `python app/expander/main.py`
- `python app/analyzer/main.py`
- `python app/selector/main.py`
- `python app/title_gen/main.py`
- `python app/pipeline/main.py`

로컬 메뉴 실행은 `run_local.bat`를 사용합니다.

- `run_local.bat`
- 메뉴 `7` 또는 `run_local.bat api` 실행 시 FastAPI 서버를 띄우고 브라우저를 자동으로 엽니다.
- 메인 UI에서 `전용 로그인 브라우저 열기` 버튼으로 앱 전용 Edge/Chrome 브라우저를 띄우고, 그 안에서 로그인한 세션을 바로 저장할 수 있습니다.
- `브라우저에서 쿠키 불러오기` 버튼은 기존 Edge/Chrome 세션을 직접 읽는 보조 경로이며, 브라우저 쿠키 DB 잠금/권한 문제로 실패할 수 있습니다.
- Creator Advisor 기준 페이지가 `/naver_blog/...`이면 서비스도 `naver_blog`로 맞춰야 합니다.

## 로컬 시크릿 / 데이터

- 로컬 전용 시크릿 기본 경로는 `.local/credentials/` 입니다.
- 기본 파일명:
  - `.local/credentials/naver_search.credentials.json`
  - `.local/credentials/searchad.credentials.json`
- 루트 `naver_search.credentials.json`, `searchad.credentials.json`도 레거시 fallback으로 계속 읽지만, 새 환경에서는 `.local/credentials/`만 쓰는 쪽을 권장합니다.
- `.local/`, `Status/`, `.tmp_*`, `*.credentials.json`은 git 추적 대상에서 제외하도록 정리했습니다.

## 다음 작업

- Vertex AI Express Mode API key로 실제 제목 생성과 fallback 동작을 수동 확인하기
- Status HTML에 `used_mode`, `fallback_reason`, `provider` 표시를 더 명확히 남기기
