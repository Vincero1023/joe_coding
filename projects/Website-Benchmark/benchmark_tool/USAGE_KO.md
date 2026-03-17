# benchmark_tool 사용 문서

## 개요

`benchmark_tool`은 `input/` 폴더 안의 HTML 파일들을 한 번에 분석해서 다음 두 가지를 생성합니다.

1. 통합 분석 결과 JSON
2. 가이드/블로그성 콘텐츠 추출 파일

핵심 목적은 다음과 같습니다.

- 사이트가 어떤 서비스인지 빠르게 추론
- 핵심 기능을 목적 중심 `features` 구조로 정리
- 수익 모델, 데이터 출처, 비즈니스 로직 추정
- 재구현이나 벤치마킹에 바로 쓸 수 있는 JSON 생성

## 실행 방법

프로젝트 루트에서 실행합니다.

```bash
python benchmark_tool/main.py
```

입력 폴더와 출력 폴더를 직접 지정할 수도 있습니다.

```bash
python benchmark_tool/main.py --input-dir benchmark_tool/input --output-dir benchmark_tool/output
```

## 입력 데이터

- 지원 형식: `.html`, `.htm`
- 위치: 기본값 `benchmark_tool/input/`
- 권장 방식:
  - 같은 서비스의 여러 페이지 HTML을 한 폴더에 넣기
  - 랜딩, 실제 기능 화면, 가이드/블로그 페이지를 함께 넣기

## 출력 데이터

기본 출력 경로는 `benchmark_tool/output/` 입니다.

- `site_analysis.json`
- `content/guide_N.html`
- `content/guide_N.md`

## site_analysis.json 해독법

`site_analysis.json`은 사람이 읽는 보고서가 아니라, 다른 프로그램이나 AI가 바로 활용할 수 있도록 만든 구조입니다.

### 최상위 필드

- `pages_analyzed`
  - 분석한 HTML 파일 개수

- `source_files`
  - 분석에 사용한 원본 파일 목록

- `site_type`
  - 사이트 성격 분류
  - 예: `["keyword_tool", "content_site"]`

- `important_keywords`
  - 사이트 텍스트에서 강하게 감지된 중요 키워드
  - 예: `["CPC", "검색량", "키워드", "확장", "추천"]`

- `core_functions`
  - 사이트의 핵심 기능 집합
  - 현재 예:
    - `keyword_analysis`
    - `keyword_expansion`
    - `scoring_system`
    - `data_filtering`
    - `content_guidance`

- `monetization_model`
  - 사이트가 어떻게 수익을 내는지에 대한 추정
  - 예: `CPC 기반 키워드 분석 SaaS`

- `data_source`
  - 데이터 출처 추정
  - 예: `네이버 검색 데이터 추정`

- `business_logic`
  - 서비스 전체 수준의 핵심 비즈니스 로직
  - 예:
    - `고CPC 키워드 우선 노출`
    - `검색량 + 경쟁도 조합 분석`
    - `CPC 기반 키워드 점수화`

- `ui_components`
  - 전체 사이트에서 대표적으로 보이는 UI 구조
  - 예:
    - `{"type":"input","role":"keyword search"}`
    - `{"type":"table","role":"data results"}`

- `user_flow`
  - 사이트 수준 사용자 흐름 요약

- `data_inputs`
  - 전체 사이트에서 핵심 입력 구조 요약

- `data_outputs`
  - 전체 사이트에서 핵심 출력 구조 요약

- `api_patterns`
  - HTML/스크립트에서 감지된 API 패턴

- `feature_logic`
  - 기능별 실제 처리 로직 추정
  - 예:
    - `keyword_analysis`: 입력 키워드의 검색량, CPC, 경쟁도 데이터 조회
    - `keyword_scoring`: CPC + 검색량 + 경쟁도 기반 점수 계산

- `features`
  - 가장 중요한 필드
  - AI가 "무슨 기능을 선택해서 구현/호출할지" 판단할 때 쓰는 목적 중심 구조

- `content_exports`
  - 추출된 가이드/블로그 콘텐츠 파일 정보

## features 필드 해독법

`features`는 기능 이름이 아니라 "목적" 중심으로 정리되어 있습니다.

형식:

```json
{
  "goal": "",
  "description": "",
  "inputs": [],
  "outputs": [],
  "logic": [],
  "ui": []
}
```

### 각 필드 의미

- `goal`
  - 이 기능의 목적
  - 예: `키워드 검색`, `점수 계산`, `콘텐츠 제공`

- `description`
  - 어떤 상황에서 이 기능을 선택해야 하는지 설명
  - AI가 기능 선택 분기를 만들 때 가장 중요합니다.

- `inputs`
  - 이 기능이 필요로 하는 입력 구조
  - 예:
    - `{"type":"input","role":"keyword seed"}`
    - `{"type":"filter","role":"metric conditions"}`

- `outputs`
  - 이 기능이 만들어내는 결과 구조
  - 예:
    - `{"type":"table","role":"keyword metrics"}`
    - `{"type":"list","role":"related keyword suggestions"}`

- `logic`
  - 구현 시 반드시 반영해야 하는 처리 규칙
  - `feature_logic`, `user_flow`, `business_logic`를 합쳐서 만든 목적 중심 요약입니다.

- `ui`
  - 프론트에서 대표적으로 필요한 UI 블록
  - 탭/섹션 설계 시 바로 참고하면 됩니다.

## features 예시 해석

### 1. 키워드 검색

- 목적: 검색량, CPC, 경쟁도 조회
- 입력:
  - 키워드 입력
  - 대량 키워드 입력
- 출력:
  - 키워드 지표 테이블
- UI:
  - 검색 입력창
  - 대량 입력 textarea
  - 결과 테이블

이 feature가 있으면 보통 다음 구성으로 구현합니다.

- 프론트:
  - 검색창
  - 실행 버튼
  - 결과 테이블
- 백엔드:
  - 키워드 기준 데이터 조회 API

### 2. 키워드 확장

- 목적: 연관 키워드/추천 키워드 생성
- 입력:
  - 기본 키워드
  - 대량 키워드
- 출력:
  - 추천 키워드 리스트
- UI:
  - 입력창
  - 추천 리스트

### 3. 점수 계산

- 목적: 여러 지표를 조합해 우선순위 계산
- 입력:
  - 키워드
  - 필터 조건
- 출력:
  - 점수 포함 테이블
- 핵심 로직:
  - 검색량 + 경쟁도 조합 분석
  - CPC 기반 키워드 점수화

### 4. 필터링

- 목적: 결과를 조건으로 좁힘
- 입력:
  - 검색량 조건
  - CPC 조건
  - 경쟁도 조건
- 출력:
  - 필터링된 키워드 테이블

### 5. 콘텐츠 제공

- 목적: 가이드/블로그 문서 제공
- 입력:
  - 없음 또는 문서 선택
- 출력:
  - 가이드 글 목록/상세

## AI가 이 JSON을 쓰는 방법

이 JSON은 다음 용도로 바로 사용할 수 있습니다.

### 1. 기능 선택기

`features[].description`을 보고 현재 요구사항에 맞는 기능을 고릅니다.

예:

- "검색량과 CPC를 보여줘" -> `goal = 키워드 검색`
- "연관 키워드까지 뽑아줘" -> `goal = 키워드 확장`
- "우선순위 점수를 계산해줘" -> `goal = 점수 계산`

### 2. 화면 설계기

`features[].ui`를 보고 필요한 화면 블록을 결정합니다.

예:

- `keyword search` -> 검색 입력창
- `data results` -> 테이블
- `keyword suggestions` -> 추천 리스트

### 3. API 설계기

`features[].inputs`, `outputs`, `logic`를 보고 엔드포인트를 설계합니다.

예:

- 입력: `keyword seed`
- 출력: `keyword metrics`
- 로직: `검색량, CPC, 경쟁도 조회`

그러면 `/keywords/analyze` 같은 API 후보를 만들 수 있습니다.

## 권장 해석 순서

이 JSON을 읽을 때는 다음 순서를 권장합니다.

1. `site_type`
2. `core_functions`
3. `monetization_model`
4. `data_source`
5. `business_logic`
6. `features`
7. `content_exports`

이 순서로 보면 사이트 정체성 -> 핵심 기능 -> 구현 대상 기능 -> 참고 콘텐츠 순으로 이해할 수 있습니다.

## 이 프로그램이 현재 잘하는 것

- HTML만으로도 서비스 성격을 비교적 빠르게 추론
- 키워드 툴/콘텐츠 사이트 같은 복합 성격을 함께 분류
- UI 개수 대신 의미 있는 구조 위주로 요약
- 기능을 AI가 선택 가능한 `features` 구조로 정리

## 한계

- 실제 API 호출 성공 여부를 확인하는 도구는 아님
- 정적 HTML에 없는 런타임 데이터는 제한적으로만 추정
- 점수 계산식은 텍스트 기반 추론이므로 실제 운영 로직과 다를 수 있음
- JS 앱이 빈 HTML만 주는 경우 분석 품질이 떨어질 수 있음

## 추천 활용 방식

- 1차 벤치마킹: `site_analysis.json` 읽기
- 2차 재구현: `features` 기준으로 탭/기능 나누기
- 3차 UI 설계: `ui`, `inputs`, `outputs` 참고
- 4차 백엔드 설계: `logic`, `data_source`, `business_logic` 참고

