# Devlog

## 짧게 쓰는 규칙 (3줄)
1. 한 항목당 3~5줄 안에서 핵심만 적는다.
2. 증상-원인-해결-검증 순서로만 기록한다.
3. 추측은 가정으로 표시하고, 확인 후 즉시 갱신한다.

## Date
- 2026-03-25 21:15 (KST)

## What changed (변경점)
- 최신 실행 결과 [Status/수익형 키워드 발굴&제목 생성기-2026-03-25T12-08-09.html](D:/joe_coding/projects/keyword_forge/Status/수익형%20키워드%20발굴&제목%20생성기-2026-03-25T12-08-09.html)을 점검해 제목 생성 스트림, 품질 분포, 선별 TXT export 반영 여부를 확인했다.

## Why (원인/배경)
- 다른 환경에서 이어서 작업할 예정이라, 마지막 실전 run 결과와 아직 남은 확인 포인트를 문서에 남겨둘 필요가 있었다.

## How verified (검증 방법/체크리스트)
- [x] 최신 status html 요약 수치 확인
- [x] 최신 CSV 산출물 확인
- [x] `output/txt/selected/live` 경로 생성 여부 확인

## Issues & Fix (문제-원인-해결)
- 문제: 최신 run은 정상 완료됐지만 `selection_export` 로그와 `output/txt/selected/live` 파일이 이번 status에는 보이지 않았다.
- 원인: 제목 스트림 패치는 반영된 상태였지만, 선별 TXT export 패치가 반영되기 전 서버/asset 상태로 실행됐을 가능성이 높다.
- 해결: 다음 run 전 서버 재시작 후 다시 실행해서 선별 TXT 생성 여부를 바로 재확인하기로 했다.

## Next (다음 작업)
- 서버 재시작 후 같은 카테고리로 재실행
- 선별 TXT export 실제 생성 확인
- 제목 반복 프레임(`왜 국내 시세와 다를까`, `무엇을 먼저 봐야 할까`) 분산 패치

## Date
- 2026-03-25 19:45 (KST)

## What changed (변경점)
- [app/selector/exporter.py](D:/joe_coding/projects/keyword_forge/app/selector/exporter.py)를 추가해 선별된 키워드를 항상 줄바꿈 TXT로 `output/txt/selected/live`, `output/txt/selected/archive`에 저장하도록 했다.
- [app/selector/service.py](D:/joe_coding/projects/keyword_forge/app/selector/service.py), [app/api/routes/selector.py](D:/joe_coding/projects/keyword_forge/app/api/routes/selector.py), [app/pipeline/service.py](D:/joe_coding/projects/keyword_forge/app/pipeline/service.py)에서 selector 실행 시 기본 export가 켜지도록 연결하고, 결과 payload에 `selection_export` 메타를 넣었다.
- [app/web_assets/app.js](D:/joe_coding/projects/keyword_forge/app/web_assets/app.js), [app/web_assets/app_overrides.js](D:/joe_coding/projects/keyword_forge/app/web_assets/app_overrides.js), [app/web.py](D:/joe_coding/projects/keyword_forge/app/web.py)에서 selector 호출에 `mode/category/seed_input`를 같이 보내고, 저장된 TXT 파일명을 activity log에 남기도록 보강했다.

## Why (원인/배경)
- 제목 품질이 아쉬운 경우 선별 키워드만 먼저 뽑아 사람이 직접 제목을 잡고 싶다는 운영 요구가 생겼다.
- 기존엔 선별 결과가 status/UI 안에만 남고 별도 TXT 큐처럼 바로 꺼내 쓰는 파일이 없었다.

## How verified (검증 방법/체크리스트)
- [x] `python -m py_compile app/selector/exporter.py app/selector/service.py app/api/routes/selector.py app/pipeline/service.py app/web.py`
- [x] `node --check app/web_assets/app.js`
- [x] `node --check app/web_assets/app_overrides.js`
- [x] `pytest -q tests/test_selector.py -k "export_selected_keywords_txt or scales_default_selection_for_large_measured_pool"`
- [x] `pytest -q tests/test_pipeline.py -k "pipeline_run_returns_all_stage_outputs"`
- [x] `pytest -q`

## Issues & Fix (문제-원인-해결)
- 문제: 선별 키워드를 사람이 직접 제목화하려고 해도 UI나 status에서 복사해야 했고, 실행 단위 TXT 파일이 없었다.
- 원인: export 기능이 제목 단계에만 집중돼 있었고 selector 단계는 파일 산출물을 만들지 않았다.
- 해결: selector 단계에 live/archive TXT export를 추가하고, category면 `날짜__카테고리.txt`, seed면 `날짜__시드키워드.txt` 규칙으로 항상 저장되게 했다.

## Next (다음 작업)
- 실제 selector run 후 생성되는 `selection_export` 메타를 status 화면에도 더 눈에 띄게 보여줄지 검토
- 제목 품질과 선별 export를 함께 써서 실전 발행 큐를 더 단순화

## Date
- 2026-03-25 19:20 (KST)

## What changed (변경점)
- [app/title/quality.py](D:/joe_coding/projects/keyword_forge/app/title/quality.py)에서 `환율 영향`, `확인 포인트`, `국내외 차이` 같은 축약형 홈 제목을 별도 감점하고, 금융 키워드의 `2주간 추이 분석` 같은 회고형 분석 표현은 무조건 최신성 위반으로 자르지 않도록 완화했다.
- [app/title/ai_client.py](D:/joe_coding/projects/keyword_forge/app/title/ai_client.py), [app/title/title_generator.py](D:/joe_coding/projects/keyword_forge/app/title/title_generator.py)에 `bare label` 금지와 금융 분석형 시간 표현 허용 규칙을 추가하고, 금융 rescue 제목을 질문/대조형으로 더 강하게 바꿨다.
- [tests/test_title.py](D:/joe_coding/projects/keyword_forge/tests/test_title.py)에 약한 홈 제목 감점과 금융 분석형 시간 표현 허용 회귀 테스트를 추가했다.

## Why (원인/배경)
- 최신 status에서 `24K금값, 환율 영향` 같은 축약형 제목이 과대평가되고, 반대로 `국제금시세, 2주간의 추이 분석`은 근거 없는 최신성 표현으로 잘리는 판단이 나왔다.
- 사용 의도는 `홈판은 더 후킹 있게`, `정보형은 검색 구조에 맞게`, `금융은 거짓 실시간성만 막고 회고형 분석은 허용` 쪽이었다.

## How verified (검증 방법/체크리스트)
- [x] `python -m py_compile app/title/quality.py app/title/ai_client.py app/title/title_generator.py`
- [x] `pytest -q tests/test_title.py`
- [x] `pytest -q`

## Issues & Fix (문제-원인-해결)
- 문제: 짧고 라벨형인 홈 제목이 후킹으로 잘못 인식되고, 금융 분석형 시간 표현까지 같은 규칙으로 잘려 품질 판단이 어색했다.
- 원인: 홈 훅 신호에 `포인트/기준선/변수` 같은 축약 라벨이 섞여 있었고, 최신성 검사가 `오늘/이번주`와 `2주간 추이`를 구분하지 않았다.
- 해결: 홈 제목의 축약 라벨 감점을 분리하고, 금융은 회고형 분석 창(`2주/3주/1개월 + 추이/분석/흐름`)만 예외 허용하도록 바꿨다.

## Next (다음 작업)
- 서버 재시작 후 같은 금융/비즈니스 카테고리로 다시 실행
- 최신 status에서 홈 제목 점수와 실제 체감이 더 가까워졌는지 확인

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
- 2026-03-25 18:22 (KST)

## What changed (변경점)
- [app/api/routes/generate_title.py](D:/joe_coding/projects/keyword_forge/app/api/routes/generate_title.py) 스트림 제너레이터에 `except` 가드를 추가하고 `json.dumps(..., default=str)`로 직렬화 실패를 흡수하도록 보강했다.

## Why (원인/배경)
- 최신 status에서 제목 단계는 `/generate-title/stream`으로 들어가고 `request_id`도 받았지만, 브라우저는 `stream_read_error / network error`만 표시했다.
- 이 패턴은 스트림이 열린 뒤 서버 쪽 예외가 제너레이터 내부에서 처리되지 않아 소켓이 끊길 때 자주 나온다.

## How verified (검증 방법/체크리스트)
- [x] `python -m py_compile app/api/routes/generate_title.py`
- [x] `pytest -q tests/test_stage_entrypoints.py -k "generate_title_stream"`
- [x] `pytest -q`

## Issues & Fix (문제-원인-해결)
- 문제: 제목 생성 중 실제 서버 예외가 나도 status에는 `network error`만 남아 원인 파악이 어려웠다.
- 원인: 제목 스트림 라우트가 `expand` 스트림처럼 제너레이터 예외를 잡아 `error payload`로 내보내지 않았고, 직렬화 실패도 그대로 연결 종료로 이어질 수 있었다.
- 해결: 제너레이터 예외를 `stream_generator_error` payload로 내려주고, 직렬화는 `default=str`로 안전하게 처리하도록 수정했다.

## Next (다음 작업)
- 서버 재시작 후 같은 제목 run 재실행
- 다음 status에서 `network error`가 사라지는지, 또는 실제 내부 예외 메시지가 노출되는지 확인

## Date
- 2026-03-25 18:15 (KST)

## What changed (변경점)
- [app/web.py](D:/joe_coding/projects/keyword_forge/app/web.py)의 asset version을 `20260325-title-stream-v66`으로 올렸다.

## Why (원인/배경)
- 최신 status를 보니 제목 단계가 아직 `/generate-title` 일반 POST를 타고 있었고, 새로 추가한 `/generate-title/stream`이 브라우저에 반영되지 않았다.
- 원인은 정적 자산 캐시로 보였고, 구버전 JS가 남아 있어 실시간 제목 진행률과 스트림 요청이 적용되지 않았다.

## How verified (검증 방법/체크리스트)
- [x] `python -m py_compile app/web.py app/api/routes/generate_title.py app/title/main.py app/title/title_generator.py`
- [x] `pytest -q tests/test_stage_entrypoints.py -k "generate_title_stream"`
- [ ] 브라우저 강력 새로고침 후 `/generate-title/stream` 호출 여부 확인

## Issues & Fix (문제-원인-해결)
- 문제: 제목 생성이 오래 걸릴 때 브라우저가 `/generate-title` 일반 요청으로 대기하다 `Failed to fetch`로 끊겼다.
- 원인: 스트림 경로를 추가했지만 프런트 asset cache가 갱신되지 않아 구버전 JS가 그대로 실행됐다.
- 해결: asset version을 올려 새 JS를 강제 로드하게 했다.

## Next (다음 작업)
- 서버 재시작 후 브라우저 강력 새로고침
- 다음 status에서 제목 단계 endpoint가 `/generate-title/stream`으로 찍히는지 확인

## Date
- 2026-03-25 18:07 (KST)

## What changed (변경점)
- [app/api/routes/generate_title.py](D:/joe_coding/projects/keyword_forge/app/api/routes/generate_title.py)에 `/generate-title/stream`을 추가해 제목 단계도 `progress -> completed` 스트림을 내보내게 했다.
- [app/title/title_generator.py](D:/joe_coding/projects/keyword_forge/app/title/title_generator.py), [app/title/main.py](D:/joe_coding/projects/keyword_forge/app/title/main.py)에서 제목 생성, 품질 검사, 자동 재작성, 모델 승격, export 단계별 진행 퍼센트를 실시간으로 publish하게 했다.
- [app/web_assets/app_overrides.js](D:/joe_coding/projects/keyword_forge/app/web_assets/app_overrides.js), [app/web_assets/app.js](D:/joe_coding/projects/keyword_forge/app/web_assets/app.js)에서 제목 단계가 `N / total 세트 · %`로 보이도록 바꿨고, [tests/test_stage_entrypoints.py](D:/joe_coding/projects/keyword_forge/tests/test_stage_entrypoints.py)에 스트림 엔드포인트 테스트를 추가했다.

## Why (원인/배경)
- 제목 생성은 체감상 오래 걸리는데, 기존 UI는 `실행 중` 상태만 보여줘서 멈춘 것처럼 느껴졌다.
- 특히 자동 재작성과 모델 승격이 붙는 run에서는 완료 시점 예측이 어려워서, 최소한 현재 몇 세트 처리했고 어느 phase인지 보여줄 필요가 있었다.

## How verified (검증 방법/체크리스트)
- [x] `python -m py_compile app/title/main.py app/title/title_generator.py app/api/routes/generate_title.py`
- [x] `node --check app/web_assets/app_overrides.js`
- [x] `node --check app/web_assets/app.js`
- [x] `pytest -q tests/test_stage_entrypoints.py -k "generate_title_stream or expand_stream or expand_analyze_stream"`
- [x] `pytest -q`

## Issues & Fix (문제-원인-해결)
- 문제: 제목 단계는 완료 전까지 정적인 상태 표시만 있고, 사용자는 실제 진행률을 알 수 없었다.
- 원인: `/generate-title`가 일반 POST 응답만 쓰고, 생성기 내부에서도 progress callback을 전혀 내보내지 않았다.
- 해결: 제목 단계도 스트리밍 라우트와 progress 이벤트를 추가하고, 프런트에서 `생성 -> 품질 검사 -> 재작성 -> 저장` phase를 퍼센트와 함께 표시하도록 연결했다.

## Next (다음 작업)
- 실제 브라우저에서 제목 생성 중 퍼센트 표시와 phase 문구가 자연스러운지 확인
- 필요하면 `재작성 3/10건` 같은 세부 문구를 더 짧게 다듬기

## Date
- 2026-03-25 14:57 (KST)

## What changed (변경점)
- [app/title/quality.py](D:/joe_coding/projects/keyword_forge/app/title/quality.py)에서 `blog` 채널은 `메인 키워드 + 서브 키워드 + 문장부` 구조를 더 높게 보고, 단순 훅 질문형이나 너무 일반적인 문장부는 감점하게 바꿨다.
- 키워드가 제목 맨 앞에 오지 않아도 구조가 충분히 강하면 블로그형에서 바로 감점하지 않게 조정했다.
- [app/title/ai_client.py](D:/joe_coding/projects/keyword_forge/app/title/ai_client.py) 프롬프트도 `블로그는 상위노출 구조 우선, 홈판은 후킹 우선` 방향으로 명시했고, [tests/test_title.py](D:/joe_coding/projects/keyword_forge/tests/test_title.py)에 구조 중심 회귀 테스트를 추가했다.

## Why (원인/배경)
- 최근 status를 보면 `home/blog 분리`는 작동했지만, 블로그형도 아직 `최근 동향과 전망`, `영향 분석`, `왜 다르게 보일까` 같은 느슨한 문장부가 남아 있었다.
- 사용자 기준도 `카피라이팅`보다 `상위노출 구조`가 더 중요했고, `키워드 맨 앞 배치` 같은 구식 규칙보다 상위 결과 공통 구조를 따라가는 방향이 맞았다.

## How verified (검증 방법/체크리스트)
- [x] `python -m py_compile app/title/quality.py app/title/ai_client.py`
- [x] `pytest -q tests/test_title.py -k "hookier or informational_blog or search_structure or generic_blog_wrapper or keyword_tokens_with_inserted_modifiers"`
- [x] `pytest -q`
- [ ] 실제 category run에서 blog 제목이 더 구조적으로 바뀌는지 재확인

## Issues & Fix (문제-원인-해결)
- 문제: 블로그 점수식이 아직 `정보성 유무` 중심이라, 상위노출 구조는 맞지만 키워드 맨 앞이 아니거나, 반대로 훅만 있고 구조가 약한 제목을 충분히 구분하지 못했다.
- 원인: 구조 적합성보다 일부 문구 패턴과 앞배치 여부를 더 직접적으로 봤다.
- 해결: `blog_search_structure`, `blog_generic_wrapper` 체크를 추가하고, 프롬프트에도 `main + support + descriptor` 원칙을 명시했다.

## Next (다음 작업)
- 실제 status/csv에서 블로그형 제목이 `구조 우선`으로 바뀌는지 확인
- 필요하면 category별 상위노출형 문장부 사전을 더 넓히고, generic wrapper 감점을 미세조정

## Date
- 2026-03-25 16:00 (KST)

## What changed (변경점)
- [app/title/quality.py](D:/joe_coding/projects/keyword_forge/app/title/quality.py)에서 채널별 점수 기준을 분리해 `naver_home`은 후킹 신호, `blog`는 정보 신호를 추가 체크하게 했다.
- `naver_home` 제목이 너무 설명서형이면 감점하고, `blog` 제목이 감정훅만 있고 정보 의도가 안 보이면 감점하도록 점수식을 조정했다.
- [tests/test_title.py](D:/joe_coding/projects/keyword_forge/tests/test_title.py)에 홈판 후킹/블로그 정보성 분리 회귀 테스트를 추가했다.

## Why (원인/배경)
- 같은 제목이라도 홈판은 `눌리느냐`, 블로그는 `검색 의도와 정보 구조가 보이느냐`가 중요해서, 같은 점수식으로 평가하면 채널 차이가 흐려졌다.
- 특히 홈판은 너무 설명서 같으면 약하고, 블로그는 너무 감정훅만 남으면 검색형 글 제목으로 약했다.

## How verified (검증 방법/체크리스트)
- [x] `python -m py_compile app/title/quality.py`
- [x] `pytest -q tests/test_title.py -k "hookier or informational_blog or quality"`
- [x] `pytest -q`
- [ ] 실제 run에서 home/blog channel score 분포 재확인

## Issues & Fix (문제-원인-해결)
- 문제: 홈판과 블로그가 서로 다른 역할인데 제목 검수는 거의 공통 점수축으로만 움직였다.
- 원인: 품질 체크가 키워드 충실도, 템플릿성, 중복성 중심이라 `후킹 부족`과 `정보축 부족`을 채널별로 분리해 보지 못했다.
- 해결: 홈판에는 `후킹 포인트`, 블로그에는 `정보 의도` 체크를 추가하고, 블로그의 앞부분 키워드 배치 패널티도 조금 더 강하게 조정했다.

## Next (다음 작업)
- 실제 status/csv에서 `naver_home_score`와 `blog_score` 분포 비교
- 필요하면 홈판 훅 신호를 카테고리별로 더 미세 조정

## Date
- 2026-03-25 15:35 (KST)

## What changed (변경점)
- [app/title/exporter.py](D:/joe_coding/projects/keyword_forge/app/title/exporter.py)에서 CSV export에 `bundle_score`, `bundle_status`, `naver_home_score`, `blog_score`, `target_mode`, `source_kind` 열을 추가했다.
- queue txt export에 기본 품질 게이트를 넣어, `review` 이상이면서 `bundle/channel score >= 75`인 제목만 플랫폼별 live/archive txt에 들어가게 했다.
- `queue_export`는 `quality_gate_enabled`, `min_bundle_score`, `min_channel_score`, `allowed_statuses`를 받도록 확장했고, manifest에도 이 필터 메타를 같이 남긴다.
- `home`와 `wordpress` 사이에서도 제목이 겹치지 않도록 전역 dedupe를 넣고, 첫 제목이 겹치면 채널의 2순위 제목으로 자동 대체하게 했다.
- txt 파일명도 더 단순하게 바꿔, live는 `날짜__카테고리.txt` 또는 `날짜__시드.txt`, archive는 `타임스탬프__카테고리.txt` 또는 `타임스탬프__시드.txt` 형태로 저장되게 했다.

## Why (원인/배경)
- 지금까지 txt queue export는 채널 첫 제목을 그대로 내보내서, 저품질 후보도 바로 발행 큐에 섞일 수 있었다.
- 운영 방식상 필요한 건 `제목 많이 생성 -> 점수/상태로 거름 -> 플랫폼별 큐에 적재` 흐름이었고, CSV에서도 그 판단 근거가 바로 보여야 했다.

## How verified (검증 방법/체크리스트)
- [x] `python -m py_compile app/title/exporter.py`
- [x] `pytest -q tests/test_title.py -k "export or queue"`
- [x] `pytest -q`
- [ ] 실제 UI/실전 run에서 queue filtering 체감 확인

## Issues & Fix (문제-원인-해결)
- 문제: txt export가 점수 기반이 아니라서 발행 큐를 다시 사람이 골라야 했다.
- 원인: exporter가 `quality_report`를 참조하지 않고 채널 첫 제목만 중복 제거 후 적재했다.
- 해결: exporter가 `quality_report.status`, `bundle_score`, `channel_scores`를 읽어 기본적으로 `review 이상 / 75점 이상`만 큐에 넣도록 바꿨고, 필요하면 설정으로 끌 수 있게 했다.
- 문제: 홈판/워프가 따로 저장돼도 제목 자체가 같으면 같은 블로그 안에서 재활용 냄새가 났다.
- 원인: dedupe 범위가 플랫폼 내부로만 제한돼 있었고, 파일명도 topic 중심이라 운영 기준으로 보기엔 덜 직관적이었다.
- 해결: multi-destination export 시 전역 dedupe를 걸고, 같은 제목 충돌 시 각 채널의 대체 제목을 우선 사용하도록 바꿨다. 파일명도 `카테고리 또는 시드 + 날짜` 기준으로 단순화했다.

## Next (다음 작업)
- UI에서 queue quality gate 설정을 조절할 수 있게 노출
- 발행용 txt를 `topic/channel` 단위로 더 세밀하게 분리할지 검토

## Date
- 2026-03-25 15:10 (KST)

## What changed (변경점)
- [app/title/exporter.py](D:/joe_coding/projects/keyword_forge/app/title/exporter.py)에 `queue_export.destination=all/both`를 추가해, 한 번의 제목 생성 결과를 `home`과 `wordpress`로 따로 live/archive/manifest에 내보낼 수 있게 했다.
- 같은 제목은 플랫폼 내부에서만 dedupe하고, `home`과 `wordpress` 사이에는 같은 제목이 있어도 각각 유지되도록 했다.
- [tests/test_title.py](D:/joe_coding/projects/keyword_forge/tests/test_title.py)에 dual queue export와 플랫폼별 dedupe 회귀 테스트를 추가했다.

## Why (원인/배경)
- 운영 방식이 `홈판용 후킹 제목`과 `워프용 정보 제목`을 분리해 누적하는 구조인데, 기존 queue export는 목적지를 한 번에 하나만 처리했다.
- 또 같은 키워드가 플랫폼별로 겹치는 것은 허용하되, 같은 플랫폼 안에서만 중복이 막혀야 실제 발행 큐 운영에 맞는다.

## How verified (검증 방법/체크리스트)
- [x] `python -m py_compile app/title/exporter.py`
- [x] `pytest -q tests/test_title.py -k "queue or split_queue or export"`
- [ ] 실제 UI/운영 루트에서 `destination=all` 사용 확인

## Issues & Fix (문제-원인-해결)
- 문제: 홈판/워프를 함께 운영하려면 같은 생성 결과를 플랫폼별로 따로 쌓아야 하는데, export는 단일 destination 기준이었다.
- 원인: queue export가 `home` 또는 `wordpress` 하나만 받도록 설계돼 있었고, dedupe도 그 단일 목적지 문맥만 고려했다.
- 해결: destination alias(`all/both`)와 multi-bundle export를 추가해 플랫폼별 파일을 각각 만들고, dedupe는 각 플랫폼 live txt 안에서만 동작하게 했다.

## Next (다음 작업)
- CSV에 `bundle_score/status/channel score` 열 추가
- min score / status 기반 txt queue filtering 추가

## Date
- 2026-03-25 14:45 (KST)

## What changed (변경점)
- [app/selector/service.py](D:/joe_coding/projects/keyword_forge/app/selector/service.py) 기본 자동 선별 목표치를 확장량 연동형으로 바꿔, measured pool이 커질수록 `4 -> 6 -> 9 -> 최대 14`까지 늘어나게 했다.
- [tests/test_selector.py](D:/joe_coding/projects/keyword_forge/tests/test_selector.py)에 대형 후보 풀에서 선별 수가 9건까지 확장되는 회귀 테스트를 추가했다.

## Why (원인/배경)
- 실제 운영에서 `3개 확장`과 `100개 확장`이 둘 다 선별 8건 안팎으로 끝나 체감상 selector가 확장량을 반영하지 못했다.
- 기존 기본값은 `ceil(measured * 0.12)`를 계산해도 상한을 8로 잘라 버려, 후보 풀이 커져도 제목 작업용 seed 다양성이 거의 늘지 않았다.

## How verified (검증 방법/체크리스트)
- [x] `python -m py_compile app/selector/service.py`
- [x] `pytest -q tests/test_selector.py`
- [ ] 실제 large expansion run에서 선별 수 증가 재확인

## Issues & Fix (문제-원인-해결)
- 문제: 확장 수를 크게 늘려도 기본 자동 선별 결과가 8건 근처에서 고정됐다.
- 원인: default selection target이 최소 4, 최대 8로 고정돼 있었고, top-up ratio도 보수적이었다.
- 해결: 기본 target을 `0.16` 비율 + 구간별 floor로 다시 잡고, 최종 상한도 14까지 열어 확장량이 큰 run에서는 선별 풀이 실제로 늘어나게 했다.

## Next (다음 작업)
- 실제 리뷰/금융 run에서 선별 수와 제목 품질의 균형 확인
- 필요하면 UI에 `보수적/표준/공격적 선별` preset 추가

## Date
- 2026-03-25 14:20 (KST)

## What changed (변경점)
- [app/title/category_detector.py](D:/joe_coding/projects/keyword_forge/app/title/category_detector.py), [app/selector/longtail.py](D:/joe_coding/projects/keyword_forge/app/selector/longtail.py), [app/title/targets.py](D:/joe_coding/projects/keyword_forge/app/title/targets.py)에 `finance` 전용 분기를 넣어 `시세/지수/계좌` 키워드를 더 정확히 분류하고, `실사용 차이/자주 생기는 문제` 같은 기기형 롱테일은 건너뛰게 했다.
- [app/title/ai_client.py](D:/joe_coding/projects/keyword_forge/app/title/ai_client.py), [app/title/quality.py](D:/joe_coding/projects/keyword_forge/app/title/quality.py), [app/title/title_generator.py](D:/joe_coding/projects/keyword_forge/app/title/title_generator.py)에서 금융 제목을 `괴리/해석/기준선/변수/조건` 중심으로 유도하고, 어색한 프레임이 나오면 품질 단계와 rescue 단계에서 다시 걸러내게 했다.
- [tests/test_title.py](D:/joe_coding/projects/keyword_forge/tests/test_title.py)에 금융 mismatch, 프롬프트 힌트, title target 필터 회귀를 추가했다.

## Why (원인/배경)
- 실제 run에서 `국제금시세`, `코스피200 야간선물`, `ISA 계좌 개설` 같은 금융 키워드에 `실사용 차이`, `자주 생기는 문제`, `동선 체크`류가 붙으면서 홈판 후킹은 있어도 신뢰성과 의도 일치가 무너졌다.
- 특히 금융은 `오늘/방금` 같은 가짜 실시간 훅보다 `왜 다르게 보이는지`, `어떤 기준을 먼저 봐야 하는지` 식의 해석 훅이 더 안전하고 맞는 방향이었다.

## How verified (검증 방법/체크리스트)
- [x] `python -m py_compile app/selector/longtail.py app/title/category_detector.py app/title/targets.py app/title/quality.py app/title/ai_client.py app/title/title_generator.py`
- [x] `pytest -q tests/test_title.py tests/test_selector.py`
- [x] `pytest -q`
- [ ] 실제 finance seed로 새 status/csv 재확인

## Issues & Fix (문제-원인-해결)
- 문제: 금융 키워드가 일반/기기형 practical 프레임으로 흘러 제목과 롱테일이 어색해졌다.
- 원인: 카테고리 감지 범위가 좁았고, `finance`여도 longtail/title/rescue가 공통 practical 분기를 타는 구간이 남아 있었다.
- 해결: `finance market`와 `finance account/policy`를 분리해 longtail, prompt, quality, rescue를 모두 `괴리/판단/조건/확인 포인트` 축으로 재정렬했다.

## Next (다음 작업)
- 실제 `finance` 실전 run 결과에서 `재생성 권장`, `실사용 차이`, `자주 생기는 문제` 잔존량 확인
- 필요하면 `naver_home` 쪽에서 `괴리형/판단형/조건형` pair 분기를 한 단계 더 세분화

## Date
- 2026-03-25 12:45 (KST)

## What changed (변경점)
- [app/collector/naver_trend.py](D:/joe_coding/projects/keyword_forge/app/collector/naver_trend.py)와 [app/local/naver_login_browser.py](D:/joe_coding/projects/keyword_forge/app/local/naver_login_browser.py)의 Creator Advisor 세션 캐시 경로를 상대경로 `.local/...` 대신 프로젝트 루트 기준 절대경로로 고정했다.
- [tests/test_naver_trend.py](D:/joe_coding/projects/keyword_forge/tests/test_naver_trend.py), [tests/test_local_naver.py](D:/joe_coding/projects/keyword_forge/tests/test_local_naver.py)에 경로 고정 회귀를 추가했다.

## Why (원인/배경)
- 실전 category 수집에서 `Unauthorized: no user logged in`, `HTTP 423`, `auth_lock_active: true`가 나왔고, 로컬 로그인 세션은 저장돼 있는데 수집기가 못 읽는 정황이 있었다.
- 원인을 보면 세션 파일 경로가 `Path(".local")` 상대경로라서, 서버를 `D:\joe_coding`에서 띄우면 `D:\joe_coding\.local`을 보고, 프로젝트 폴더에서 띄우면 `projects\keyword_forge\.local`을 보는 식으로 실행 위치에 따라 달라질 수 있었다.

## How verified (검증 방법/체크리스트)
- [x] `python -m py_compile app/collector/naver_trend.py app/local/naver_login_browser.py tests/test_naver_trend.py tests/test_local_naver.py`
- [x] `pytest -q tests/test_naver_trend.py tests/test_local_naver.py`
- [x] `pytest -q`
- [ ] 서버 재시작 후 실제 category + naver_trend 실전 재확인

## Issues & Fix (문제-원인-해결)
- 문제: 로그인은 했는데 category 수집 시 Creator Advisor가 비로그인으로 판정되며 보호 락까지 걸렸다.
- 원인: 세션 캐시가 실행 작업 디렉터리에 따라 서로 다른 `.local`을 보게 되어, 저장한 세션과 읽는 세션 경로가 엇갈릴 수 있었다.
- 해결: 네이버 세션/로그인 브라우저 경로를 모두 프로젝트 루트 절대경로로 통일했다.

## Next (다음 작업)
- 서버 재시작 후 `보호 락 해제 -> 전용 로그인 브라우저 -> category 수집` 순서로 실전 확인
- 필요하면 `auth_lock_active`가 있을 때 UI에서 더 직접적인 복구 버튼/문구를 보여주기

---

## Date
- 2026-03-25 10:20 (KST)

## What changed (변경점)
- 예전에 쓰던 `네이버 홈판 최적화 프롬프트`의 핵심을 현재 엔진에 맞게 흡수해 [app/title/category_detector.py](D:/joe_coding/projects/keyword_forge/app/title/category_detector.py) 감지 키워드를 넓히고, [app/title/ai_client.py](D:/joe_coding/projects/keyword_forge/app/title/ai_client.py) 프롬프트에 `카테고리 경계 유지`, `이슈/논쟁/반전 2중 결합`, `YMYL 완곡 표현` 규칙을 더 명시했다.
- [app/title/targets.py](D:/joe_coding/projects/keyword_forge/app/title/targets.py)에서 selected keyword dedupe 서명에 `추천/비교/방법/설정` 같은 intent token을 조건부로 포함하게 바꿔 `경제 뉴스 추천`과 `경제 뉴스 비교`가 하나로 합쳐지지 않게 했다.
- [tests/test_title.py](D:/joe_coding/projects/keyword_forge/tests/test_title.py)에 `청약 vs ETF` 카테고리 분류, `기초연금` senior overlay, `intent token 다른 single keyword 보존` 회귀를 추가했다.

## Why (원인/배경)
- 사용자가 주신 예전 홈판 프롬프트에는 현재 엔진보다 더 분명한 `카테고리별 데이터 훅`, `도메인 경계`, `준최2/YMYL 톤`, `홈판용 프레임 결합` 기준이 있었고, 그중 좋은 부분은 지금 구조에 녹일 가치가 있었다.
- 동시에 현재 HEAD는 `selected_keywords 4개 -> generated_titles 3개` 회귀로 [tests/test_pipeline.py](D:/joe_coding/projects/keyword_forge/tests/test_pipeline.py) 2건이 실패했고, 실제 누락 키워드는 `경제 뉴스 비교`였다.

## How verified (검증 방법/체크리스트)
- [x] `python -m py_compile app/title/category_detector.py app/title/ai_client.py app/title/targets.py tests/test_title.py`
- [x] `pytest -q tests/test_title.py -k "detect_category_distinguishes_real_estate_and_finance_signals or category_boundary_rule_and_senior_overlay or keeps_single_keywords_when_intent_token_differs"`
- [x] `pytest -q tests/test_pipeline.py -k "test_pipeline_run_returns_all_stage_outputs or test_pipeline_endpoint_runs_end_to_end"`
- [x] `pytest -q`
- [ ] 실제 제목 run에서 홈판형 출력이 과하게 템플릿화되지 않는지 확인

## Issues & Fix (문제-원인-해결)
- 문제: 홈판용 제목 방향은 있었지만 카테고리 경계/안전 톤이 프롬프트에 더 명확히 반영될 여지가 있었고, title target dedupe가 `비교` 같은 의미 차이를 지워서 파이프라인 결과 수를 줄였다.
- 원인: detector/prompt가 예전 홈판 프롬프트만큼 넓은 키워드 범위를 커버하지 않았고, dedupe signature는 stop token을 너무 공격적으로 제거해 `추천`과 `비교`를 같은 묶음으로 봤다.
- 해결: 프롬프트는 홈판 규칙을 더 직접적으로 명시하고, dedupe signature는 의미가 달라지는 intent token은 보존하도록 바꿨다.

## Next (다음 작업)
- 실제 status를 다시 뽑아 홈판형 `naver_home` 제목이 예전 프롬프트 방향으로 더 자연스러워졌는지 확인하기
- `senior_health_info`와 일반 `health`를 지금처럼 묶어 둘지, 카테고리를 더 세분화할지 검토하기

---

## Date
- 2026-03-25 02:45 (KST)

## What changed (변경점)
- `app/title/exporter.py`, `app/title/main.py`를 정리해 기본 제목 산출물을 `output/csv` 아래로 모으고, 1차 설계 기준의 `txt queue export` 기반을 추가했다.
- `title_export.queue_export` 설정으로 `output/txt/live/<destination>/<topic>.txt`, `output/txt/archive/...txt`, `output/manifests/...json`을 함께 남길 수 있게 했고, `generation_meta.queue_export`에도 결과 메타를 실었다.
- `tests/test_title.py`에 `csv 하위 폴더`, `txt live/archive/manifest` 회귀를 추가했고, pipeline 경로 테스트와 전체 테스트도 다시 통과시켰다.

## Why (원인/배경)
- 현재 실제 운영 흐름은 `제목 생성 -> 주제별 txt 파일 -> PRIME가 순차 포스팅`에 가깝고, 기존 `output/*.csv`만으로는 이 큐 등록 흐름을 추적하기 어려웠다.
- 또 `txtoutput`처럼 별도 루트를 더 만들기보다 `output` 아래에서 `csv/txt/manifests`로 통합하는 편이 구조를 덜 복잡하게 유지할 수 있었다.

## How verified (검증 방법/체크리스트)
- [x] `python -m py_compile app/title/exporter.py app/title/main.py tests/test_title.py`
- [x] `pytest -q tests/test_title.py -k "exports_csv_by_default or queue_txt_bundle or export_multiple_formats"`
- [x] `pytest -q tests/test_pipeline.py -k "generate_title_endpoint_returns_wrapped_title_sets or pipeline_endpoint_runs_end_to_end"`
- [x] `pytest -q`
- [ ] 브라우저에서 `워드프레스용 / 홈판용 txt 보내기` UI 연결 확인

## Issues & Fix (문제-원인-해결)
- 문제: 제목 결과는 자동 저장되지만, 실제 포스팅 큐로 넘기는 `주제별 txt` 구조와 상태 추적 기준이 없었다.
- 원인: exporter가 `csv/xlsx/md/txt` 파일 포맷 중심이었고, `한 키워드 한 채널` 기준의 queue 개념과 manifest 저장이 없었다.
- 해결: 1차 설계로 범위를 줄여 `txt export = queued` 기반만 먼저 만들고, `output/csv`, `output/txt/live`, `output/txt/archive`, `output/manifests` 구조를 서버에서 바로 만들도록 정리했다.

## Next (다음 작업)
- 결과 카드에서 선택한 제목을 `워드프레스용 txt` 또는 `홈판용 txt`로 보내는 UI 버튼 붙이기
- `queued` 상태와 중복 경고를 `txt export 시점` 기준으로만 반영하도록 프런트 상태 흐름 단순화하기

---

## Date
- 2026-03-25 02:20 (KST)

## What changed (변경점)
- `README.md` 다음 작업 목록에 `텔레그램 / 외부 에이전트` 연동용 자동화 API 아이디어를 추후 과제로 기록했다.
- 방향은 `키워드/주제 지시 -> 시드 생성 또는 queue 등록 -> 완료 알림 -> artifact/요약 전송` 흐름이다.

## Why (원인/배경)
- 현재 queue/API 구조만으로도 외부 자동화 연결 여지는 충분하지만, 지금 우선순위는 플랫폼 완성도와 제목 품질 안정화다.
- 그래서 당장 구현하지 않고, 후속 자동화 방향만 문서에 먼저 남겨 두는 편이 맞았다.

## How verified (검증 방법/체크리스트)
- [x] `README.md` 다음 작업 목록 반영 확인
- [ ] 실제 자동화 API 사양 문서화

## Issues & Fix (문제-원인-해결)
- 문제: 외부 자동화 아이디어가 대화에만 남으면 후속 우선순위에서 빠질 수 있었다.
- 원인: 별도 backlog 항목 없이 즉흥 아이디어 수준으로만 존재했다.
- 해결: README/DEVLOG에 후속 자동화 방향을 명시해 추후 개발 목록으로 승격했다.

## Next (다음 작업)
- 제목 품질과 결과 신뢰도를 더 끌어올리는 쪽에 집중하기
- 외부 자동화는 플랫폼 안정화 후 `API 토큰 / 웹훅 / queue callback` 설계와 함께 착수하기

---

## Date
- 2026-03-24 17:55 (KST)

## What changed (변경점)
- `app/title/title_generator.py`에 practical rescue 경로를 추가해 `설정 팁/실사용 차이/장단점/자주 생기는 문제/사전예약 방법` 키워드가 AI 재시도 뒤에도 저품질이면 deterministic 구조화 제목으로 한 번 더 구제하게 바꿨다.
- rescue suffix 선택도 보정해 `general` 카테고리라고 해서 무조건 제품형(`블루투스/DPI/버튼`) 문구를 쓰지 않고, 키워드 자체가 제품형으로 보일 때만 그 분기를 타게 했다.
- `app/title/ai_client.py`의 기본/item 프롬프트 둘 다에 `Do not shorten the keyword phrase` 규칙을 넣어 `손목 편한 마우스 설정 팁 -> 편한 마우스 설정 팁` 같은 축약을 더 강하게 막았다.
- `tests/test_title.py`에 `실패한 AI 재시도 뒤 rescue 제목 채택`, `keyword shortening 경고` 회귀를 추가했다.

## Why (원인/배경)
- 최신 `V1 + V2` status에서 `22세트 전부 retry`, `자동 재작성 22회 채택 0`, `모델 승격 채택 0`, `평균 74점`으로 떨어졌고, 실제 제목도 `최신 정보/총정리/완벽 가이드/뭐가 다를까`와 키워드 축약이 다시 보였다.
- 프롬프트만 세게 하는 방식으로는 해결이 안 됐고, 같은 실패 골격이 반복되면 후단에서 구조적으로 다른 제목을 만들어 주는 구제 단계가 필요했다.

## How verified (검증 방법/체크리스트)
- [x] `python -m py_compile app/title/title_generator.py app/title/ai_client.py tests/test_title.py`
- [x] `pytest -q tests/test_title.py -k "practical_rescue or warns_against_keyword_shortening or auto_retries_low_quality_ai_titles or escalates_model_after_two_failed_quality_attempts"`
- [x] `pytest -q tests/test_title.py -k "practical_rescue or warns_against_keyword_shortening"`
- [x] `pytest -q`
- [ ] 실제 새 status에서 rescue 채택 수와 `retry` 감소 확인

## Issues & Fix (문제-원인-해결)
- 문제: V1+V2만 켜도 제목이 전부 `retry`로 남고, AI 재시도와 모델 승격이 실질적으로 품질을 올리지 못했다.
- 원인: practical keyword 위에 generic wrapper가 반복될 때 프롬프트만으로는 골격을 바꾸지 못했고, descriptive keyword 앞 토큰이 종종 잘렸으며 `general` 분기가 제품형 rescue 문구를 과하게 사용할 여지도 있었다.
- 해결: practical keyword는 후단 rescue 제목 세트를 deterministic하게 만들고, full keyword 보존 규칙을 prompt helper 전부에 넣었으며, 제품형 rescue는 키워드 자체가 제품처럼 보일 때만 쓰도록 좁혔다.

## Next (다음 작업)
- 새 status에서 `auto_retry accepted_count`가 실제 rescue 채택까지 반영되는지 확인하기
- practical rescue 제목이 실제 status에서도 broad/product/non-product 케이스별로 너무 비슷해지지 않는지 점검하기

---

## Date
- 2026-03-24 17:15 (KST)

## What changed (변경점)
- `app/title/quality.py`에서 `실사용 차이/장단점/설정 팁/자주 생기는 문제/연결 문제` 같은 구체 글감 키워드 위에 `총정리/완벽 가이드/최신 정보`를 덧씌우는 제목을 하드 리젝트하게 바꿨다.
- `app/title/targets.py`에 related mode 키워드 정리 헬퍼를 넣어 `스트라이크 스트라이크`, `m720` 혼입 같은 모델명 잡음을 줄이고 대표 키워드 + concrete suffix 중심으로 정리했다.
- `app/title/ai_client.py`, `app/title/title_generator.py` 프롬프트에 웹 검색에서 확인한 실전형 제목 패턴(증상/환경/기간/해결 결과 중심)을 반영했고, `tests/test_title.py` 회귀 테스트 4건을 추가했다.

## Why (원인/배경)
- 최신 status에서 `32세트`까지 수량은 회복됐지만, 실제 제목은 `최신 비교 분석`, `총정리 가이드`, `완벽 가이드`, `최신 정보`가 다시 덧붙으며 평균 점수가 `70점`까지 내려갔다.
- 검색에 실제로 잘 걸리는 제목은 `모델 + 증상/효과 + 기간/환경`, `모델 + 연결/설정 + 기기 맥락`, `모델 + 문제 + 해결 결과`처럼 훨씬 구체적이었고, 지금 생성기는 그 방향을 후단에서 다시 흐리고 있었다.

## How verified (검증 방법/체크리스트)
- [x] `python -m py_compile app/title/quality.py app/title/targets.py app/title/ai_client.py app/title/title_generator.py`
- [x] `pytest -q tests/test_title.py`
- [x] `pytest -q tests/test_selector.py`
- [x] `pytest -q`
- [ ] 실제 `로지텍 마우스` 재실행 후 새 status 비교

## Issues & Fix (문제-원인-해결)
- 문제: 좋은 글감 키워드를 만들어도 제목 생성 단계가 다시 `총정리/완벽 가이드/최신 정보` 같은 템플릿 골격을 덧씌우고, V2/V3는 모델명 잡음이 섞였다.
- 원인: 품질 필터는 concrete keyword 위의 generic overlay를 별도로 잡지 않았고, related mode target은 대표 키워드와 support 토큰 혼입을 충분히 정리하지 않았다.
- 해결: concrete keyword + generic overlay 조합은 하드 리젝트로 격상하고, related mode는 대표 키워드 기준으로 노이즈를 접어 넣었으며, 프롬프트도 실전형 제목 구조를 직접 힌트로 주게 바꿨다.

## Next (다음 작업)
- 새 status에서 `총정리/완벽 가이드/최신 정보/꼭 알아두세요` 빈도와 `재생성 권장` 수가 얼마나 줄었는지 확인하기
- 필요하면 `문제` 계열을 `원인/해결/증상/설정 오류/연결 끊김` 하위 프레임으로 더 잘게 분기하기

---

## Date
- 2026-03-24 16:38 (KST)

## What changed (변경점)
- `app/selector/longtail.py`의 general longtail 기본 출력을 `추천 기준/비교 포인트/고를 때 체크` 대신 `실사용 차이/장단점/자주 생기는 문제/설정 팁` 축으로 바꿨다.
- `app/title/targets.py`에서 저정보 longtail suggestion을 그냥 버리지 않고, 구체적인 글감 키워드로 치환한 뒤 `longtail_selected` 타깃으로 다시 살리도록 바꿨다.
- `tests/test_selector.py`, `tests/test_title.py` 기대값을 새 longtail 방향에 맞게 갱신했고 전체 테스트를 다시 통과시켰다.

## Why (원인/배경)
- 실제 status에서 하드 필터 이후 `30세트 -> 10세트`로 줄어든 원인은 생성 실패가 아니라, V1 longtail target이 템플릿형이라 제목 단계에서 거의 사라졌기 때문이었다.
- 사용자는 매번 구매형 글만이 아니라 문제, 현상, 사용 경험까지 다루길 원했고, 현재 longtail 생성은 그 방향을 충분히 반영하지 못했다.

## How verified (검증 방법/체크리스트)
- [x] `python -m py_compile app/selector/longtail.py app/title/targets.py`
- [x] `pytest -q tests/test_selector.py tests/test_title.py`
- [x] `pytest -q`
- [ ] 실제 `로지텍 마우스` 재실행 후 status 비교

## Issues & Fix (문제-원인-해결)
- 문제: 템플릿형 longtail을 강하게 막자 제목 세트 수가 너무 많이 줄었다.
- 원인: longtail 생성기가 여전히 `추천 기준/비교 포인트/고를 때 체크` 중심이었고, title target 단계는 이를 버리기만 했다.
- 해결: longtail 기본 출력을 문제/현상형 글감으로 바꾸고, 이미 들어온 저정보 longtail도 `실사용 차이/장단점`류로 치환해 다시 타깃으로 사용하게 했다.

## Next (다음 작업)
- 실제 `로지텍 마우스`를 다시 돌려 V1 수가 회복되는지, 제목 결과가 구매형 한쪽으로 치우치지 않는지 확인하기
- 필요하면 카테고리별 suffix를 더 세분화해 디바이스/금융/정책 키워드별 글감 톤을 더 맞추기

---

## Date
- 2026-03-24 16:09 (KST)

## What changed (변경점)
- `app/title/quality.py`에 `제목 골격이 템플릿형 표현에 머물러 있습니다.` 하드 리젝트를 추가해 `추천 기준`, `고를 때 체크`, `최신 정보`, `구매 가이드`, `총정리`류 제목은 최종 통과하지 못하게 바꿨다.
- `app/selector/service.py`에서 `추천 기준`, `고를 때 체크`, `비교 포인트`, `최신 정보` 프레임을 가진 키워드는 기본 자동 선별에서 우선 제외하고, fallback 정렬에서도 뒤로 밀리게 했다.
- `app/title/targets.py`에서 자동 생성된 longtail title target 중 `추천 기준`, `고를 때 체크`, `비교 포인트`, `최신 정보` 계열은 건너뛰도록 바꿨고, 회귀 테스트 3건을 추가했다.

## Why (원인/배경)
- 최신 status를 보면 자동 재작성은 실제로 작동했지만, 최종 결과에는 여전히 `추천 기준`, `고를 때 체크`, `최신 정보`, `구매 가이드` 같은 골격이 많이 남아 있었다.
- 원인은 제목 생성기만의 문제가 아니라, title target으로 들어가는 longtail 키워드 자체가 이미 템플릿형 표현으로 기울어 있다는 점이었다.

## How verified (검증 방법/체크리스트)
- [x] `python -m py_compile app/title/quality.py app/selector/service.py app/title/targets.py`
- [x] `pytest -q tests/test_title.py`
- [x] `pytest -q tests/test_selector.py`
- [x] `pytest -q`
- [ ] 실제 `로지텍 마우스` 재실행 후 status 비교

## Issues & Fix (문제-원인-해결)
- 문제: status 기준으로 제목이 실제로는 비슷한 템플릿에서 크게 벗어나지 않았고, target keyword도 `추천 기준`/`고를 때 체크` 쪽으로 쏠렸다.
- 원인: 저정보 골격을 감점만 하고 있었고, 자동 title target 단계도 템플릿형 longtail을 그대로 채택했다.
- 해결: 최종 제목엔 하드 리젝트를 추가하고, selector/title target 단계에서도 템플릿형 키워드를 덜 뽑도록 걸렀다.

## Next (다음 작업)
- 실제 `로지텍 마우스`를 다시 돌려 status에서 `추천 기준`, `고를 때 체크`, `최신 정보`, `구매 가이드` 비중이 얼마나 줄었는지 확인하기
- 모델 승격 채택이 여전히 `0`이면 escalation prompt 또는 target model을 한 단계 더 강하게 조정하기

---

## Date
- 2026-03-24 15:30 (KST)

## What changed (변경점)
- `app/title/quality.py`에 `제목 골격이 너무 일반적입니다.` 규칙을 추가해 `최신 정보`, `업데이트 확인`, `구매 가이드`, `사용 후기`, `신상`, bare `비교` 같은 저정보 골격을 직접 감점하도록 바꿨다.
- `app/title/ai_client.py`, `app/title/presets.py`, `app/title/title_generator.py`에서 fast/재작성 프롬프트를 강화해 `추천 기준`, `체크리스트`, `가이드` 같은 추상 골격 대신 `실사용 차이`, `장단점`, `성능`, `세팅`, `가격대`, `추천 대상`처럼 더 구체적인 표현을 요구하도록 바꿨다.
- `tests/test_title.py`에 generic skeleton 감지 회귀 테스트 2건을 추가했고 전체 테스트를 다시 통과시켰다.

## Why (원인/배경)
- 최신 status를 보면 자동 재작성 메타는 보였지만, 실제 제목은 여전히 `최신 정보`, `구매 가이드`, `추천 기준`, `고를 때 체크`, `체크리스트` 같은 정보 밀도 낮은 골격이 많이 남아 있었다.
- 즉 문제는 단순 반복만이 아니라, 모델이 빠르게 안전한 골격으로 도망가면서 구체성이 부족한 제목을 계속 내는 점이었다.

## How verified (검증 방법/체크리스트)
- [x] `python -m py_compile app/title/quality.py app/title/ai_client.py app/title/presets.py app/title/title_generator.py`
- [x] `pytest -q tests/test_title.py`
- [x] `pytest -q`
- [ ] 실제 `로지텍 마우스` 재실행 후 status 비교

## Issues & Fix (문제-원인-해결)
- 문제: 제목이 반복될 뿐 아니라 `최신 정보`, `구매 가이드`, `사용 후기`처럼 너무 일반적인 골격으로 많이 출력됐다.
- 원인: fast preset/재작성 프롬프트가 “반복은 피하라” 수준이라, 모델이 여전히 저정보 안전 문구로 수렴했다.
- 해결: 저정보 골격은 품질 점수에서 직접 감점하고, fast/재작성 프롬프트는 구체 표현을 강제하도록 강화했다.

## Next (다음 작업)
- `로지텍 마우스`를 다시 돌려 `추천 기준`, `고를 때`, `체크리스트`, `구매 가이드`, `최신 정보` 빈도가 얼마나 줄었는지 확인하기
- 필요하면 product 계열 키워드에 한해 `실사용/성능/무게/그립감/버튼/배터리/세팅` 같은 표현을 더 강하게 밀도록 추가 튜닝하기

---

## Date
- 2026-03-24 15:13 (KST)

## What changed (변경점)
- `app/web_assets/app.js`에 제목 생성 메타 요약 함수를 추가해 `auto_retry`, `model_escalation`, `final_model` 정보를 결과 요약 문자열에 함께 노출하도록 바꿨다.
- `app/web_assets/app_overrides.js`의 `제목 결과` / `제목 워크플로` 카드에 `자동 재작성`, `모델 승격` 통계를 직접 표시하고, 별도 메타 요약 줄도 넣었다.
- `app/web_assets/app_workflow_utils.js`의 실행 기록도 모델만 보이던 요약 대신 자동 재작성/승격 메타까지 함께 남기도록 바꿨고, `app/web.py` asset version을 갱신했다.

## Why (원인/배경)
- 최신 status html을 보면 선별 증가는 확인됐지만, 현재 run에서 자동 재작성과 모델 승격이 실제로 몇 번 일어났는지는 화면에서 바로 읽기 어려웠다.
- `generation_meta`에는 값이 들어오는데, 프런트 요약 문자열과 실행 기록 카드가 대부분 모델 정보만 보여줘서 사용자가 자동 재작성 작동 여부를 판단하기 힘들었다.

## How verified (검증 방법/체크리스트)
- [x] `node --check app/web_assets/app.js`
- [x] `node --check app/web_assets/app_workflow_utils.js`
- [x] `node --check app/web_assets/app_overrides.js`
- [x] `python -m py_compile app/web.py`
- [x] `pytest -q tests/test_web_routes.py`
- [ ] 브라우저에서 status/export 화면 확인

## Issues & Fix (문제-원인-해결)
- 문제: status html에서 자동 재작성과 모델 승격이 실제로 작동했는지 바로 확인하기 어려웠다.
- 원인: 화면 요약이 `generation_meta`의 상세 메타를 버리고 preset/provider/model 위주로만 노출하고 있었다.
- 해결: 결과 카드, 제목 워크플로 카드, 실행 기록 요약에 `자동 재작성 시도/채택`, `모델 승격`, `최종 모델` 흐름이 남도록 프런트 요약을 확장했다.

## Next (다음 작업)
- 브라우저에서 새 status를 다시 저장해 `자동 재작성 0회`인지, `N회 시도 / M건 채택`인지 실제로 보이는지 확인하기
- 필요하면 결과 리스트 상단에도 `generation_meta` 전용 진단 패널을 추가해 디버그 모드 없이도 더 자세히 읽게 만들기

---

## Date
- 2026-03-24 14:50 (KST)

## What changed (변경점)
- `app/title/quality.py`에 배치 단위 제목 유사성 가드를 추가해, 키워드를 제거한 뒤에도 같은 제목 골격이 반복되면 품질 점수와 상태에 반영되도록 바꿨다.
- `app/title/title_generator.py`의 재시도 판단을 조정해, 여전히 `retry` 판정인 후보는 중간 자동 재시도에서 채택하지 않고 모델 승격 단계로 넘기도록 정리했다.
- `tests/test_title.py`에 배치 반복 제목 골격 회귀 테스트를 추가했고, 제목 테스트/전체 테스트를 다시 통과시켰다.

## Why (원인/배경)
- 실제 status html을 보면 `뭐가 다를까`, `추천 기준`, `체크리스트`, `비교 포인트` 같은 제목 골격이 배치 전체에서 반복되는 문제가 있었는데, 기존 품질 평가는 같은 키워드 안에서만 유사성을 봤다.
- 그래서 개별 키워드 품질 점수는 높아도 사이트 레벨에서는 템플릿 냄새가 남았고, 자동 재시도도 아직 재생성 권장인 후보를 중간 단계에서 받아들이는 경우가 있었다.

## How verified (검증 방법/체크리스트)
- [x] `pytest -q tests/test_title.py`
- [x] `pytest -q`
- [ ] 실데이터 배치 재실행 (`로지텍 마우스` 등)
- [ ] status html에서 제목 반복도 재확인

## Issues & Fix (문제-원인-해결)
- 문제: 키워드만 다르면 통과돼서 배치 전체 제목 골격 반복을 제대로 잡지 못했다.
- 원인: 품질 검사가 단건/채널 내부 중심이었고, 자동 재시도 채택 기준도 `retry -> retry` 후보를 받아들일 여지가 있었다.
- 해결: 배치 단위 skeleton 비교 + noisy family 반복 가드를 추가하고, 아직 `retry_recommended`인 재시도 후보는 채택하지 않도록 조정했다.

## Next (다음 작업)
- 실제 대형 키워드로 제목 생성 결과를 다시 뽑아 `뭐가 다를까`, `추천 기준`, `체크리스트`, `비교 포인트` 반복도가 얼마나 줄었는지 확인하기
- 필요하면 status html 기준으로 skeleton family 임계치와 패널티 강도를 한 번 더 미세조정하기

---

## Date
- 2026-03-24 11:46 (KST)

## What changed (변경점)
- `app/title/templates.py`에서 `비교`, `체크`, `체크리스트`, `가이드` 계열 문구가 과도하게 반복되지 않도록 제목 템플릿 문구를 다듬고, 같은 키워드 안에서 noisy frame이 연속 선택되지 않게 보정했다.
- `app/title/presets.py`의 기본 AI 프리셋 가이던스도 `checklist/comparison` 골격을 과하게 반복하지 말도록 톤을 조정했다.
- `app/selector/service.py`에 기본 자동 선별의 최소 확보 수를 추가해 `gold/promising`이 몇 개 안 나올 때도 measured 후보를 `editorial_support`로 적당량 보충하도록 바꿨다.

## Why (원인/배경)
- 실제 사용 중 제목 결과가 `체크`, `비교`, `체크리스트` 쪽으로 자주 쏠렸고, 대형 키워드에서는 선별이 지나치게 적게 남아 다음 단계 작업성이 떨어졌다.
- 원인을 보면 제목은 기본 템플릿/프리셋 어휘가 해당 단어군을 강하게 밀고 있었고, 선별은 기본 자동 모드가 `gold/promising`만 통과시키고 수가 적어도 추가 보충을 하지 않았다.

## How verified (검증 방법/체크리스트)
- [x] `pytest -q tests/test_title.py tests/test_selector.py`
- [ ] `pytest -q`
- [ ] 브라우저/실데이터 수동 확인

## Issues & Fix (문제-원인-해결)
- 문제: 제목이 특정 어휘 골격으로 반복되고, 선별 수가 지나치게 적게 나오는 경우가 있었다.
- 원인: 제목은 템플릿/프리셋 편향, 선별은 기본 자동 모드의 지나친 컷오프 구조 때문이었다.
- 해결: 제목은 문구 다양화 + noisy frame 중복 억제를 넣고, 선별은 자동 모드에서 measured 후보를 최소 수량만큼 보충하도록 조정했다.

## Next (다음 작업)
- 실제 `로지텍 마우스` 같은 대형 키워드에서 선별 수와 제목 어휘 편향이 개선됐는지 확인하기
- 필요하면 자동 선별 최소 개수와 제목 프레임 다양화 강도를 추가 튜닝하기

---

## Date
- 2026-03-24 11:33 (KST)

## What changed (변경점)
- `workspace-nav`에서 `결과 작업대` 링크를 제거해 상단 스티키 바를 `실행 조건 / 빠른 시작 / 결과 단계 5개` 구성으로 더 압축했다.
- `app/web.py`의 asset version을 다시 올려 브라우저가 이전 상단 네비 캐시를 잡지 않게 했다.

## Why (원인/배경)
- 결과 단계 5개가 이미 상단 스티키 바 안으로 들어온 뒤에는 `결과 작업대` 링크가 사실상 같은 영역으로 가는 중복 진입점이 됐다.
- 상단 바는 정보보다 전환 밀도가 중요하므로, 중복 링크를 빼는 편이 더 읽기 쉽고 단계 버튼도 덜 답답하게 보인다.

## How verified (검증 방법/체크리스트)
- [ ] 브라우저 수동 확인
- [ ] `python -m py_compile app/web.py`
- [ ] `pytest -q tests/test_web_routes.py`

## Issues & Fix (문제-원인-해결)
- 문제: 상단 스티키 바에 `결과 작업대` 링크와 결과 단계 5개가 함께 있어 역할이 겹쳤다.
- 원인: 결과 단계 전환 UI를 상단으로 옮긴 뒤에도 이전 섹션 이동 링크가 그대로 남아 있었다.
- 해결: `결과 작업대` 링크를 제거해 상단 바를 결과 단계 전환 중심으로 정리했다.

## Next (다음 작업)
- 브라우저에서 상단 스티키 바 밀도와 가로 스크롤 체감 확인하기
- 결과 작업대 내부 렌더링 추가 분리 작업 이어가기

---

## Date
- 2026-03-24 11:27 (KST)

## What changed (변경점)
- `workspace-nav`에서 `진행 현황`, `운영 설정`, `진단 / 로그` 항목을 제거하고, 그 자리에 결과 단계 5개를 가로 전환 버튼으로 붙였다.
- `app/web.py`에서 오른쪽 `결과 단계` 패널을 제거하고 `진단 / 로그` 버튼을 hero 액션 영역으로 옮겨 상단 네비의 역할을 `섹션 이동 + 결과 전환` 중심으로 재정리했다.
- `app/web_assets/app_overrides.js`와 `app/web_assets/app.css`에서 결과 단계 도크가 패널이 아니라 상단 스티키 네비 안에서 렌더링되도록 수정하고, 좁은 화면에서도 가로 스크롤로 버티게 보정했다.

## Why (원인/배경)
- 오른쪽 보조 영역 높이가 부족해지면서 `결과 단계` 패널의 마지막 단계가 잘 보이지 않았고, 상단 네비에는 중복된 링크/유틸리티가 남아 공간 효율이 떨어졌다.
- 사용 흐름상 더 중요한 것은 `현재 섹션 이동`과 `결과 단계 즉시 전환`이라, 이 둘을 같은 스티키 바에서 처리하는 편이 밀도와 접근성이 더 좋다.

## How verified (검증 방법/체크리스트)
- [ ] 브라우저 수동 확인
- [ ] `node --check app/web_assets/app_overrides.js`
- [ ] `python -m py_compile app/web.py`
- [ ] `pytest -q`

## Issues & Fix (문제-원인-해결)
- 문제: 오른쪽 `결과 단계` 패널은 세로 공간 부족으로 잘리는 구간이 있었고, 상단 스티키 네비는 중복 버튼 때문에 핵심 전환 UI를 담기엔 비효율적이었다.
- 원인: 결과 단계는 오른쪽 컬럼에, 유틸리티 버튼은 상단 네비와 hero 액션에 동시에 있어 화면 자원이 분산돼 있었다.
- 해결: 상단 네비에서 중복 항목을 제거하고 결과 단계 5개를 이 자리에 옮겨, 스티키 바 하나에서 섹션 이동과 결과 전환을 모두 처리하게 만들었다.

## Next (다음 작업)
- 브라우저에서 결과 단계 5개가 마지막 `제목`까지 잘 보이는지와 active 상태가 자연스러운지 확인하기
- 결과 작업대 내부 렌더링을 다음 분리 단위로 더 쪼개기

---

## Date
- 2026-03-24 11:13 (KST)

## What changed (변경점)
- `app/web.py`에서 `진행 현황`과 `결과 단계`를 `workspace-sidebar`로 묶어 오른쪽 보조 영역이 한 컬럼처럼 동작하도록 바꿨다.
- `app/web_assets/app.css`에서 데스크톱에서는 `workspace-sidebar` 전체가 sticky 되고, 모바일/좁은 화면에서는 일반 문서 흐름으로 내려오도록 레이아웃 규칙을 조정했다.
- asset version을 다시 올려 이전 레이아웃 캐시가 남지 않게 했다.

## Why (원인/배경)
- `결과 단계`를 진행현황 아래에 고정한 뒤, 두 패널이 각자 따로 배치돼 스크롤 중 진행현황이 결과 단계 아래로 숨어 보이는 구간이 생겼다.
- 사용감 기준으로는 두 패널이 따로 움직이는 것보다 “오른쪽 보조 패널 한 덩어리”처럼 같이 따라오는 편이 훨씬 자연스럽다.

## How verified (검증 방법/체크리스트)
- [ ] 브라우저 수동 확인
- [ ] `python -m py_compile app/web.py`
- [ ] `pytest -q tests/test_web_routes.py`
- [ ] `git diff --check`

## Issues & Fix (문제-원인-해결)
- 문제: 진행현황은 sticky 흐름인데 결과 단계는 별도 배치라, 스크롤 위치에 따라 둘의 관계가 어색해지고 진행현황이 가려지는 것처럼 보였다.
- 원인: 오른쪽 보조 UI가 `summary-panel`과 `insights-panel` 두 개의 독립 블록으로 배치돼 있어 공통 sticky 컨테이너가 없었다.
- 해결: 두 패널을 하나의 `workspace-sidebar`로 묶고 데스크톱에서만 컬럼 전체를 sticky 처리해 함께 이동하도록 바꿨다.

## Next (다음 작업)
- 실제 브라우저에서 긴 스크롤 구간과 좁은 화면 전환 시 보조 컬럼 움직임 확인하기
- 결과 작업대 내부 분리 작업을 이어가면서 오른쪽 보조 패널 정보 밀도도 추가 조정하기

---

## Date
- 2026-03-24 11:02 (KST)

## What changed (변경점)
- 결과 전환용 `1~5단계` 탭을 결과 작업대 상단에서 제거하고, 오른쪽 `진행현황` 아래의 고정 패널(`resultStageDockPanel`)로 옮겼다.
- `app/web_assets/app_overrides.js`에서 단계 도크를 항상 5개 항목으로 렌더링하도록 바꾸고, 아직 준비되지 않은 단계는 비활성 상태로 보여주게 정리했다.
- `app/web_assets/app_workflow_utils.js`에 단계 도크 클릭 이벤트를 연결해 데스크톱에서는 바로 전환되고, 좁은 화면에서는 결과 섹션으로 자연스럽게 이동하도록 맞췄다.

## Why (원인/배경)
- 기존 구조는 결과가 쌓일수록 `수집/확장/분석/선별/제목` 탭이 작업대 상단에 늘어나 시각적으로 흔들렸고, 상단으로 다시 올라가야 다음 결과를 볼 수 있어 흐름이 자주 끊겼다.
- 특히 사용자가 분석 중에 제목 결과를 보거나, 제목 결과에서 다시 선별 보드로 돌아갈 때 전환 컨트롤이 작업면 상단에만 있는 점이 불편했다.

## How verified (검증 방법/체크리스트)
- [ ] 브라우저 수동 확인
- [ ] `node --check app/web_assets/app_workflow_utils.js`
- [ ] `node --check app/web_assets/app_overrides.js`
- [ ] `python -m py_compile app/web.py`
- [ ] `pytest -q`

## Issues & Fix (문제-원인-해결)
- 문제: 결과 전환 탭이 단계별로 점점 늘어나는 구조라 위치가 불안정했고, 작업대 상단 의존도가 높아 전환 동선이 길었다.
- 원인: 전환 UI가 결과 렌더링 내부에 붙어 있어 결과 개수와 함께 커지고, 진행현황과 분리돼 있어 “지금 어디를 보고 있는지”를 한 곳에서 잡기 어려웠다.
- 해결: 고정 5단계 도크를 진행현황 아래로 분리하고, 활성/비활성 상태만 갱신하도록 바꿔 전환 위치를 항상 같은 자리로 고정했다.

## Next (다음 작업)
- 브라우저에서 데스크톱/좁은 화면 기준으로 단계 도크 클릭 후 실제 전환 흐름 확인하기
- 결과 작업대 내부 렌더링(`selection rail / title result`)을 다음 분리 단위로 더 쪼개기

---

## Date
- 2026-03-24 10:41 (KST)

## What changed (변경점)
- `app/web_assets/app_workflow_utils.js`에 섹션 네비 상태 동기화 로직을 추가해 상단 바와 `workspace-nav`가 현재 스크롤 위치에 맞춰 활성 상태를 자동으로 반영하도록 정리했다.
- `app/web_assets/app.css`에서 상단 링크/워크스페이스 네비의 active 스타일과 `scroll-padding-top`, 모바일 상단 바 가로 스크롤 처리를 보강해 섹션 점프 동작이 더 안정적으로 보이게 맞췄다.
- `app/web.py`의 asset version을 갱신해 브라우저가 이전 CSS/JS 캐시를 계속 쓰지 않게 했다.

## Why (원인/배경)
- 샘플 방향으로 앱형 상단 바와 스티키 섹션 네비를 넣은 뒤에도, 실제 사용감은 “현재 어느 섹션에 있는지”가 자동으로 잡히지 않아 시각 구조와 동작 구조 사이에 약한 단절이 있었다.
- 특히 스크롤 중 활성 상태가 고정되지 않으면 레이아웃은 깔끔해 보여도 탐색 감각은 덜 정리된 것처럼 느껴질 수 있어, 구조 변경보다 상태 동기화를 우선 보완하는 편이 안전했다.

## How verified (검증 방법/체크리스트)
- [ ] 브라우저 수동 확인
- [ ] `node --check app/web_assets/app_workflow_utils.js`
- [ ] `python -m py_compile app/web.py`
- [ ] `pytest -q tests/test_web_routes.py`

## Issues & Fix (문제-원인-해결)
- 문제: 상단 바/보조 네비를 추가했지만, 스크롤 위치와 활성 링크가 연결되지 않아 앱형 탐색 구조가 반쯤만 완성된 상태였다.
- 원인: anchor와 sticky layout은 있었지만 현재 섹션을 추적하고 active 스타일을 반영하는 클라이언트 상태가 없었다.
- 해결: 섹션 scroll spy 성격의 경량 동기화 로직과 active 스타일을 추가하고, 모바일에서는 상단 바가 잘리지 않도록 가로 스크롤을 허용했다.

## Next (다음 작업)
- 브라우저에서 섹션 이동, active 상태, utility drawer 버튼 활성화가 함께 자연스럽게 보이는지 확인하기
- 결과 작업대(`results board / selection rail / title result`)를 다음 분리 단위로 더 쪼개기

---

## Date
- 2026-03-24 10:23 (KST)

## What changed (변경점)
- `sample/키워드마스터-2026-03-18T12-19-10.html`, `sample/사이트 사용법.html`, `sample/기능 메뉴얼 (1).html`의 앱형 상단 바, 스티키 탭형 탐색, 카드 밀도 패턴을 참고해 메인 대시보드 레이아웃을 재정리했다.
- `app/web.py`에 고정 상단 `app-topbar`, 스티키 `workspace-nav`, 주요 섹션 anchor(`section-progress`, `section-controls`, `section-launcher`, `section-results`)를 추가해 화면 구조를 더 앱형 작업면처럼 읽히게 했다.
- `app/web_assets/app.css`에서 배경/표면 톤을 더 차분한 workspace 계열로 조정하고, 상단 바/보조 네비/섹션 scroll offset/sticky 동작을 추가해 기존 패널 구조를 유지한 채 벤치마크 방향성을 반영했다.

## Why (원인/배경)
- 현재 화면은 기능은 많지만 첫 인상이 `한 화면에 카드가 많은 페이지`에 가까워, 벤치마킹했던 키워드마스터 계열처럼 “어디서 시작하고 어디로 이동하는지”가 한 번에 읽히는 앱형 크롬이 부족했다.
- 특히 샘플 사이트의 강점은 개별 카드보다 `상단 앱 바 + 스티키 섹션 네비 + 카드형 작업면` 조합이라, 이 구조를 현재 워크플로에 맞게 이식하는 편이 방향성에 맞았다.

## How verified (검증 방법/체크리스트)
- [x] `python -m py_compile app/web.py`
- [x] `pytest -q tests/test_web_routes.py`
- [x] `git diff --check`
- [ ] 브라우저 수동 확인

## Issues & Fix (문제-원인-해결)
- 문제: 화면이 기능 중심으로는 충분했지만, 벤치마크 대비 앱형 탐색 구조와 시선 흐름이 약해 대시보드 방향성이 덜 드러났다.
- 원인: 상단 고정 앱 바와 스티키 섹션 네비 없이 hero와 패널만 이어져 있어, 사용자가 스크롤 중 현재 위치와 다음 액션을 잡기 어려웠다.
- 해결: 앱형 상단 바, 섹션 점프 네비, anchor 기반 scroll offset, 더 선명한 workspace 표면 톤을 추가해 기능 흐름을 한 화면에서 더 쉽게 읽히게 만들었다.

## Next (다음 작업)
- 브라우저에서 상단 바/스티키 네비/모바일 가로 스크롤 동작을 실제로 확인하기
- 다음 분리 단계에서 `results board / selection rail / title result` 렌더링을 추가 분해하면서 섹션별 레이아웃을 더 미세 조정하기

---

## Date
- 2026-03-24 10:09 (KST)

## What changed (변경점)
- `app/web_assets/app_workflow_utils.js`를 새로 추가해 utility drawer, 실행 기록, 키워드 보관함, topic seed, queue, busy-button/중단 제어 로직을 `app_overrides.js`에서 분리했다.
- `app/web_assets/app_overrides.js`는 롱테일 옵션, 선별/보드 렌더링, 결과 액션 중심으로 줄였고, `app/web.py`에서 새 자산을 `app.js -> app_workflow_utils.js -> app_overrides.js` 순서로 로드하도록 연결했다.
- asset version을 갱신해 브라우저 캐시에 이전 단일 번들 스크립트가 남지 않게 했다.

## Why (원인/배경)
- 프런트엔드가 `app.js` 1만 줄대, `app_overrides.js` 4천 줄대까지 커져 보조 기능과 핵심 결과 렌더링이 한 파일에 뒤섞여 있었고, 다음 변경부터 회귀 범위를 읽기 어려운 상태였다.
- 특히 utility drawer와 실행 기록/보관함/queue는 결과 보드와 결합도가 상대적으로 낮아, 첫 분리 대상으로 떼어내는 편이 가장 안전했다.

## How verified (검증 방법/체크리스트)
- [x] `node --check app/web_assets/app_workflow_utils.js`
- [x] `node --check app/web_assets/app_overrides.js`
- [x] `python -m py_compile app/web.py`
- [x] `pytest -q tests/test_web_routes.py`
- [ ] 브라우저 수동 확인

## Issues & Fix (문제-원인-해결)
- 문제: 실행 기록/보관함/queue/주제 시드 같은 보조 워크플로와 선별/결과 보드 렌더링이 같은 파일에 섞여 있어 수정 범위를 좁히기 어려웠다.
- 원인: 기능 추가를 빠르게 이어 붙이는 과정에서 `app_overrides.js`가 utility 계층과 결과 계층을 함께 흡수했다.
- 해결: utility 계층을 별도 자산으로 분리하고, 기존 override 파일은 선택/롱테일/결과 렌더링 중심으로 남겨 로딩 순서와 책임 경계를 나눴다.

## Next (다음 작업)
- 브라우저에서 utility drawer, queue, 보관함, topic seed, 결과 보드 액션을 한 번씩 수동 확인하기
- 다음 분리 단계로 `results board / selection rail / title result` 렌더링 묶음을 추가 분해하기

---

## Date
- 2026-03-24 09:29 (KST)

## What changed (변경점)
- `.dockerignore`에 `.local/`, `Status/`, `output/`, `.tmp*/`, `.tmp_*`, `*.credentials.json`을 추가해 Docker build context에서 로컬 시크릿/산출물이 빠지도록 정리했다.
- `README.md` 로컬 시크릿/데이터 안내를 보강해 git ignore뿐 아니라 Docker build context 차단까지 현재 정책을 명시했다.

## Why (원인/배경)
- `.gitignore`만으로는 로컬 시크릿이 git에는 안 올라가도 `docker build` 시 build context로 전송될 수 있어, 시크릿/로컬 데이터 정리 트랙이 완전히 닫히지 않았다.
- 특히 루트 레거시 credential JSON과 `.local` 세션/산출물은 이미지에 복사되지 않더라도 빌드 전송 단계에서 불필요한 노출면이 남아 있었다.

## How verified (검증 방법/체크리스트)
- [x] `git diff --check`
- [x] `Get-Content .dockerignore`
- [x] `Get-Content README.md`
- [ ] Docker build 실제 실행
- [ ] 회귀(기존 기능) 이상 없음

## Issues & Fix (문제-원인-해결)
- 문제: 로컬 시크릿/산출물이 git ignore에서는 막히지만 Docker build context에서는 계속 포함될 수 있었다.
- 원인: `.dockerignore`가 `.gitignore`와 달리 `.local`, `Status`, `output`, legacy credential JSON 패턴을 제외하지 않았다.
- 해결: `.dockerignore`를 로컬 데이터 정책과 맞추고 README에 build context 차단 사실을 함께 명시했다.

## Next (다음 작업)
- 실제 Docker/Compose 실행이 필요한 환경에서 build context와 런타임 동작을 한 번 더 확인하기
- 필요하면 `.env`/시크릿 샘플 export 절차를 README에 더 구체화하기

---

## Date
- 2026-03-24 02:29 (KST)

## What changed (변경점)
- `app/title/exporter.py`, `tests/test_title.py`, `tests/test_pipeline.py`에서 제목 결과 `output/` 기본 export를 `csv` 단일 파일로 바꾸고, `xlsx/md`는 명시 요청 시에만 생성되도록 정리했다.
- `app/web_assets/app.js`에서 제목 자동 저장이 일어나면 2주 중복 판정용 최근 작업 이력도 함께 기록되도록 연결해, `output` 저장과 중복 차단 흐름이 어긋나지 않게 맞췄다.
- `app/web_assets/app_overrides.js`, `app/title/targets.py`에서 `전체` 조합 선별이 실제로는 자동 선별로 내려가던 버그를 고치고, 제목 기본 타깃 모드도 `단일 + 롱테일 V1`로 통일했다.

## Why (원인/배경)
- 실제 사용 흐름은 `output` 폴더 산출물을 바로 자동 블로그 작성기로 넘기는 쪽인데, 기본 export가 다중 포맷이라 산출물이 과했고 2주 중복 이력도 브라우저 CSV 수동 다운로드에만 묶여 있었다.
- 또 `A~D / 1~4 전체 선택`이 UI상으로는 전체 조합처럼 보였지만 실행 시에는 필터 없음으로 처리돼, 오사카 같은 대형 시드에서도 자동 선별 8건만 남는 문제가 있었다.

## How verified (검증 방법/체크리스트)
- [x] `node --check app/web_assets/app.js`
- [x] `node --check app/web_assets/app_overrides.js`
- [x] `pytest -q tests/test_title.py tests/test_pipeline.py`
- [x] `pytest -q` (`146 passed`)
- [x] `Status/수익형 키워드 발굴&제목 생성기-2026-03-23T17-19-46.html`에서 오사카 실행 로그 확인

## Issues & Fix (문제-원인-해결)
- 문제: `전체` 조합을 눌러도 실제로는 자동 선별이 돌아가 글감 후보가 과하게 줄고, `output` 자동 저장만 쓰면 2주 중복 판정이 느슨하게 보였다.
- 원인: 프런트가 `전체 선택`을 명시 필터가 아닌 “선택 안 함”처럼 취급했고, 최근 작업 이력 기록도 `CSV 다운로드 버튼` 경로에만 연결돼 있었다.
- 해결: `전체 선택`을 실제 `combo_filter(all)`로 보내도록 수정하고, 제목 자동 저장 시에도 최근 작업 이력을 적재하도록 연결했으며, 제목 기본 모드는 `단일 + V1`로 맞췄다.

## Next (다음 작업)
- 브라우저에서 오사카 같은 대형 시드로 `전체 조합` 실행 후 실제 선별/제목 건수가 기대치대로 늘어나는지 수동 확인하기
- 필요하면 `글감 탐색 전용` 선별 프리셋을 별도로 추가해 자동 선별과 전체 조합의 목적 차이를 더 명확히 드러내기

---

## Date
- 2026-03-23 09:30 (KST)

## What changed (변경점)
- `app/analyzer/main.py`, `app/analyzer/naver_searchad.py`, `app/analyzer/naver_open_search.py`에서 실측 분석 수집을 병렬화하고 SearchAd keyword tool 배치/worker 설정을 추가해 분석 대기 시간을 줄였다.
- `app/analyzer/scorer.py`, `app/selector/service.py`, `app/web.py`, `app/web_assets/app_overrides.js`에서 `공략성` 축을 실제 클릭 활동이 반영되는 `노출도` 중심 해석으로 다듬고 관련 설명/UI 문구를 함께 정리했다.
- `app/title/issue_sources.py`, `app/title/exporter.py`, `app/title/ai_client.py`, `app/title/main.py`, `app/api/routes/generate_title.py`, `app/pipeline/service.py`에 `news / reaction / mixed` 이슈 소스 모드와 제목 결과 `csv/xlsx/md` export를 추가했고, `output/`도 git ignore에 포함했다.

## Why (원인/배경)
- 분석 단계는 SearchAd keyword tool, bid 조회, blog 검색량 조회를 거의 직렬로 수행하고 있어 키워드 수가 늘면 체감 대기 시간이 급격히 길어졌다.
- 제목 단계는 실시간 이슈를 참고하더라도 어떤 소스를 얼마나 반영했는지 제어가 어려웠고, 생성 결과를 바로 재사용할 수 있는 산출물도 남지 않았다.

## How verified (검증 방법/체크리스트)
- [x] `pytest -q tests/test_analyzer.py tests/test_naver_open_search.py tests/test_naver_searchad.py tests/test_title.py tests/test_pipeline.py tests/test_web_routes.py`
- [x] `pytest -q` (`139 passed`)
- [x] 회귀(기존 기능) 이상 없음

## Issues & Fix (문제-원인-해결)
- 문제: 분석 실측 수집이 느리고 `공략성` 축이 실제 클릭 신호를 충분히 반영하지 못했다.
- 원인: 측정 소스 호출이 직렬 위주였고, `공략성` 가중치도 opportunity/희소성 쪽에 상대적으로 치우쳐 있었다.
- 해결: 실측 수집을 병렬화하고 SearchAd 청크 실패 시 분할 재시도를 넣었으며, 공격 축에는 click yield / exposure signal을 추가해 `노출도` 해석으로 정리했다.

## Next (다음 작업)
- 실제 로컬 API key와 네이버 응답 환경에서 병렬 수집 체감 시간과 rate limit 안정성을 한 번 더 수동 확인하기
- 제목 `issue_source_mode`와 export artifact를 메인 UI에서 더 잘 드러내고, 필요하면 결과물 파일명/저장 위치 옵션을 세분화하기

---

## Date
- 2026-03-22 10:07 (KST)

## What changed (변경점)
- `.gitignore`, `app/analyzer/naver_searchad.py`, `app/analyzer/naver_open_search.py`를 손봐 시크릿 기본 경로를 `.local/credentials/...`로 옮기고, 루트 `*.credentials.json`은 레거시 fallback으로만 남겼다.
- `tests/test_naver_searchad.py`, `tests/test_naver_open_search.py`에 `local 우선 / legacy fallback` 회귀 테스트를 추가했고, README와 handoff 문서도 새 로컬 시크릿 경로 기준으로 갱신했다.
- 저장 세션/Status/임시 로그 같은 로컬 산출물은 git ignore 대상으로 정리해 작업 트리와 시크릿이 계속 섞이지 않게 했다.

## Why (원인/배경)
- 현재 저장소에는 루트 credential JSON, `.local` 브라우저 프로필, `Status` 산출물 같은 로컬 전용 데이터가 함께 추적되고 있어 시크릿 노출과 작업 트리 오염 위험이 컸다.
- 특히 분석 credential 파일은 코드 기본 경로가 루트를 보고 있어, 새 환경에서도 시크릿을 저장소 바로 아래에 두기 쉬운 구조였다.

## How verified (검증 방법/체크리스트)
- [ ] 로컬 재실행 완료
- [ ] 출력 파일 생성 확인
- [x] `pytest -q tests/test_naver_searchad.py tests/test_naver_open_search.py`
- [ ] 회귀(기존 기능) 이상 없음

## Issues & Fix (문제-원인-해결)
- 문제: 로컬 시크릿/세션/산출물이 저장소 루트와 git 추적 대상에 섞여 있었다.
- 원인: credential 기본 파일명이 루트 경로였고, `.local`, `Status`, `.tmp_*` 같은 런타임 산출물에 대한 ignore 규칙이 약했다.
- 해결: 기본 credential 경로를 `.local/credentials/`로 이동하고 레거시 fallback만 유지했으며, git ignore와 문서를 함께 정리했다.

## Next (다음 작업)
- 이미 추적 중인 `.local`, `Status`, 루트 credential 파일을 git index에서 완전히 걷어내기
- 필요하면 `.local/.env` 또는 시크릿 export/import 규칙까지 한 번 더 정리하기

---

## Date
- 2026-03-22 01:25 (KST)

## What changed (변경점)
- `app/title/ai_client.py`, `app/title/presets.py`, `app/web.py`, `app/web_assets/app.js`에 `Vertex AI` 제목 provider를 추가했다. 현재 구현은 `Vertex AI Express Mode API key` 기준이다.
- `app/selector/longtail.py`, `app/selector/service.py`, `app/title/targets.py`, `app/web_assets/app_overrides.js`, `app/web_assets/app.css`에서 롱테일 `가이드 / 체크리스트`를 기본 강제 후보에서 빼고 선택형 의도 토큰으로 바꿨다.
- 관련 테스트를 갱신하고 `tests/test_selector.py`, `tests/test_title.py`, `tests/test_pipeline.py`, `tests/test_web_routes.py` 회귀를 다시 확인했다.

## Why (원인/배경)
- Gemini Developer API free tier는 짧은 시간 재생성 시 429에 자주 걸리고, Google Cloud 크레딧을 활용하려면 Vertex AI 경로가 필요했다.
- 롱테일 조합에서 `가이드`, `체크리스트`가 너무 자주 섞여 템플릿처럼 보였고, 실제 의도형 후보와 구분이 어려웠다.

## How verified (검증 방법/체크리스트)
- [x] `node --check app/web_assets/app.js`
- [x] `node --check app/web_assets/app_overrides.js`
- [x] `pytest -q tests/test_selector.py tests/test_title.py tests/test_web_routes.py tests/test_pipeline.py`
- [x] `pytest -q` (`130 passed`)
- [ ] 브라우저에서 Vertex AI key로 실제 제목 생성 수동 확인

## Issues & Fix (문제-원인-해결)
- 문제: Gemini free tier 429가 잦고, 제목 생성 provider 선택지가 Google AI Studio API에 묶여 있었다.
- 원인: 백엔드가 `generativelanguage.googleapis.com`만 직접 호출했고, Vertex AI 경로는 없었다.
- 해결: `aiplatform.googleapis.com` 기반 Vertex AI Express Mode 호출을 추가하고, UI provider 선택과 프리셋/모델 목록을 함께 연결했다.

## Next (다음 작업)
- Vertex AI Express Mode API key로 실제 제목 생성과 fallback 동작을 수동 확인하기
- 필요하면 다음 단계로 Full Vertex AI(service account) 경로를 별도 provider로 분리하기

## Date
- 2026-03-21 21:30 (KST)

## What changed (변경점)
- `app/scheduler/service.py`, `app/api/routes/scheduler.py`, `app/main.py`에 작업 Queue / 일일 카테고리 루틴 / 백그라운드 순차 실행기를 추가했다.
- 시드 키워드 배치를 Queue에 넣으면 기존 `pipeline`을 항목별로 순차 실행하고, 결과를 `Status/queue_exports/...xlsx`로 저장하도록 연결했다.
- `tests/test_scheduler_service.py`, `tests/test_scheduler_api.py`를 추가하고, 전체 테스트를 다시 돌려 회귀를 확인했다.

## Why (원인/배경)
- 예약모드는 `expander` 내부 큐가 아니라 상위 작업 오케스트레이터로 분리해야 시드 배치, 카테고리 루틴, 파일 출력, 런타임 가드를 한곳에서 일관되게 제어할 수 있다.

## How verified (검증 방법/체크리스트)
- [x] `python -m py_compile app/scheduler/service.py app/api/routes/scheduler.py app/main.py`
- [x] `pytest -q tests/test_scheduler_service.py tests/test_scheduler_api.py`
- [x] `pytest -q`
- [x] 회귀(기존 기능) 이상 없음

## Issues & Fix (문제-원인-해결)
- 문제: 시드 키워드를 여러 개 예약 실행하거나, 카테고리 루틴을 매일 자동 생성하는 상위 작업 계층이 없었다.
- 원인: 기존 구조는 개별 API 실행과 `expander` 내부 확장 큐만 있었고, 배치 작업 상태 저장과 결과 파일 출력 계층이 없었다.
- 해결: JSON 상태 저장 기반 스케줄러 서비스와 Queue API를 추가하고, 항목별 파이프라인 결과를 xlsx로 묶어 저장하도록 했다.

## Next (다음 작업)
- Queue / 루틴 UI를 메인 화면에 붙이고 상태 조회, 다운로드, 취소를 브라우저에서 직접 다루게 만들기
- 예약 루틴이 실제 운영 설정과 충돌할 때 재시도/재개 정책을 더 정교화하기

---

## Date
- 2026-03-21 10:02 (KST)

## What changed (변경점)
- `app/selector/cannibalization.py`, `app/selector/service.py`, `app/selector/longtail.py`, `app/pipeline/service.py`에 카니벌라이제이션 리포트를 추가해 선별 키워드와 롱테일 후보의 토픽/의도 충돌을 자동 집계하도록 연결했다.
- `app/selector/serp_summary.py`, `app/api/routes/selector.py`, `app/web_assets/app_overrides.js`, `app/web_assets/app.css`에 네이버 SERP 경쟁 요약 기능을 추가해 상위 제목, 반복 용어, 도메인 편중을 버튼 한 번으로 확인할 수 있게 했다.
- 선별 결과 카드에 `카니벌라이제이션 검사`와 `SERP 경쟁 요약` 보드를 붙였고, 롱테일 재검증 시 카니벌라이제이션은 즉시 갱신하고 SERP 요약은 stale 방지를 위해 다시 실행하도록 정리했다.

## Why (원인/배경)
- 롱테일과 제목 모드까지 붙은 뒤에는 “이걸 따로 글로 써도 되는지”와 “실제 검색결과가 이미 어떻게 굳어 있는지”를 툴 안에서 바로 판단할 수 있어야 다음 실험이 빨라진다.

## How verified (검증 방법/체크리스트)
- [x] `node --check app/web_assets/app_overrides.js`
- [x] `python -m py_compile app/pipeline/service.py app/selector/cannibalization.py app/selector/serp_summary.py app/api/routes/selector.py app/web.py`
- [x] `python -m pytest -q` (`101 passed`)
- [x] 회귀(기존 기능) 이상 없음

## Issues & Fix (문제-원인-해결)
- 문제: 선별 결과에서 비슷한 키워드를 따로 써야 할지 합쳐야 할지 판단 근거가 부족했고, 상위 노출 제목 패턴도 수동 검색 없이 확인할 수 없었다.
- 원인: selector가 콘텐츠 맵과 롱테일까지만 보여주고, 중복 위험 판단과 실시간 SERP 요약 레이어는 없었다.
- 해결: 토픽/의도 기반 카니벌라이제이션 리포트와 온디맨드 SERP 경쟁 요약 API/UI를 추가해 선별 단계에서 바로 병합/분리 판단과 경쟁 패턴 확인이 가능해졌다.

## Next (다음 작업)
- 카니벌라이제이션 결과를 제목/발행 워크플로우에 더 직접 연결할지 검토
- 예약 기반 자동 순차 작업은 별도 기능으로 후순위 설계

---

## Date
- 2026-03-21 17:20 (KST)

## What changed (변경점)
- `app/web.py`, `app/web_assets/app.js`, `app/web_assets/app.css`, `app/web_assets/app_overrides.js`에 `운영 설정` 드로어를 추가하고 `일일 10회 이하 / 상시 슬로우 / 직접 설정` 모드를 저장/적용할 수 있게 했다.
- `app/core/runtime_settings.py`, `app/api/routes/settings.py`, `app/expander/utils/throttle.py`에 런타임 운영 가드를 추가해 Naver 요청 간격, 일일 작업 상한, 일일 Naver 요청 상한, 연속 실행 보호, 401/403 자동 잠금을 서버에서 직접 관리하게 했다.
- 현재까지의 변경과 제목 개선 방향, 다른 PC에서 이어서 작업하는 방법을 `HANDOFF_2026-03-21.md`에 상세 정리했다.

## Why (원인/배경)
- 이제 초기 개발 단계가 지나서 실행 옵션이 메인 화면에 계속 쌓이는 구조보다, 장시간 실행과 예약모드 전환을 대비한 분리형 운영 설정이 필요했다.
- 제목 생성은 검색 상위 제목을 참고하지만 아직 `뉴스 본문/커뮤니티 반응` 수준은 아니라, 다음 작업 우선순위를 문서로 명확히 남겨둘 필요가 있었다.

## How verified (검증 방법/체크리스트)
- [x] `pytest tests/test_web_routes.py tests/test_runtime_operation_settings.py tests/test_runtime_settings_api.py tests/test_expander_throttle.py tests/test_naver_request_slow_mode.py tests/test_stage_entrypoints.py`
- [x] `node --check app/web_assets/app.js`
- [x] `node --check app/web_assets/app_overrides.js`
- [x] `python -m py_compile` 관련 파일 통과

## Issues & Fix (문제-원인-해결)
- 문제: 장시간 실행/예약모드 대비 운영 안전장치와 세팅 분리 UI가 없고, 다른 PC에서 이어서 작업할 때 최근 변경 맥락이 끊겼다.
- 원인: 요청 간격은 env 변수에만 묶여 있었고, 프런트 설정도 로컬 브라우저 저장 중심이라 인수인계 문서가 없으면 이어받기 어렵다.
- 해결: 런타임 운영 설정 API와 세팅 드로어를 추가하고, 별도 핸드오프 문서에 최근 작업 내역과 제목 개선 조언을 정리했다.

## Next (다음 작업)
- 예약모드가 런타임 운영 설정을 그대로 읽도록 연결
- 제목 생성은 `뉴스형 / 반응형 / 혼합형` 이슈 소스 분리부터 강화

---

## Date
- 2026-03-20 17:22 (KST)

## What changed (변경점)
- `app/web.py`, `app/web_assets/app.css`, `app/web_assets/app.js`, `app/web_assets/app_overrides.js`에서 실행/시작점 UI를 다시 정리해 `확장/분석/제목 생성 시작점`을 왼쪽 독립 패널로 분리하고, 상단 실행 버튼은 새 세션 시작 의미로 고정했다.
- 확장 옵션의 `연관확장 / 자동완성 / 원문포함`을 체크박스 대신 색상형 토글 칩으로 바꿔 한 줄로 정리했고, 제목 결과 카드에는 `버전별 필터 + 점수/키워드 정렬` 컨트롤을 추가했다.
- 제목 생성/새 세션 흐름에서 `선택한 조합(수익성 · 공략성)`이 빈 값으로 깨지던 프런트 필터 판정을 고쳐, 빈 배열을 명시적 조합 선택으로 오인하지 않게 수정했다.

## Why (원인/배경)
- `Status` 기준으로 시작점 카드가 메인 패널 안에서 길게 늘어져 보여 독립 작업대처럼 인식되지 않았고, 확장 옵션도 체크 UI 때문에 가로 공간을 과하게 차지했다.
- 또 제목 단계 재실행 중 빈 조합 오류가 나면서, 실제 선택 프로필이 없는 상태도 조합 필터 오류로 잘못 처리되는 문제가 드러났다.

## How verified (검증 방법/체크리스트)
- [x] `node --check app/web_assets/app.js`
- [x] `node --check app/web_assets/app_overrides.js`
- [x] `python -m py_compile app/web.py`
- [x] Playwright로 레이아웃 좌표, 제목 정렬/필터 동작 확인

## Issues & Fix (문제-원인-해결)
- 문제: 시작점 UI가 독립 패널처럼 보이지 않았고, 제목 재실행 시 빈 축 필터가 조합 오류로 노출됐다.
- 원인: 시작점 카드가 `control-panel` 내부 흐름에 묶여 있었고, `hasExplicitAxisFilterSelection()`가 빈 배열도 명시적 필터처럼 취급했다.
- 해결: launcher를 별도 panel/column으로 분리하고, 옵션 칩 UI를 압축했으며, 제목 결과 정렬 UI를 추가하고 빈 배열 필터는 기본 상태로 처리하도록 수정했다.

## Next (다음 작업)
- 실제 키워드 케이스로 제목 정렬/필터 UX를 더 다듬고 필요한 기본 정렬값을 고정
- `시크릿 / 로컬 데이터 정리`와 함께 상태 저장/session restore 범위를 한 번 더 점검

---

## Date
- 2026-03-20 13:20 (KST)

## What changed (변경점)
- `app/title/targets.py`, `app/title/main.py`, `app/pipeline/service.py`에 제목 target builder를 추가해 `single / 롱테일 V1 / V2 / V3` 모드별 제목 대상을 서버에서 조합하도록 바꿨다.
- `app/web.py`, `app/web_assets/app.js`, `app/web_assets/app_overrides.js`에 제목 키워드 모드 선택 UI, 결과 요약/CSV 메타, target 단위 재생성 흐름을 연결했다.
- `app/title/quality.py`, `app/title/title_generator.py`에서 품질 검수와 AI 자동 재시도 뒤에도 target 메타데이터가 유지되도록 보강했고, `tests/test_title.py`, `tests/test_pipeline.py`에 관련 테스트를 추가했다.

## Why (원인/배경)
- 롱테일 후보는 이미 selector에서 만들 수 있었지만, 제목 단계는 여전히 선별 단일 키워드 기준이라 실제 `단일 / V1 / V2 / V3` 발행 흐름을 실험할 수 없었다.

## How verified (검증 방법/체크리스트)
- [ ] 로컬 재실행 완료
- [ ] 출력 파일 생성 확인
- [ ] 핵심 케이스 N건 수동 확인
- [x] 회귀(기존 기능) 이상 없음

## Issues & Fix (문제-원인-해결)
- 문제: 제목 생성이 `selected_keywords` 중심 계약에 묶여 있어 롱테일 모드를 켜도 결과 메타와 재생성 단위가 안정적으로 유지되지 않았다.
- 원인: title stage가 target 개념 없이 키워드 문자열만 넘겼고, `quality.py`가 품질 enrich 시 메타데이터를 버렸으며, 프런트 재생성도 keyword 단위로만 동작했다.
- 해결: `keyword_modes`와 `title_targets` 계약을 추가하고, 품질 검수/자동 재시도/CSV/재생성을 모두 target 단위로 맞춰 `single / V1 / V2 / V3` 병렬 생성을 일관되게 연결했다.

## Next (다음 작업)
- 브라우저에서 `single / V1 / V2 / V3` 조합별 수동 클릭 검증
- 다음 우선순위인 `시크릿 / 로컬 데이터 정리` 진행

---

## Date
- 2026-03-20 11:45 (KST)

## What changed (변경점)
- `app/title/presets.py`, `app/title/ai_client.py`, `app/title/title_generator.py`에 제목 프리셋 레지스트리와 preset 기반 옵션 해석을 추가해, provider/model/temperature/prompt guidance를 서버에서 한 번에 해석하도록 정리했다.
- `app/web.py`, `app/web_assets/app.js`, `app/web_assets/app_overrides.js`에 `프롬프트 / 모델 프리셋` 선택 UI와 설명 문구, 수동 변경 시 custom 전환 로직, 결과 요약 표시를 붙였다.
- `tests/test_title.py`, `tests/test_pipeline.py`에 preset 기본값/메타데이터/파이프라인 전달 테스트를 추가하고 회귀 테스트를 다시 돌렸다.

## Why (원인/배경)
- AI 제목 설정은 provider/model/temperature/custom prompt가 각각 흩어져 있어, 실제 운영용 조합을 저장하거나 재현하기 어려웠다.

## How verified (검증 방법/체크리스트)
- [ ] 로컬 재실행 완료
- [ ] 출력 파일 생성 확인
- [x] 핵심 케이스 3건 수동 확인
- [x] 회귀(기존 기능) 이상 없음

## Issues & Fix (문제-원인-해결)
- 문제: AI 제목 생성 설정이 개별 입력만 있어 “검증된 조합”을 빠르게 다시 쓰거나 결과 메타에서 추적하기 어려웠다.
- 원인: `title_options`가 raw provider/model/system_prompt만 받고, preset 개념과 서버 해석 계층이 없었다.
- 해결: preset 레지스트리를 추가해 프런트와 백엔드가 같은 preset key를 공유하게 하고, generation meta에도 적용된 preset/model 정보를 함께 남기도록 바꿨다.

## Next (다음 작업)
- `시크릿 / 로컬 데이터 정리` 우선순위로 이동
- 롱테일 검증 결과의 CSV / 제목 생성 연동 여부를 계속 검토

---

## Date
- 2026-03-20 02:32 (KST)

## What changed (변경점)
- `selector`에 롱테일 조합 엔진과 `/verify-longtail` 검증 엔드포인트를 추가해, 선별 결과에서 바로 롱테일 후보를 만들고 다시 분석할 수 있게 했다.
- 선택 결과 카드에 `롱테일 조합` 보드를 추가하고, 예상 조합과 검증 결과를 분리해서 보여주며 `롱테일 검증 실행` 버튼으로 재분석하도록 연결했다.
- `tests/test_selector.py`, `tests/test_pipeline.py`에 롱테일 제안/검증/엔드포인트 테스트를 보강하고 관련 회귀 테스트를 다시 돌렸다.

## Why (원인/배경)
- 기존 콘텐츠 맵은 어떤 키워드를 묶을지까지만 보여줬고, 실제로 중심 키워드와 서브 의도를 합쳐 쓸만한 롱테일을 만드는 단계는 사용자가 수동으로 해야 했다.

## How verified (검증 방법/체크리스트)
- [ ] 로컬 재실행 완료
- [ ] 출력 파일 생성 확인
- [x] 핵심 케이스 3건 수동 확인
- [x] 회귀(기존 기능) 이상 없음

## Issues & Fix (문제-원인-해결)
- 문제: 수익성 좋은 중심 키워드가 있어도, 이를 실제 글 주제로 확장할 롱테일 후보와 검증 흐름이 툴 안에 없었다.
- 원인: `selector`가 선별과 콘텐츠 맵까지만 반환하고, 조합 후보 생성/재분석을 위한 별도 API와 UI가 없었다.
- 해결: 클러스터 기반 롱테일 제안 모듈을 추가하고, 예상 조합 등급과 검증 결과를 함께 보여주는 검증 보드를 붙였다.

## Next (다음 작업)
- 롱테일 검증 결과를 CSV나 제목 생성 단계와 연동할지 검토
- 다음 우선순위인 `프롬프트 / 모델 프리셋` 작업으로 이동

---

## Date
- 2026-03-20 02:12 (KST)

## What changed (변경점)
- 최신 `Status` 결과를 확인해 같은 키워드 묶음이 동일한 4개 골격으로 반복되는 문제를 재현하고, `title/templates.py`의 그룹 선택 순서를 다시 조정했다.
- 의도형 템플릿 그룹은 앞에 고정하고, 일반형 그룹만 키워드별 seed로 섞어 같은 묶음에서도 서로 다른 제목 조합이 나오게 했다.
- `tests/test_title.py`는 유지하면서 전체 테스트를 다시 돌려 제목 분기 변경의 회귀가 없는지 확인했다.

## Why (원인/배경)
- `샤넬 카드지갑 / 셀린느 카드지갑 / 미우미우 카드지갑`처럼 비슷한 후보를 동시에 생성하면, 서로 다른 키워드인데도 같은 골격 4개가 그대로 반복돼 템플릿 티가 강하게 났다.

## How verified (검증 방법/체크리스트)
- [ ] 로컬 재실행 완료
- [ ] 출력 파일 생성 확인
- [x] 핵심 케이스 3건 수동 확인
- [x] 회귀(기존 기능) 이상 없음

## Issues & Fix (문제-원인-해결)
- 문제: 한 묶음의 키워드 여러 개가 `조건과 보장 한눈에 / 찾는 사람이 보는 핵심 / 먼저 보는 체크리스트 / 실수 줄이는 포인트` 같은 동일 골격으로 반복됐다.
- 원인: 템플릿 엔진이 의도 분기 후에도 일반형 그룹 선택 순서가 사실상 고정돼 있어, 유사 키워드가 같은 상위 그룹 조합을 계속 탔다.
- 해결: 의도형 그룹은 보존하고, 일반형 그룹만 키워드별로 다른 순서가 되도록 섞어 동일 묶음 반복률을 낮췄다.

## Next (다음 작업)
- 사용자가 새로 생성한 `Status` 결과를 다시 확인해 템플릿 반복률 체감 검증
- 만족스러우면 다음 우선순위인 롱테일 조합 제안 설계로 이동

---

## Date
- 2026-03-20 02:06 (KST)

## What changed (변경점)
- `title/templates.py`를 키워드 맥락 기반 템플릿 엔진으로 다시 바꿔 `후기/예약/프로필/가격/비교/정책/로컬 서비스` 의도를 따로 분기하도록 수정했다.
- 템플릿은 더 이상 카테고리 하나만 보고 고르지 않고, 로컬 토큰·서비스성·프로필성·미디어성까지 함께 봐서 서로 다른 제목 골격을 우선 선택한다.
- `tests/test_title.py`에 의도별 템플릿 결과 테스트를 추가해 `후기 후기` 같은 중복 표현과 generic 회귀를 막았다.

## Why (원인/배경)
- 직전 템플릿 개편 뒤에도 실제 키워드 다수가 `general` 흐름으로 떨어지면서 `핵심 포인트`, `체크 포인트`, `가이드` 같은 비슷한 말투가 반복됐다.

## How verified (검증 방법/체크리스트)
- [ ] 로컬 재실행 완료
- [ ] 출력 파일 생성 확인
- [x] 핵심 케이스 4건 수동 확인
- [x] 회귀(기존 기능) 이상 없음

## Issues & Fix (문제-원인-해결)
- 문제: `평택 밸리왁싱 후기`, `함돈균 교수프로필`, `차량 5부제 요일` 같이 성격이 다른 키워드도 비슷한 generic 템플릿으로 생성됐다.
- 원인: 제목 템플릿이 카테고리/일반 분기 위주였고, `후기/예약/프로필/정책` 같은 검색 의도와 로컬 서비스 문맥을 충분히 반영하지 못했다.
- 해결: 템플릿 컨텍스트를 새로 만들고 의도별 그룹을 우선 배치해, 키워드 맥락에 맞는 제목 골격을 먼저 선택하도록 바꿨다.

## Next (다음 작업)
- 실제 키워드 묶음으로 제목을 다시 생성해 템플릿 반복률 확인
- 만족스러운 수준이면 다음 업그레이드인 롱테일 조합 제안으로 이동

---

## Date
- 2026-03-20 01:57 (KST)

## What changed (변경점)
- `title/templates.py`를 다시 설계해 제목 후보를 그룹형 템플릿으로 나누고, 키워드 해시와 검색 의도에 따라 다른 골격이 선택되도록 바꿨다.
- `title/ai_client.py` 기본 시스템 프롬프트와 사용자 프롬프트에 `문장 골격 반복 금지`, `의도 반영`, `상투 문구 금지` 지시를 추가했다.
- `title/quality.py`는 `완벽 정리`, `갑자기 바뀌었다` 같은 고정형 문구를 품질 패널티로 잡아 자동 재시도가 다시 걸리도록 보강했다.

## Why (원인/배경)
- 실제 `Status` 저장 결과를 보면 템플릿과 AI 결과가 모두 비슷한 상투 문구로 수렴해 제목 품질이 낮고, AI 모드의 장점도 거의 드러나지 않았다.

## How verified (검증 방법/체크리스트)
- [ ] 로컬 재실행 완료
- [ ] 출력 파일 생성 확인
- [x] 핵심 케이스 4건 수동 확인
- [x] 회귀(기존 기능) 이상 없음

## Issues & Fix (문제-원인-해결)
- 문제: `완벽 정리`, `비교 및 선택 기준 정리`, `갑자기 바뀌었다` 같은 문구가 제목 전반에 반복됐다.
- 원인: 템플릿 후보군이 좁았고, AI 기본 프롬프트도 JSON 형식과 개수 제한만 강해서 문장 골격 다양성을 제대로 요구하지 못했다.
- 해결: 템플릿을 의도별/유형별 그룹 선택 구조로 바꾸고, AI 프롬프트와 품질 검수에 반복 억제 규칙을 추가했다.

## Next (다음 작업)
- 새 템플릿으로 실제 키워드 묶음 2~3세트를 다시 생성해 문구 품질 확인
- 필요 시 카테고리 감지 패턴과 롱테일 조합 기능 설계 계속

---

## Date
- 2026-03-20 01:43 (KST)

## What changed (변경점)
- `PROJECT.md`에 현재 업그레이드 큐를 `제목 품질 검수 -> 롱테일 조합 제안 -> 프롬프트/모델 프리셋 -> 시크릿 정리` 순서로 고정했다.
- `title_generator`에 제목 품질 점수, 품질 요약, AI 저품질 제목 자동 재시도 1회를 추가했고, 결과마다 `quality_report`를 붙이도록 바꿨다.
- 웹 제목 카드에 품질 점수/상태/사유를 노출하고 `기준 미달만 다시 생성` 버튼을 추가했다.

## Why (원인/배경)
- 다음 업그레이드 순서를 저장소 안에 남겨두지 않으면 우선순위가 흔들릴 수 있었고, 제목 생성도 “만들기만 하고 품질을 판정하지 않는” 상태라 실전 사용성이 아쉬웠다.

## How verified (검증 방법/체크리스트)
- [ ] 로컬 재실행 완료
- [ ] 출력 파일 생성 확인
- [x] 핵심 케이스 3건 수동 확인
- [x] 회귀(기존 기능) 이상 없음

## Issues & Fix (문제-원인-해결)
- 문제: 제목 생성 결과에 품질 판정이 없어서 어떤 결과를 다시 뽑아야 할지 바로 알기 어려웠다.
- 원인: 제목 생성기는 4개 제목만 반환하고, 키워드 포함 여부/중복도/길이 같은 품질 판단과 재시도 로직이 없었다.
- 해결: 제목 번들별 품질 점수와 사유를 계산하고, AI 모드에서는 기준 미달 키워드만 다시 요청해 더 나은 결과를 선택하도록 보강했다.

## Next (다음 작업)
- 제목 품질 기준을 실제 수동 검토 결과에 맞춰 더 미세 조정
- 롱테일 조합 제안 + 검증 기능 설계 착수

---

## Date
- 2026-03-19 08:55 (KST)

## What changed (변경점)
- `analyzer`를 샘플 상세 화면 기준으로 다시 맞춰 `PC조회 / MO조회 / 총조회 / 블로그 / CPC / 1위입찰` 실측값을 우선 사용하고, 일부 값이 비어 있어도 추정치가 섞이지 않게 정리했다.
- `naver_open_search`는 블로그 수 조회 시 키워드 공백을 붙여서 질의하도록 바꿔 `김길리 메달수 -> 4,659`처럼 샘플과 같은 기준으로 맞췄다.
- `Study/` 문서는 `/guides`와 상세 문서 페이지에서 바로 볼 수 있게 연결하고, 샘플 사이트명 표기는 `본 사이트`로 중립화했다.

## Why (원인/배경)
- `김길리 메달수`, `삼천리자전거 가격`처럼 샘플 사이트와 비교했을 때 블로그 수, 점수, CPC/입찰가 해석이 어긋났고, 사용 가이드도 파일 폴더에서만 확인할 수 있었다.

## How verified (검증 방법/체크리스트)
- [ ] 로컬 재실행 완료
- [ ] 출력 파일 생성 확인
- [x] 핵심 케이스 3건 수동 확인
- [x] 회귀(기존 기능) 이상 없음

## Issues & Fix (문제-원인-해결)
- 문제: 실측 분석이라고 보여도 일부 항목은 추정치가 섞였고, 블로그 수 질의 기준도 샘플 사이트와 달랐다.
- 원인: `scorer`가 실측 누락값을 heuristic으로 메우고 있었고, 블로그 검색 질의가 공백 포함 형태였다.
- 해결: 실측 모드에서는 누락값을 0으로 유지하고, 블로그 수는 공백 정규화 키워드로 조회하도록 바꿨다. 가이드는 사이트 내부 문서 페이지로 재구성했다.

## Next (다음 작업)
- 사용자가 보내는 샘플 검색결과를 더 대조해 점수 구간과 표기 컬럼을 추가 보정
- UI 전반에서 `1위입찰`과 측정 출처 배지를 일관되게 노출

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
