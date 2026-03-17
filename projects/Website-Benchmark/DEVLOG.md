# Devlog

## 기록 규칙
1. 항목은 3~5줄 안에서 핵심만 적는다.
2. 변경점, 원인, 해결, 검증 순서로 기록한다.
3. 추측은 추측으로 표시하고, 확인되면 즉시 갱신한다.

## Date
- YYYY-MM-DD HH:mm (KST)

## What changed
- [수정한 파일/기능]
- 예시: `update_3gyogu_hwpx.py`의 이미지 매핑 분기 로직 수정

## Why
- [문제 원인/배경]
- 예시: 특정 문단에서 floating image id가 누락되어 이미지 교체가 되지 않음

## How verified
- [ ] 로직 재검토 완료
- [ ] 출력 파일 생성 확인
- [ ] 주요 케이스 수동 확인
- [ ] 회귀 이상 없음

## Issues & Fix
- 문제: [...]
- 원인: [...]
- 해결: [...]

## Next
- [다음 1~2개 작업]

---

## Date
- 2026-03-17 16:50 (KST)

## What changed
- `main.py`, `cli.py`, `analyzer.py`, `report.py`에 URL/파일 입력, 구조 추출, Markdown 리포트 생성을 묶는 CLI 흐름을 추가했다.
- `sample_*.html`, `test_analysis.py`, `README.md`를 추가해 샘플 입력과 기본 검증 경로를 만들었다.

## Why
- 프로젝트 개요만 있고 입력부터 리포트 출력까지 이어지는 실행 가능한 최소 버전이 필요했다.

## How verified
- [x] 로직 재검토 완료
- [x] 출력 파일 생성 확인
- [x] 주요 케이스 3건 수동 확인
- [x] 회귀 이상 없음

## Issues & Fix
- 문제: 페이지 역할과 기능 분류가 네비게이션 링크 텍스트에 끌려 잘못 분류되었다.
- 원인: 제목과 헤딩보다 링크 텍스트 비중이 높아 `contact` 페이지가 `pricing`으로 인식되었다.
- 해결: 역할/기능 분류에서 제목, 헤딩, 섹션 신호를 우선하도록 규칙을 조정했다.

## Next
- URL 로딩 실패 케이스와 인코딩 예외 처리를 보강한다.
- 기능/컴포넌트 규칙을 세분화해 신호 품질을 높인다.

---

## Date
- 2026-03-17 18:33 (KST)

## What changed
- `analyzer.py`에 HTML 디코딩 후보 탐지, URL 로딩 이슈 수집, 파일/URL별 인코딩 추적을 추가했다.
- `cli.py`, `report.py`에서 로딩 실패를 사용자에게 보이도록 하고 `Load Notes`와 인코딩 정보를 리포트에 노출했다.
- `test_analysis.py`, `README.md`를 갱신해 CP949 입력과 URL 실패 케이스를 회귀 테스트 및 문서에 반영했다.

## Why
- UTF-8 고정 읽기와 무시되는 URL 실패 때문에 실제 사이트 분석 시 원인 파악이 어려웠다.

## How verified
- [x] 로직 재검토 완료
- [x] 출력 파일 생성 확인
- [x] 주요 케이스 4건 자동 확인
- [x] 회귀 이상 없음

## Issues & Fix
- 문제: 비 UTF-8 HTML은 `UnicodeDecodeError` 또는 깨진 텍스트로 이어질 수 있었고, URL fetch 실패는 조용히 누락되었다.
- 원인: 로컬 파일은 UTF-8로만 읽고, URL 크롤러는 예외를 삼킨 채 계속 진행했다.
- 해결: BOM, HTTP charset, meta charset, 주요 대체 인코딩을 순차 시도하고 실패 원인을 `Load Notes`에 축적하도록 변경했다.

## Next
- 기능/컴포넌트 분류 규칙의 오탐 케이스를 샘플 HTML로 더 늘린다.
- 빈 디렉터리, 비 HTML 응답, redirect 체인 같은 입력 경계를 더 테스트한다.
