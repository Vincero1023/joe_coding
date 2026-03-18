# Project Overview

## Purpose
- 벤치마크 기반 키워드 툴 동작을 모사해 수집, 확장, 분석, 선별까지 이어지는 수익형 키워드 파이프라인을 구축하는 것이 목적이다.
- 단순 트래픽 키워드가 아니라 광고 단가와 입찰 경쟁이 붙는 키워드를 우선 탐지해 실제 수익 가능성이 높은 주제를 찾도록 돕는다.

## Features
- 고정 카테고리 선택과 실시간 네이버 검색 수집을 수행하는 `collector`
- 자동완성, 연관 확장, 조합 확장을 다중 엔진 구조로 수행하는 `expander`
- CPC, bid, volume, competition 기반 수익성 점수 계산을 수행하는 `analyzer`
- 골든 키워드 기준으로 최종 수익형 키워드를 선별하는 `selector`
- 선별된 골든 키워드로 네이버 홈형, 블로그형 제목을 생성하는 `title_gen`
- 수집부터 제목 생성까지 한 번에 실행하는 `pipeline`

## Tech Stack
- Python, FastAPI, Pydantic Settings, SQLAlchemy, PostgreSQL, BeautifulSoup4, pytest, Docker, Docker Compose

## Development Plan
1. `collector`의 실시간 수집 품질과 카테고리 매핑을 다듬는다.
2. `title_gen`과 전체 파이프라인 API 계약을 고정하고 테스트를 보강한다.
3. 운영용 설정, 인증형 수집 소스, 배포 구성을 다듬어 실사용 가능한 구조로 마무리한다.

## Idea
광고 수익 가능성이 높은 키워드를 자동으로 발굴하고, 실제 콘텐츠 제작 전 단계까지 연결하는 모듈형 키워드 포지 시스템
