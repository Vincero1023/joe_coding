# Project Overview

## Purpose
- 웹사이트를 분석해 핵심 기능과 화면 구조를 빠르게 파악한다.
- 벤치마킹과 재구현에 필요한 정보를 문서 형태로 정리한다.

## Features
- 주요 페이지와 섹션 구조 분석
- 핵심 기능 및 UI 패턴 추출
- 공통 컴포넌트와 사용자 흐름 정리
- 분석 결과를 Markdown 문서로 기록

## Tech Stack
- Python 3
- 표준 라이브러리 기반 CLI (`argparse`)
- HTML 파싱 (`html.parser`)
- URL 로드/크롤링 (`urllib.request`, `urllib.parse`)
- Markdown 리포트 출력

## Development Plan
1. 입력 방식(URL/정적 파일) 정의
2. 페이지 구조 추출 로직 구현
3. 기능/컴포넌트 분류 규칙 정리
4. Markdown 리포트 출력 흐름 구성

## Idea
웹사이트를 분석하여 핵심 기능 및 구조를 추출하는 프로그램

## Current Scope
- URL, 단일 HTML 파일, HTML 디렉터리 입력 지원
- 규칙 기반으로 페이지 역할/섹션/기능/컴포넌트/사용자 흐름 추출
- Markdown 리포트 자동 생성
