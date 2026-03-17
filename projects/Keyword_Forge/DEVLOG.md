# Devlog

## 짧게 쓰는 규칙 (3줄)
1. 한 항목당 3~5줄 안에서 핵심만 적는다.
2. 증상-원인-해결-검증 순서로만 기록한다.
3. 추측은 가정으로 표시하고, 확인 후 즉시 갱신한다.

## Date
- YYYY-MM-DD HH:mm (KST)

## What changed (변경점)
- [수정한 파일/기능]
- 예시: `update_3gyogu_hwpx.py`의 이미지 매핑 분기 로직 수정

## Why (원인/배경)
- [왜 바꿨는지]
- 예시: 특정 행에서 floating image id가 누락되어 사진이 교체되지 않음

## How verified (검증 방법/체크리스트)
- [ ] 로컬 재실행 완료
- [ ] 출력 파일 생성 확인
- [ ] 핵심 케이스 N건 수동 확인
- [ ] 회귀(기존 기능) 이상 없음

## Issues & Fix (문제-원인-해결)
- 문제: [...]
- 원인: [...]
- 해결: [...]

## Next (다음 작업)
- [다음 1~2개 작업]

---

## Date
- 2026-03-18 01:30 (KST)

## What changed (변경점)
- `collector`를 벤치마크 분석 JSON 기반 수집기로 정리하고 `category/seed` 모드를 추가했다.
- `expander`를 다중 엔진 구조로 재구성하고 자동완성, 연관 확장, 조합 확장, 다중 깊이 확장, 품질 필터를 구현했다.
- `analyzer`를 수익성 중심 점수 엔진으로 바꾸고 `selector` 모듈을 추가해 골든 키워드만 선별하도록 연결했다.

## Why (원인/배경)
- 초기 스켈레톤 구조만으로는 실제 키워드 툴처럼 수집-확장-평가-선별 흐름을 검증하기 어려웠다.
- 특히 `analyzer`는 단순 가중합이 아니라 수익성 중심 판단을 해야 했고, `selector`는 별도 최종 전략 모듈로 분리할 필요가 있었다.

## How verified (검증 방법/체크리스트)
- [x] `python app/collector/main.py` 실행 확인
- [x] `python app/expander/main.py` 실행 확인
- [x] `python app/analyzer/main.py` 실행 확인
- [x] `python app/selector/main.py` 실행 확인
- [x] 주요 파일 문법 검사 및 직접 입력 케이스 확인

## Issues & Fix (문제-원인-해결)
- 문제: `PROJECT.md` 한글이 깨져 문서 신뢰도가 떨어짐
- 원인: 이전 작성 과정에서 인코딩이 섞여 저장됨
- 해결: UTF-8 기준으로 문서를 다시 작성하고 현재 모듈 상태를 반영함

## Next (다음 작업)
- `title_gen` 구현 및 전체 파이프라인 연결
- 모듈별 테스트 보강과 API 계약 정리
