# Website Benchmark

웹사이트 또는 정적 HTML 입력을 분석해 핵심 기능, 화면 구조, 공통 컴포넌트, 사용자 흐름을 Markdown 보고서로 정리하는 CLI 도구입니다.

## Quick Start

```bash
python main.py sample_home.html -o report.md
python main.py . -o site-report.md --max-pages 10
python main.py https://example.com -o site-report.md --crawl-depth 1 --timeout 10
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
- 로딩 실패 및 디코딩 관련 메모

## CLI Options

```bash
python main.py SOURCE [-o report.md] [--max-pages 5] [--crawl-depth 1] [--timeout 10]
```

## Notes

- 현재 버전은 HTML 구조와 텍스트 신호를 기반으로 규칙 기반 분석을 수행합니다.
- URL 분석은 같은 도메인의 내부 링크만 제한적으로 크롤링합니다.
- 로컬 파일과 원격 HTML은 선언된 charset, BOM, meta charset을 우선 사용하고 주요 대체 인코딩으로 보정합니다.
- URL 로딩 실패나 디코딩 품질 저하는 보고서의 `Load Notes` 섹션에 기록됩니다.
