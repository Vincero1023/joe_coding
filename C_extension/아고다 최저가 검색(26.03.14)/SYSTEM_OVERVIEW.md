# Agoda Best 시스템 개요

## 버전

- 현재 문서 기준 버전: `2.0.0`
- 제품명: `Agoda Best`

## 1. 목적

이 확장 프로그램은 Agoda 호텔 상세 페이지를 기준으로 여러 캠페인 링크를 비교해 최저가 후보를 찾고, 이미 예약한 호텔의 가격 변동까지 추적하는 것을 목표로 합니다.

핵심 목표는 세 가지입니다.

- 여러 `cid/tag` 조합을 빠르게 비교하기
- 결과를 별도 탭에 고정해 사용 흐름을 안정화하기
- 저장한 예약의 가격 하락을 나중에 다시 점검하기

## 2. 주요 사용자 흐름

### 실시간 스캔

1. 사용자가 Agoda 호텔 상세 페이지를 엽니다.
2. 팝업에서 비교할 옵션을 선택합니다.
3. 백그라운드 서비스 워커가 결과 탭을 열고 스캔을 시작합니다.
4. 숨김 스캔 탭 3개가 재사용되며 각 시나리오를 병렬로 확인합니다.
5. 결과 탭에 상위 3개와 전체 결과가 실시간으로 누적됩니다.

### 예약 추적

1. 결과 탭에서 현재 페이지를 예약으로 저장하거나 예약 추적기에서 URL을 직접 등록합니다.
2. 예약 목록 페이지에서 개별 예약을 다시 확인할 수 있습니다.
3. 저장된 예약은 24시간마다 자동 점검됩니다.
4. 더 싼 가격이 발견되면 알림과 함께 최저가 링크를 다시 엽니다.

## 3. 파일 구성

핵심 파일:

- `manifest.json`
- `catalog.js`
- `background.js`
- `popup.html`
- `popup.css`
- `popup.js`
- `results.html`
- `results.css`
- `results.js`
- `reservations.html`
- `reservations.css`
- `reservations.js`

문서 및 운영 파일:

- `README.md`
- `VERSION_HISTORY.md`
- `PROJECT_HISTORY.md`
- `STEP_LOG.md`
- `tools/start-step.ps1`
- `tools/rollback.ps1`
- `snapshots/`

## 4. 역할 분리

### `manifest.json`

확장 프로그램의 엔트리와 권한을 정의합니다.

- 서비스 워커: `background.js`
- 팝업: `popup.html`
- 권한: `storage`, `tabs`, `scripting`, `alarms`, `notifications`
- 호스트 권한: `https://*.agoda.com/*`

### `catalog.js`

비교 가능한 링크 규칙을 정의합니다.

- 검색 경로
- 카드/결제
- 항공사/적립
- 프로모션 페이지

각 규칙은 선택 가능 항목으로 표시되며, 일부 규칙은 우선순위 `high`를 가집니다.

### `background.js`

실제 스캔 엔진과 상태 관리 중심 파일입니다.

주요 책임:

- 스캔 시작/중지
- 결과 탭과 예약 탭 열기
- 시나리오 URL 생성
- 숨김 스캔 탭 풀 3개 재사용
- Agoda 가격 추출
- 결과 랭킹 계산
- 예약 저장/조회/자동 점검
- 가격 하락 알림 처리

### `popup.*`

팝업은 스캔 제어와 설정 편집을 담당합니다.

- 옵션 선택
- 자동 실행 여부 저장
- 결과 탭 열기
- 예약 추적기 열기
- 스캔 시작/중지

### `results.*`

결과 탭은 실시간 결과 확인용 화면입니다.

- 기준 페이지 정보
- 현재 페이지 기준가
- 상위 3개 결과
- 전체 결과 테이블
- 예약 저장

### `reservations.*`

예약 추적기 전용 화면입니다.

- 수동 URL 등록
- 저장된 예약 목록
- 현재 최저가 확인
- 최저가 열기
- 항목 삭제

## 5. 스캔 엔진 구조

### 동시성

- 동시 스캔 개수는 항상 `3`
- 숨김 Agoda 스캔 탭도 항상 `3`

### 탭 재사용

- 스캔 시작 시 숨김 Agoda 탭 3개를 준비합니다.
- 각 시나리오는 사용 가능한 탭에 할당됩니다.
- 새 탭을 계속 만들지 않고 `chrome.tabs.update()`로 URL만 바꿉니다.
- 스캔 완료, 중지, 기준 탭 변경 시에만 정리합니다.

### 시나리오 생성

비교 가능한 규칙은 두 변형으로 확장됩니다.

- `desktop`: `isShowMobileAppPrice=false`
- `mobile`: `isShowMobileAppPrice=true`

프로모션 페이지처럼 비교 대상이 아닌 규칙은 변형을 만들지 않습니다.

### 우선순위

실행 순서는 아래와 같습니다.

1. `high` 우선순위 카드/결제 규칙
2. `normal` 우선순위 검색/일반 유입 규칙
3. 프로모션 페이지 열기 전용 규칙

## 6. 가격 추출 규칙

가격 추출은 Agoda DOM 속성과 화면 텍스트를 함께 사용합니다.

우선순위:

1. `cheapest-room-price-property-nav-bar` 계열 DOM 속성
2. `fpc-room-price` 계열 DOM 속성
3. `시작가` 바로 다음 금액
4. `1박` 바로 이전 금액

추가 방어 규칙:

- `0`으로 먼저 들어오는 Agoda 속성값은 바로 버립니다.
- `ICN` 같은 3글자 공항 코드는 통화로 인정하지 않습니다.
- 항공 위젯, 숙소 개수, 할부/월 결제 금액은 가격 후보에서 제외합니다.

## 7. 상태 모델

백그라운드는 `scanState`를 중심으로 동작합니다.

대표 필드:

- `running`
- `message`
- `currentIndex`
- `total`
- `results`
- `currentPageResult`
- `sourceUrl`
- `sourceTitle`
- `updatedAt`

이 상태는 팝업, 결과 탭, 예약 추적기에서 재사용됩니다.

## 8. 예약 추적 데이터

저장 키:

- `savedReservations`

저장 구조:

```json
[
  {
    "id": "reservation-...",
    "url": "https://www.agoda.com/...",
    "hotelName": "Hilton Dalian",
    "priceBooked": 181659,
    "currency": "KRW",
    "checkin": "2026-04-13",
    "checkout": "2026-04-14",
    "createdAt": "2026-03-15T10:00:00+09:00"
  }
]
```

제한:

- 최대 저장 수: `5`

## 9. 자동 점검

- `chrome.alarms`를 사용합니다.
- 예약이 하나 이상 있으면 24시간마다 자동 점검합니다.
- 최저가가 예약가보다 낮아지면 알림을 생성합니다.
- 알림 클릭 시 저장된 최저가 링크를 다시 엽니다.

## 10. 주요 버전 흐름

- `1.0.0`: 기본 스캔/결과 탭 안정화
- `1.3.0`: 병렬 스캔 안정화
- `1.4.0`: 신규 CID 규칙 추가
- `1.5.0`: 우선순위/모바일 변형/탭 풀 강화
- `2.0.0`: 브랜드 변경, 한글 통일, 예약 추적 직접 등록

세부 연혁은 `PROJECT_HISTORY.md`와 `VERSION_HISTORY.md`를 참고합니다.

## 11. 한계

- Agoda DOM 구조가 바뀌면 추출 규칙이 다시 조정될 수 있습니다.
- 기기, 로그인 상태, 통화, 쿠키, 광고 차단 등 환경 차이로 결과가 달라질 수 있습니다.
- 국가/IP 기반 가격 차이는 확장 프로그램만으로 완전히 재현하기 어렵습니다.
- 프로모션 페이지는 실제 호텔 상세 가격 비교가 아니라 열기 전용인 경우가 있습니다.

## 12. 롤백 방식

모든 큰 변경은 스냅샷으로 저장합니다.

예시:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-036-agoda-best-v2-docs-icons-layout
```
