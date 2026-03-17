# Website Benchmark

URL 또는 정적 HTML 파일을 분석해 핵심 기능, 페이지 구조, 공통 컴포넌트, 사용자 흐름을 Markdown 문서로 정리하는 CLI 도구다.

## Quick Start

```bash
python main.py sample_home.html -o report.md
python main.py . -o site-report.md --max-pages 10
```

## Input

- 단일 HTML 파일
- HTML 파일이 들어 있는 디렉터리
- URL (`http://` 또는 `https://`)

## Output

- 페이지별 역할과 요약
- 주요 섹션 구조
- 핵심 기능 신호
- 공통 컴포넌트
- 추정 사용자 흐름

## CLI Options

```bash
python main.py SOURCE [-o report.md] [--max-pages 5] [--crawl-depth 1] [--timeout 10]
```

## Notes

- 현재 버전은 HTML 구조와 텍스트 신호를 기반으로 규칙 기반 분석을 수행한다.
- URL 분석 시 같은 도메인 링크만 제한적으로 크롤링한다.
- 로컬 파일은 UTF-8 기준으로 읽는다.
