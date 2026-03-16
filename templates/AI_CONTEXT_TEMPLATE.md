# AI Context

## Project Name
- [프로젝트 이름]
- 예시: 주일예배 출석 파일 자동 정리기

## Project Type (windows / web-docker / chrome-extension / desktop-gui / scripts / experiments)
- [하나 선택]
- 예시: windows

## One-line Goal
- [한 줄 목표]
- 예시: 엑셀 원본을 읽어 교회요람 HWPX를 한 번에 최신 데이터로 갱신한다.

## Users & Scenario (누가/언제/어떻게)
- [사용자와 사용 시점/방식]
- 예시: 사무간사가 매주 월요일 네트워크 드라이브의 원본 파일을 더블클릭 실행으로 업데이트한다.

## Inputs (파일/데이터/환경)
- [입력 목록]
- 예시: `input/member.xlsx`, `template/book.hwpx`, Windows 11, Python 3.11

## Outputs (결과물 형태, 파일명 규칙)
- [출력 규칙]
- 예시: `output/요람_YYYYMMDD_v01.hwpx`, 로그 `output/run_YYYYMMDD.log`

## Constraints (제약)
- [제약사항]
- 예시: 기존 원본 파일 덮어쓰기 금지, 네트워크 드라이브 잠금 파일 주의, 관리자 권한 없이 실행 가능해야 함.

## Tech Stack (언어/라이브러리/런타임)
- [기술 스택]
- 예시: Python 3.11, pandas, openpyxl, lxml, PowerShell 래퍼

## Run Methods (CLI/GUI/DOCKER/EXTENSION)
- [실행 방식]
- 예시: CLI `python main.py --input ...`, GUI는 `run.bat` 더블클릭

## Done Definition (완료 기준)
- [완료 조건]
- 예시: 샘플 3건에서 오류 없이 출력 생성 + 파일명 규칙 준수 + DEVLOG에 검증 기록 완료.