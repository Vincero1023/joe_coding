# Keyword_Forge

수익성 중심 키워드 워크플로우를 위한 모듈형 백엔드 프로젝트입니다.  
키워드를 수집하고, 확장하고, 수익성 기준으로 분석한 뒤, 골든 키워드만 선별하는 흐름을 FastAPI 기반 API로 구성합니다.

## 현재 구현 상태

- `collector`
  - 벤치마크 분석 JSON을 읽어 수집 전략을 추론합니다.
  - 샘플 HTML 구조를 해석해 키워드와 카테고리를 수집합니다.
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
  - 아직 구현 전입니다.

## 처리 흐름

1. `collector`가 키워드를 수집합니다.
2. `expander`가 실데이터와 규칙 기반으로 키워드를 확장합니다.
3. `analyzer`가 CPC, bid, volume, competition을 바탕으로 점수를 계산합니다.
4. `selector`가 실제 수익 가능성이 높은 골든 키워드만 남깁니다.

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

## 실행 메모

각 모듈은 개별 실행 예시를 포함합니다.

- `python app/collector/main.py`
- `python app/expander/main.py`
- `python app/analyzer/main.py`
- `python app/selector/main.py`

## 다음 작업

- `title_gen` 구현
- 모듈 간 전체 파이프라인 통합
- 테스트 보강 및 API 계약 정리
