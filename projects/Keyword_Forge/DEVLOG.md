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
- 2026-03-18 20:46 (KST)

## What changed (변경점)
- `expander`에 `POST /expand/stream` 실시간 스트림을 추가하고, 웹 UI에서 확장 중 새 키워드를 즉시 누적해서 보여주도록 연결했다.
- 확장 결과 카드는 기본 12건만 낮은 높이로 보여주고, 실시간 진행 배너와 전체 펼쳐보기로 밀도를 줄였다.
- 확장 상태 문구와 로그 문구를 스트림 기준으로 다시 정리하고 asset version을 올렸다.

## Why (원인/배경)
- 확장 단계는 실제로는 오래 걸리는데, 완료 전까지 화면이 비어 보여 사용자가 멈춘 것으로 오해할 가능성이 컸다.

## How verified (검증 방법/체크리스트)
- [ ] 로컬 재실행 완료
- [ ] 출력 파일 생성 확인
- [ ] 핵심 케이스 N건 수동 확인
- [x] 회귀(기존 기능) 이상 없음

## Issues & Fix (문제-원인-해결)
- 문제: 확장 도중 어떤 키워드가 수집되고 있는지 화면에서 바로 확인할 수 없었다.
- 원인: `/expand`가 완료 후 최종 결과만 반환하고 프런트도 한 번에 렌더링하는 구조였다.
- 해결: NDJSON 스트림으로 진행 이벤트와 중간 키워드를 보내고, 프런트에서 즉시 누적 렌더링하도록 바꿨다.

## Next (다음 작업)
- 확장 결과 행에서 원본 키워드별 접기/펼치기 추가
- 분석 단계도 부분 진행 상태 노출 검토

---

## Date
- 2026-03-18 19:27 (KST)

## What changed (변경점)
- `app/expander/sources/naver_related.py`가 정적 HTML 섹션 대신 네이버 QRA API(`s.search.naver.com/p/qra/1/search.naver`)를 우선 읽도록 바꿨다.
- 검색 페이지 요청 헤더를 브라우저 수준으로 맞춰 `버터떡` 같은 한글 쿼리도 `???`로 깨지지 않게 했다.
- `tests/test_expander_related.py`를 QRA URL/응답 파싱 기준으로 다시 고정했다.

## Why (원인/배경)
- 기존 방식은 `#nx_right_related_keywords`만 봐서 실제로는 연관어가 보여도 수집이 0건으로 떨어졌고, `seed`와 `expander` 모두 같은 한계를 공유했다.

## How verified (검증 방법/체크리스트)
- [ ] 로컬 재실행 완료
- [ ] 출력 파일 생성 확인
- [x] 핵심 케이스 3건 수동 확인
- [x] 회귀(기존 기능) 이상 없음

## Issues & Fix (문제-원인-해결)
- 문제: `버터떡`이 브라우저에서는 `버터떡 레시피`, `서울 버터떡` 등이 보이는데 collector/expander에서는 0건이었다.
- 원인: 연관어 데이터가 정적 HTML이 아니라 QRA API 응답으로 렌더되고 있었고, 단순 `urllib` 헤더로는 한글 쿼리도 `???`로 변형됐다.
- 해결: 검색 페이지에서 QRA API URL을 추출해 JSON `result.contents[].query`를 읽고, 요청 헤더를 실제 브라우저와 가깝게 보강했다.

## Next (다음 작업)
- 확장 결과 실시간 프리뷰 보강
- QRA 외 추가 연관 블록 후보 탐색

---

## Date
- 2026-03-18 19:13 (KST)

## What changed (변경점)
- `collector`의 `seed` 모드를 기사 제목 fallback이 아니라 `네이버 자동완성 + 실제 연관검색어` 1회 수집으로 다시 설계했다.
- `seed` 결과는 카테고리 태깅 없이 독립 키워드 소스로 저장하고, Query Log도 `Query / Area / Source`로 분리했다.
- 웹 입력은 `seed` 모드에서 카테고리를 비활성화하고, 캐시 갱신용 asset version을 올렸다.

## Why (원인/배경)
- `버터떡`처럼 시드 검색을 하면 `버터떡 추천/후기/가격` 접미어 쿼리와 뉴스 기사 제목이 수집돼, 사용자가 기대한 `버터떡 레시피`, `서울 버터떡` 같은 실제 연관검색 흐름과 달랐다.

## How verified (검증 방법/체크리스트)
- [ ] 로컬 재실행 완료
- [ ] 출력 파일 생성 확인
- [x] 핵심 케이스 2건 수동 확인
- [x] 회귀(기존 기능) 이상 없음

## Issues & Fix (문제-원인-해결)
- 문제: `seed` 수집이 네이버 연관검색어 대신 뉴스/블로그 검색 결과 제목을 키워드처럼 취급했다.
- 원인: `seed`도 category preset 수집과 같은 `_build_query_variants -> autocomplete 실패 시 검색 fallback` 경로를 탔다.
- 해결: `seed` 전용 수집 경로를 만들어 `자동완성 + 연관검색`만 1차 결과로 사용하고, 검색 fallback은 `seed`에서 제거했다.

## Next (다음 작업)
- seed/expand 실시간 수집 프리뷰 보강
- 연관검색어 메타 지표 노출 설계

---

## Date
- 2026-03-18 18:59 (KST)

## What changed (변경점)
- `app/expander/utils/throttle.py`를 추가해 네이버 자동완성/연관검색 요청을 공용 throttle로 묶고 기본 간격을 0.55초로 올렸다.
- `naver_autocomplete`, `naver_related`는 각자 따로 `sleep`하지 않고 같은 버킷을 공유하도록 바꿨다.
- `tests/test_expander_throttle.py`로 간격 예약과 환경변수 override 회귀 테스트를 추가했다.

## Why (원인/배경)
- depth 확장 시 자동완성과 연관검색이 번갈아 빠르게 붙으면 캐시 미스 구간에서 네이버 요청이 연속 발생해 차단·빈 응답 위험이 커질 수 있었다.

## How verified (검증 방법/체크리스트)
- [ ] 로컬 재실행 완료
- [ ] 출력 파일 생성 확인
- [x] 핵심 케이스 2건 수동 확인
- [x] 회귀(기존 기능) 이상 없음

## Issues & Fix (문제-원인-해결)
- 문제: 소스별 개별 `sleep`만 있어서 자동완성 다음 연관검색이 사실상 바로 붙는 구간이 있었다.
- 원인: `naver_autocomplete.py`, `naver_related.py`가 서로 다른 마지막 요청 시각만 관리했다.
- 해결: 공용 throttle가 요청 슬롯을 예약하도록 바꾸고, 필요하면 `KEYWORD_FORGE_NAVER_REQUEST_GAP_SECONDS`로 간격을 조절할 수 있게 했다.

## Next (다음 작업)
- 확장 결과 실시간 프리뷰 보강
- 연관검색어 메타 지표 노출 설계

---

## Date
- 2026-03-18 19:05 (KST)

## What changed (변경점)
- `expander`에 `app/expander/sources/naver_related.py`를 추가해 네이버 검색 결과의 `연관 검색어` 블록에서 실제 확장 키워드를 수집하도록 바꿨다.
- `related_engine`는 더 이상 `연관/추천/비교` 접미사를 붙이지 않고, `combinator`는 기본 흐름에서 빠지게 조정했다.
- 웹 결과 영역의 `확장 키워드` 카드는 압축 표 형태로 바꾸고 기본 12건만 보여준 뒤 전체 펼치기를 지원하도록 수정했다.

## Why (원인/배경)
- 기존 expander는 실연관어 수집이 아니라 접미 단어를 붙여 결과를 과도하게 부풀렸고, 카드형 UI도 한 행당 높이가 커서 많은 결과를 보기 어려웠다.

## How verified (검증 방법/체크리스트)
- [x] 로컬 재실행 완료
- [ ] 출력 파일 생성 확인
- [x] 핵심 케이스 3건 수동 확인
- [x] 회귀(기존 기능) 이상 없음

## Issues & Fix (문제-원인-해결)
- 문제: `강이슬, 대한민국 슈터 신기록 추천/확장/분석` 같은 조합식 키워드가 대량 생성돼 확장 품질이 떨어졌다.
- 원인: `related_engine`가 네이버 연관검색어를 가져오지 않고 하드코딩된 접미어를 이어 붙이는 구조였다.
- 해결: `#nx_right_related_keywords` 섹션 파서를 추가하고, 관련 엔진은 실제 네이버 연관검색 결과만 반환하게 바꿨다. UI는 표형 미리보기 + 전체 펼치기 구조로 재구성했다.

## Next (다음 작업)
- collector/expander 실시간 미리보기 보강
- 수집 노이즈 필터 추가 정교화

---

## Date
- 2026-03-18 18:36 (KST)

## What changed (변경점)
- `app/collector/naver_trend.py`에서 요청 날짜 트렌드가 비어 있으면 최근 3일 범위 안에서 가장 가까운 유효 날짜를 자동으로 다시 찾도록 했다.
- `app/collector/service.py`, `app/web_assets/app.js`에 실제 사용일/요청일을 같이 남기도록 보강했고, `tests/test_naver_trend.py`에 날짜 backoff 테스트를 추가했다.

## Why (원인/배경)
- `비즈니스·경제`처럼 특정 날짜에는 Creator Advisor가 빈 `queryList`를 반환하는 경우가 있어, 로그인은 정상인데도 사용자는 `트렌드 응답에 키워드가 없습니다`만 보게 됐다.

## How verified (검증 방법/체크리스트)
- [x] 로컬 재실행 완료
- [ ] 출력 파일 생성 확인
- [x] 핵심 케이스 3건 수동 확인
- [x] 회귀(기존 기능) 이상 없음

## Issues & Fix (문제-원인-해결)
- 문제: `비즈니스·경제 / 2026-03-18` 수집이 빈 결과로 끝났다.
- 원인: Creator Advisor 실데이터 기준으로 2026-03-18은 빈 응답이고, 2026-03-17부터 다시 키워드가 존재했다.
- 해결: 비어 있는 날짜면 최근 유효 날짜로 자동 backoff 하고, Query Log에 `기준일`과 `요청일`을 함께 표시하도록 했다.

## Next (다음 작업)
- 실시간 수집/확장 미리보기를 더 시각적으로 정리
- 수집 노이즈 관련도 필터 강화

---

## Date
- 2026-03-18 18:02 (KST)

## What changed (변경점)
- `app/collector/categories.py`를 Creator Advisor 현재 `naver_blog` 카테고리 트리에 맞춰 32개 카테고리와 그룹 구조로 다시 정리했다.
- `app/collector/naver_trend.py`에서 401/403 시 최신 로컬 세션 캐시로 한 번 더 재시도하고, Creator Advisor 요청 헤더도 실제 브라우저 요청에 가깝게 보강했다.
- `app/web.py`는 카테고리 `<select>`를 트렌드 그룹별 `<optgroup>`로 렌더링하도록 바꿨고, `tests/test_naver_trend.py`를 추가했다.

## Why (원인/배경)
- 현재 선택 카테고리 범위가 네이버 트렌드 실제 분류와 어긋나 있었고, 막 로그인한 뒤에도 UI에 남은 오래된 쿠키 때문에 `Forbidden`이 뜰 수 있었다.

## How verified (검증 방법/체크리스트)
- [x] 로컬 재실행 완료
- [ ] 출력 파일 생성 확인
- [x] 핵심 케이스 3건 수동 확인
- [x] 회귀(기존 기능) 이상 없음

## Issues & Fix (문제-원인-해결)
- 문제: `국내여행` 등 트렌드 카테고리 수집에서 `인증 쿠키 필요 / Forbidden` 경고가 남았다.
- 원인: 프런트 입력칸에는 이전 쿠키가 남아 있을 수 있었고, 서버는 그 쿠키만 그대로 사용했다. 또 카테고리 목록도 네이버 트렌드 현재 체계와 달랐다.
- 해결: 트렌드 요청이 401/403이면 `.local/naver_playwright/naver_creator_session.json`의 최신 세션으로 재시도하게 했고, 카테고리 목록은 Creator Advisor `categoryTree` 기준으로 재구성했다.

## Next (다음 작업)
- collector/expander 실시간 프리뷰를 샘플 사이트처럼 더 시각적으로 정리
- 수집 결과 관련도 필터를 강화해 `선풍기 -> 온수매트` 같은 노이즈를 줄이기

---

## Date
- 2026-03-18 17:31 (KST)

## What changed (변경점)
- `app/local/naver_login_browser.py`에 Playwright 직접 초기화 실패 시 `app/local/naver_login_worker.py` 보조 프로세스로 다시 시도하는 fallback을 추가했다.
- Windows 콘솔 인코딩 때문에 worker JSON이 깨지던 문제를 raw bytes decode(`utf-8 -> cp949`)로 보정했고, 관련 회귀 테스트 2건을 늘렸다.

## Why (원인/배경)
- 일부 로컬 환경에서 FastAPI 요청 안에서 바로 Playwright를 띄우면 시작 단계가 실패했지만, 같은 코드를 별도 Python 프로세스로는 실행할 가능성이 있었다.
- worker가 내보내는 JSON이 cp949로 섞여 들어와 fallback 실패 원인을 다시 가려버렸다.

## How verified (검증 방법/체크리스트)
- [ ] 로컬 재실행 완료
- [ ] 출력 파일 생성 확인
- [x] 핵심 케이스 3건 수동 확인
- [x] 회귀(기존 기능) 이상 없음

## Issues & Fix (문제-원인-해결)
- 문제: `전용 로그인 브라우저 초기화 실패` 뒤에도 실제 브라우저 대체 실행 경로가 없어서 버튼이 바로 막혔다.
- 원인: 요청 프로세스와 별도 Python 프로세스의 Playwright 실행 안정성이 달랐고, worker 출력은 Windows 인코딩 때문에 바로 파싱되지 않았다.
- 해결: direct 실패 시 subprocess worker로 재시도하고, worker JSON은 raw bytes 기준으로 decode해 timeout/성공 상태를 그대로 UI에 전달하게 했다.

## Next (다음 작업)
- 실제 브라우저 로그인 후 세션 저장까지 end-to-end 수동 확인
- collector 실시간 프리뷰와 관련도 필터 보강 이어서 정리

---

## Date
- 2026-03-18 17:06 (KST)

## What changed (변경점)
- `app/local/naver_login_browser.py`에서 Playwright 초기화 단계 예외를 별도로 감싸 `HTTP 500` 대신 구조화된 `HTTP 400`으로 내려가게 수정했다.
- `tests/test_local_naver.py`에 `sync_playwright()`가 즉시 `NotImplementedError`를 던지는 회귀 테스트를 추가했다.

## Why (원인/배경)
- 전용 로그인 브라우저 버튼 클릭 시 일부 로컬 환경에서 Playwright가 시작 단계에서 바로 실패했고, 이 예외가 라우트에서 처리되지 않아 `Unhandled server error`만 보였다.

## How verified (검증 방법/체크리스트)
- [ ] 로컬 재실행 완료
- [ ] 출력 파일 생성 확인
- [x] 핵심 케이스 2건 수동 확인
- [x] 회귀(기존 기능) 이상 없음

## Issues & Fix (문제-원인-해결)
- 문제: `/local/naver-login-browser`가 즉시 실패할 때 `Unhandled server error`만 보여 실제 원인을 알 수 없었다.
- 원인: `sync_playwright()` 초기화 구간 예외가 `LocalLoginBrowserError`로 변환되지 않고 그대로 500으로 전파됐다.
- 해결: 초기화 구간을 별도 `try/except`로 감싸고 `playwright` 시도 기록과 힌트를 포함한 400 응답으로 통일했다.

## Next (다음 작업)
- 실제 로컬 브라우저 창에서 로그인 후 세션 확보가 끝까지 정상 완료되는지 수동 확인
- category 트렌드 수집과 전용 로그인 브라우저 흐름을 한 번에 재검증

---

## Date
- 2026-03-18 16:41 (KST)

## What changed (변경점)
- `app/local/naver_login_browser.py`, `POST /local/naver-login-browser`를 추가해 기존 Edge/Chrome 쿠키 DB를 읽지 않고 앱 전용 브라우저에서 직접 로그인 세션을 확보하도록 했다.
- `app/web.py`, `app/web_assets/app.js`에 `전용 로그인 브라우저 열기` 버튼을 추가하고, 성공 시 쿠키를 자동 주입하도록 연결했다.
- `requirements.txt`, `README.md`, `tests/test_local_naver.py`를 업데이트해 playwright 기반 로컬 로그인 흐름과 회귀 테스트를 반영했다.

## Why (원인/배경)
- 실제 재현 결과 기존 브라우저 쿠키 import는 Edge/Chrome 쿠키 DB 잠금 때문에 `RequiresAdminError`가 발생해, 로그인돼 있어도 세션을 읽지 못했다.
- 로컬 전용 도구라면 기존 브라우저 DB를 읽는 것보다 앱 전용 브라우저 프로필을 직접 관리하는 편이 더 안정적이다.

## How verified (검증 방법/체크리스트)
- [x] `python -m pytest` 전체 실행
- [x] `python -m py_compile` 변경 Python 파일 문법 검사
- [x] `node --check app/web_assets/app.js` 문법 검사
- [ ] 실제 playwright 전용 브라우저를 열어 로그인 후 세션 확보 수동 확인

## Issues & Fix (문제-원인-해결)
- 문제: 기존 브라우저에서 로그인돼 있어도 쿠키 DB 접근이 관리자 권한을 요구해 자동 세션 로드가 실패했다.
- 원인: `browser-cookie3`가 Windows에서 잠긴 Chromium 쿠키 DB를 읽는 과정에서 `shadowcopy` 경로로 넘어가며 권한 제약에 걸렸다.
- 해결: 기존 브라우저 쿠키 import는 보조 경로로 남기고, 기본 권장 흐름은 앱 전용 Edge/Chrome 브라우저를 띄워 로그인 후 세션 쿠키를 직접 저장하는 방식으로 바꿨다.

## Next (다음 작업)
- playwright 전용 브라우저 수동 검증 후 UI 문구와 예외 처리를 더 다듬기
- 저장된 로컬 세션 재사용/만료 감지 흐름 정리

---

## Date
- 2026-03-18 16:34 (KST)

## What changed (변경점)
- `app/local/naver_session.py`, `app/api/routes/local_naver.py`에서 로컬 브라우저 쿠키 읽기 실패 사유와 브라우저별 시도 내역을 구조화해 반환하도록 바꿨다.
- `app/web_assets/app.js`에 로컬 쿠키 불러오기 실패 시 상태 영역에 원인/힌트를 바로 보여주도록 보강했다.
- `tests/test_local_naver.py`에 로컬 세션 실패 응답 테스트를 추가했다.

## Why (원인/배경)
- 같은 브라우저에서 네이버 로그인과 Creator Advisor 접속이 되어 있어도, Edge/Chrome 쿠키 DB가 잠겨 있으면 현재 방식은 단순히 `세션 없음`처럼 보여 원인을 오해하기 쉬웠다.
- 실제 재현 결과 이 환경에서는 `RequiresAdminError`, `Permission denied`가 발생하고 있었다.

## How verified (검증 방법/체크리스트)
- [x] `python -m pytest` 전체 실행
- [x] `python -m py_compile` 변경 Python 파일 문법 검사
- [x] `node --check app/web_assets/app.js` 문법 검사
- [x] 로컬 재현으로 Edge/Chrome `RequiresAdminError` 확인

## Issues & Fix (문제-원인-해결)
- 문제: 브라우저에서 로그인돼 있어도 `브라우저에서 쿠키 불러오기`가 실패하고 원인이 화면에 드러나지 않았다.
- 원인: 브라우저 쿠키 DB가 잠겨 있거나 권한이 부족해 읽기 실패했는데, UI는 실패 사유를 일반 문구로만 표시했다.
- 해결: 브라우저별 시도 내역과 힌트를 API에서 구조화해 내려주고, 프런트 상태 영역에 첫 실패 사유와 `브라우저 완전 종료 후 재시도` 힌트를 바로 보여주도록 바꿨다.

## Next (다음 작업)
- Edge/Chrome 실행 중에도 읽을 수 있는 로컬 우회 방식 검토
- Creator Advisor 로그인/세션 확보를 더 자동화할 로컬 전용 흐름 설계

---

## Date
- 2026-03-18 16:25 (KST)

## What changed (변경점)
- `app/local/naver_session.py`, `POST /local/naver-session`를 추가해 로컬 Edge/Chrome/Firefox에서 네이버 로그인 쿠키를 직접 읽어오도록 했다.
- `app/web.py`, `app/web_assets/app.js`, `app/web_assets/app.css`에 `브라우저에서 쿠키 불러오기` 버튼과 브라우저 선택 UI를 넣고, 트렌드 수집 기본값을 `naver_blog + fallback off`로 바꿨다.
- `README.md`, `tests/test_local_naver.py`를 추가/갱신해 로컬 전용 흐름과 회귀 검증을 정리했다.

## Why (원인/배경)
- Creator Advisor 인증이 필요한 구조에서는 서버형 웹서비스보다 개인 로컬 도구가 더 자연스럽고, 수동 쿠키 붙여넣기 UX는 사용성이 낮았다.
- 특히 이전 저장값 때문에 `influencer`나 fallback 상태가 남으면 사용자가 공개 검색 결과를 실제 트렌드로 오해하기 쉬웠다.

## How verified (검증 방법/체크리스트)
- [x] `python -m pytest` 전체 실행
- [x] `python -m py_compile` 변경 Python 파일 문법 검사
- [x] `node --check app/web_assets/app.js` 문법 검사
- [ ] 실제 Edge/Chrome/Firefox 로그인 상태에서 로컬 쿠키 자동 로드 수동 확인

## Issues & Fix (문제-원인-해결)
- 문제: Creator Advisor를 쓰려면 사용자가 쿠키를 직접 복사해야 했고, fallback이 기본으로 켜져 있어 실제 트렌드 여부를 혼동했다.
- 원인: 로컬 브라우저 세션을 활용하는 도우미가 없었고, 트렌드 설정 저장값도 로컬 우선 흐름에 맞게 정리되지 않았다.
- 해결: 로컬 브라우저 쿠키 로더를 추가하고, UI에서 버튼 한 번으로 세션을 채우며 기본 동작은 실제 트렌드 우선, fallback은 명시적으로만 켜도록 바꿨다.

## Next (다음 작업)
- 로컬 브라우저 로그인 창 열기/세션 테스트까지 한 번에 되는 흐름 추가 검토
- Creator Advisor live 응답을 이용한 단계별 실시간 수집 프리뷰 고도화

---

## Date
- 2026-03-18 15:58 (KST)

## What changed (변경점)
- `collector` category 모드에 `naver_trend` 소스를 추가하고 Creator Advisor 주제 id 조회 후 실제 인기 유입 검색어를 가져오도록 연결했다.
- `app/web.py`, `app/web_assets/app.js`, `app/web_assets/app.css`에 카테고리 수집 소스, 트렌드 서비스/날짜/쿠키 입력 UI와 `localStorage` 저장을 추가했다.
- 트렌드 설정 기본값을 `naver_blog + fallback off`로 바꾸고, 쿠키 없이 실행하면 프런트에서 바로 멈추도록 가드했다.
- `tests/test_health.py`, `tests/test_debug_api.py`에 trend 성공/fallback 테스트를 보강했다.

## Why (원인/배경)
- 기존 category 수집은 내부 preset 쿼리를 다시 검색하는 구조라 `국내여행` 같은 카테고리에서 네이버가 실제로 보여주는 이슈 키워드를 얻지 못했다.
- Creator Advisor 트렌드 API는 인증 쿠키가 필요하므로, 실사용 경로와 fallback 경로를 함께 분리해 두지 않으면 사용자 경험이 불안정했다.
- 특히 쿠키가 없는데 fallback이 기본으로 켜져 있으면 사용자는 실제 트렌드가 아니라 공개 검색 결과를 트렌드로 오해하기 쉬웠다.

## How verified (검증 방법/체크리스트)
- [x] `python -m pytest` 전체 실행
- [x] `python -m py_compile` 변경 Python 파일 문법 검사
- [x] `node --check app/web_assets/app.js` 문법 검사
- [ ] 브라우저에서 실제 쿠키 입력 후 live 트렌드 수집 확인

## Issues & Fix (문제-원인-해결)
- 문제: category 모드가 실제 네이버 트렌드가 아니라 preset 검색 결과만 돌려줬다.
- 원인: collector가 Creator Advisor `preferred-category`/`trend/category` 흐름을 쓰지 않고 고정 query 확장만 사용했다.
- 해결: 카테고리별 Creator Advisor 주제명을 매핑하고, 인증 쿠키가 있으면 트렌드 검색어를 우선 수집하며 기본값은 `naver_blog + fallback off`로 바꿔 실제 트렌드 경로와 fallback 경로를 명확히 분리했다.

## Next (다음 작업)
- 수집 결과/확장 결과를 더 표형으로 바꿔 실시간 지표를 보기 쉽게 정리
- seed/search fallback 노이즈 필터를 `선풍기`, `DDR5` 같은 케이스로 추가 보정

---

## Date
- 2026-03-18 15:23 (KST)

## What changed (변경점)
- `run_local.bat`의 FastAPI 실행 경로에서 서버 시작 후 브라우저를 자동으로 열도록 수정했다.
- `README.md` 실행 메모에 `run_local.bat api`와 메뉴 `7`의 자동 브라우저 오픈 동작을 추가했다.

## Why (원인/배경)
- 로컬에서 FastAPI 테스트를 시작할 때 서버만 켜지고 브라우저를 따로 열어야 해서 확인 흐름이 끊겼다.
- 특히 메뉴형 배치 실행에서는 사용자가 "서버 실행" 이후 다음 행동을 다시 해야 했다.

## How verified (검증 방법/체크리스트)
- [ ] 로컬 재실행 완료
- [ ] 출력 파일 생성 확인
- [ ] 핵심 케이스 N건 수동 확인
- [x] 배치 파일 파싱 확인 (`cmd /c "call run_local.bat bogus"`)

## Issues & Fix (문제-원인-해결)
- 문제: FastAPI 테스트 시작 후 브라우저를 수동으로 열어야 했다.
- 원인: `run_local.bat`의 `:run_api` 경로가 `uvicorn` 실행만 하고 브라우저 호출은 하지 않았다.
- 해결: `APP_URL` 변수를 추가하고, `uvicorn` 실행 직전에 숨김 PowerShell로 2초 후 기본 브라우저를 열도록 바꿨다.

## Next (다음 작업)
- collector/expander 실시간 프리뷰와 관련도 필터링 정교화
- run_local 메뉴에서 docs 홈(`/api-docs`)과 메인 UI(`/`) 중 열 주소를 선택할지 검토

---

## Date
- 2026-03-18 13:34 (KST)

## What changed (변경점)
- `app/web_assets/app.js`, `app/web_assets/app.css`에서 collector 결과를 쿼리 묶음 보드 형태로 다시 렌더링하고, 묶음/전체 선택 버튼을 추가했다.
- collector 디버그 패널을 요청 요약, 수집 요약, query log 표, warning 카드로 재구성해 코드 블록 없이도 읽히게 바꿨다.
- `app/web.py`의 asset version을 갱신해 브라우저 캐시로 이전 UI가 남지 않게 했다.

## Why (원인/배경)
- 기존 collector 화면은 카드 안에 키워드 몇 개만 단순 나열하거나 debug JSON을 그대로 보여줘서, 실제 사용자가 결과를 선별하기에 구조가 약했다.
- 특히 screenshot처럼 요청/응답이 코드 블록으로 보이는 방식은 expander sample UI와 비교해 도구 화면의 가독성이 떨어졌다.

## How verified (검증 방법/체크리스트)
- [ ] 로컬 브라우저 수동 확인
- [x] `node --check app/web_assets/app.js` 문법 검사
- [x] `python -m py_compile app/web.py` 문법 검사
- [x] 회귀(기존 기능) 이상 없음

## Issues & Fix (문제-원인-해결)
- 문제: 수집 결과가 원본 쿼리별로 정리되지 않아 보기 어렵고, collector 진단도 코드처럼 출력됐다.
- 원인: 결과 렌더러가 단순 리스트/`<pre>` 중심이었고, 선택 워크플로를 고려한 그룹/표 UI가 없었다.
- 해결: 결과를 `raw` 쿼리 기준 그룹 카드로 묶고, collector debug는 카드/표/경고 목록으로 재구성했다.

## Next (다음 작업)
- analyze 결과도 선택 후 다음 단계로 넘기는 인터랙션 추가
- collector 결과 정렬 기준을 사용자 옵션으로 바꿀지 검토

---

## Date
- 2026-03-18 13:17 (KST)

## What changed (변경점)
- `app/title/ai_client.py`, `app/title/title_generator.py`, `app/title/main.py`에 template/AI 이중 모드와 OpenAI, Gemini, Anthropic 연동 경로를 추가했다.
- `app/web.py`, `app/web_assets/app.js`, `app/web_assets/app.css`에 제목 생성 AI 설정 UI와 `localStorage` 기반 API 키 저장을 추가했다.
- `tests/test_title.py`, `tests/test_pipeline.py`에 AI 성공, 키 누락 fallback, pipeline 전달 테스트를 추가했다.

## Why (원인/배경)
- 기존 제목 생성은 템플릿 기반만 가능해서 AI 품질이 필요한 사용 시나리오를 지원하지 못했다.
- 사용자가 사이트에서 API 키를 입력하고 유지하길 원했지만, 서버 저장 없이 브라우저 단에서 기억하는 경로가 없었다.

## How verified (검증 방법/체크리스트)
- [x] `python -m pytest` 전체 실행
- [x] `python -m py_compile` 변경 Python 파일 문법 검사
- [x] `node --check app/web_assets/app.js` 문법 검사
- [x] 회귀(기존 기능) 이상 없음

## Issues & Fix (문제-원인-해결)
- 문제: 제목 생성이 규칙 기반만 지원돼 AI 모델로 자연스럽게 확장할 수 없었다.
- 원인: `title_gen` 서비스 계약에 provider/model/api key 개념이 없었고, 프런트엔드도 제목 생성 모드를 따로 설정할 수 없었다.
- 해결: provider 공통 HTTP 클라이언트를 추가하고, UI에서 API 키를 브라우저에만 저장한 뒤 요청 시점에만 전달하도록 바꿨다.

## Next (다음 작업)
- AI 응답 품질 비교용 prompt/template 튜닝
- provider별 rate limit/timeout/비용 경고 UI 정리

---

## Date
- 2026-03-18 12:28 (KST)

## What changed (변경점)
- `app/core/keyword_inputs.py`를 추가하고 `expander`/`analyzer`가 줄바꿈·콤마 기반 직접 입력으로도 시작되도록 입력 계약을 분리했다.
- 웹 UI에 `expand`/`analyze` 시작점 선택 카드와 수집 키워드 체크박스를 추가해 단계별 독립 실행 흐름을 만들었다.
- `tests/test_stage_entrypoints.py`로 collect 없이 expand, expand 없이 analyze 되는 경로를 테스트로 고정했다.

## Why (원인/배경)
- 기존 화면은 사실상 collect부터 순차 실행하는 흐름에 고정돼 있어서, 실제 사용자가 중간 단계부터 작업을 시작하기 어려웠다.
- 특히 수집 결과 일부만 골라 expand 하거나 외부에서 가져온 키워드를 바로 expand/analyze 하는 구조가 UI와 서비스 계약 모두에서 약했다.

## How verified (검증 방법/체크리스트)
- [x] `python -m pytest` 전체 실행
- [x] `python -m py_compile` 변경 Python 파일 문법 검사
- [x] `node --check app/web_assets/app.js` 문법 검사
- [x] 회귀(기존 기능) 이상 없음

## Issues & Fix (문제-원인-해결)
- 문제: 각 기능이 독립 모듈처럼 보였지만 실제 입력 경로는 이전 단계 결과에 과하게 묶여 있었다.
- 원인: `expand`와 `analyze`가 사실상 구조화된 이전 단계 payload만 받도록 짜여 있었고, UI도 그 전제를 그대로 따르고 있었다.
- 해결: 공통 키워드 파서를 추가해 텍스트/리스트 입력을 서비스 레벨에서 직접 받게 하고, 프런트엔드도 단계별 입력 소스를 명시적으로 고르게 바꿨다.

## Next (다음 작업)
- expand/analyze 결과에서도 선택 후 다음 단계로 넘기는 세부 워크플로 정리
- 단계별 입력 계약을 README/API 문서에 명확히 반영

---

## Date
- 2026-03-18 12:04 (KST)

## What changed (변경점)
- `app/web.py`, `app/web_assets/app.js`, `app/web_assets/app.css`에 단계별 실시간 상태, 진행률, 오류/디버그 패널을 추가했다.
- `app/api/errors.py`, `app/main.py`에 `request_id` 포함 구조화 오류 응답과 공통 예외 핸들러를 추가했다.
- `app/collector/service.py`, `app/pipeline/service.py`, `tests/test_debug_api.py`에 collector 진단 로그와 debug 검증 테스트를 보강했다.

## Why (원인/배경)
- 오류가 나도 UI에는 짧은 실패 문구만 보여서 어느 단계에서 어떤 요청이 깨졌는지 확인하기 어려웠다.
- collector 내부에서 예외를 삼켜 빈 결과로 끝나는 경로가 있어 실제 실패 원인이 로그 없이 사라지고 있었다.

## How verified (검증 방법/체크리스트)
- [x] `python -m pytest` 전체 실행
- [x] `python -m py_compile` 변경 Python 파일 문법 검사
- [x] `node --check app/web_assets/app.js` 문법 검사
- [x] 회귀(기존 기능) 이상 없음

## Issues & Fix (문제-원인-해결)
- 문제: 키워드 수집/확장 중 실패 시 단계, request id, 상세 응답이 화면에 남지 않았다.
- 원인: 프런트엔드가 `error.message`만 출력했고 백엔드는 구조화된 오류 페이로드와 추적 id를 내려주지 않았다.
- 해결: 단계 상태 머신, 오류 콘솔, collector debug 로그를 UI에 추가하고 백엔드 공통 예외 핸들러로 `request_id`, `code`, `detail`을 표준화했다.

## Next (다음 작업)
- collector query 로그를 스트리밍으로 밀어주는 SSE/WebSocket 방식 검토
- 운영 환경에서 traceback 노출 범위와 로그 적재 방식 정리

---

## Date
- 2026-03-18 11:20 (KST)

## What changed (변경점)
- `collector`를 고정 카테고리 preset 기반 라이브 수집기로 바꾸고 네이버 검색 결과 폴백을 추가했다.
- 웹 UI의 카테고리 입력을 자유 텍스트에서 선택형 `<select>`로 바꿨다.
- collector/pipeline 테스트를 네트워크 mock 기반으로 다시 고정했다.

## Why (원인/배경)
- 카테고리를 매번 수기로 넣는 방식은 오입력이 잦고, 샘플 HTML 기반 수집은 실제 데이터 흐름 검증에 한계가 있었다.
- Creator Advisor 공식 API는 인증이 필요해 공개 환경에서 바로 쓰기 어려워서, 우선 공개 검색 결과 기반 라이브 수집 폴백이 필요했다.

## How verified (검증 방법/체크리스트)
- [ ] `python -m pytest` 전체 실행
- [x] `python -m py_compile` 변경 Python 파일 문법 검사
- [x] 테스트 함수 16건 직접 호출
- [x] 실시간 `collector` 호출로 `비즈니스경제` 키워드 수집 확인

## Issues & Fix (문제-원인-해결)
- 문제: 공개 자동완성 응답이 비어 실제 수집 결과가 0건으로 떨어졌다.
- 원인: 네이버 자동완성 공개 응답이 현재 환경에서 빈 `items`를 반환했다.
- 해결: 자동완성 우선 수집 뒤 결과가 비면 네이버 검색 결과 페이지에서 공개 링크 텍스트를 추출하도록 폴백을 추가했다.

## Next (다음 작업)
- Creator Advisor 인증 쿠키 기반 진짜 카테고리 수집 소스 연결 검토
- 검색 결과 기반 collector 노이즈 필터 추가 정교화

---

## Date
- 2026-03-18 10:49 (KST)

## What changed (변경점)
- `pipeline` 모듈과 `POST /pipeline` 엔드포인트를 추가해 수집-확장-분석-선별-제목 생성을 한 번에 실행하도록 연결했다.
- `title_gen` API 계약을 테스트로 고정하고 `MODULE_REGISTRY`에 `select`, `pipeline` 항목을 보강했다.
- README/PROJECT를 현재 구현 상태에 맞게 갱신했다.

## Why (원인/배경)
- 단계별 엔드포인트만으로는 전체 흐름 검증이 분산되어 실제 운영 시나리오를 한 번에 확인하기 어려웠다.
- 문서상 `title_gen` 미구현 상태와 실제 코드 상태가 어긋나 있어 다음 작업 우선순위가 혼선될 수 있었다.

## How verified (검증 방법/체크리스트)
- [ ] `python -m pytest` 전체 실행
- [ ] `python -m py_compile` 변경 파일 문법 검사
- [ ] `TestClient` 기반 `/pipeline`, `/generate-title` 응답 확인
- [ ] 핵심 샘플 경로로 전체 파이프라인 수동 실행

## Issues & Fix (문제-원인-해결)
- 문제: 전체 파이프라인을 서버 측에서 한 번에 실행하는 진입점이 없었다.
- 원인: 프런트엔드가 개별 모듈 호출을 순차 실행하는 구조에만 맞춰져 있었다.
- 해결: `PipelineService`를 추가하고 각 모듈 출력을 다음 단계 입력으로 연결했다.

## Next (다음 작업)
- 파이프라인 입력 스키마를 더 명확히 분리하고 옵션별 테스트를 보강
- 운영 설정과 배포 흐름 정리

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
