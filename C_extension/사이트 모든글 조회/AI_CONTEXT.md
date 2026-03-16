# AI Context

## Project Name
- 워드프레스 수익화 벤치마킹 익스텐션

## Project Type (windows / web-docker / chrome-extension / desktop-gui / scripts / experiments)
- chrome-extension

## One-line Goal
- 사용자가 지정한 워드프레스 기반 사이트의 공개 글 URL을 수집하고, 제목 패턴·키워드·인기 추정·수익화 신호를 분석한다.

## Users & Scenario (누가/언제/어떻게)
- 사용자가 블로그/사이트 주소를 입력하거나 현재 탭 기준으로 실행한다.
- 익스텐션은 공개 엔드포인트를 우선 조회해 글 URL을 수집하고, 수익형 키워드, 머니페이지, 제목 공식, 기회 점수를 화면에 표시한다.

## Inputs (파일/데이터/환경)
- 사이트 기본 URL 또는 현재 활성 탭 URL
- 공개 접근 가능한 `sitemap.xml`, 워드프레스 REST API(`wp-json/wp/v2/...`), RSS, 아카이브 페이지
- Windows 11, Chrome 최신 버전, Manifest V3

## Outputs (결과물 형태, 파일명 규칙)
- 팝업에서 수집/분석 수, 상위 수익 키워드, 머니페이지 후보, 제목 공식, 기회 점수 표시
- TSV/JSON으로 내보낼 수 있는 벤치마킹 결과물
- 실행 단위별 간단한 상태 로그(성공/실패 원인, 수집 개수, 분석 개수)

## Constraints (제약)
- 공개 접근 가능한 정보만 수집한다.
- 로그인, 관리자 페이지, 글쓰기/수정/삭제 관련 경로에는 접근하지 않는다.
- 탐지 회피, 프록시 우회, 헤더 위장, 지문 변조, 계정/세션 은닉 기능은 구현하지 않는다.
- 사이트 부하를 줄이기 위해 보수적 요청 간격과 중복 제거를 적용한다.
- Manifest V3 기준을 지키고 권한은 최소 범위만 선언한다.

## Tech Stack (언어/라이브러리/런타임)
- Chrome Extension Manifest V3
- JavaScript 또는 TypeScript
- HTML/CSS 기반 팝업 UI
- `fetch` 기반 공개 엔드포인트 조회

## Run Methods (CLI/GUI/DOCKER/EXTENSION)
- Chrome의 `확장 프로그램 > 개발자 모드 > 압축해제된 확장 프로그램 로드`
- 팝업에서 사이트 URL 입력 후 수집 실행
- 필요 시 현재 탭 URL 자동 반영

## Done Definition (완료 기준)
- 공개 워드프레스 사이트에서 글 URL 수집과 본문 기반 분석이 모두 동작한다.
- 일반 페이지/REST API/사이트맵 중 가능한 공개 소스를 우선 사용한다.
- 수익형 키워드, 머니페이지, 제목 공식, 기회 점수가 팝업에 표시된다.
- 권한이 최소화되어 있고, 로그인/관리자 경로 비접근 원칙이 코드와 문서에 반영되어 있다.
- DEVLOG에 검증 결과와 예외 케이스를 기록한다.
