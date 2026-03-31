import json
from functools import lru_cache
from html import escape
from pathlib import Path
import re

from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app.collector.categories import (
    CATEGORY_GROUPS,
    CATEGORY_SOURCE_CHOICES,
    DEFAULT_CATEGORY,
    DEFAULT_CATEGORY_SOURCE,
    DEFAULT_TREND_SERVICE,
    TREND_SERVICE_CHOICES,
)
from app.expander.utils.tokenizer import normalize_key
from app.core.title_prompt_settings import get_title_prompt_settings
from app.title.ai_client import get_default_system_prompt
from app.title.evaluation_prompt import DEFAULT_TITLE_EVALUATION_PROMPT
from app.title.issue_sources import (
    DEFAULT_COMMUNITY_SOURCE_KEYS,
    build_community_source_payload,
    build_issue_source_mode_payload,
)
from app.title.presets import DEFAULT_TITLE_PRESET_KEY, build_title_preset_payload


router = APIRouter()
_ASSET_VERSION = "20260329-layout-v86"
_STUDY_DIR = Path(__file__).resolve().parents[1] / "Study"
_GUIDE_GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("basics", "시작하기", ("사용법", "무료 키워드", "검색량 조회", "도구 추천")),
    ("discovery", "키워드 발굴", ("황금키워드", "연관검색어", "롱테일", "검색량 많은", "트렌드")),
    ("blog", "블로그 전략", ("블로그", "SEO", "방문자", "애드포스트")),
    ("ads", "광고 · CPC", ("CPC", "입찰가", "경쟁사")),
    ("business", "스토어 · 플레이스", ("스마트스토어", "플레이스", "시즌")),
)


_GUIDE_GROUPS = (
    ("basics", "시작하기", ()),
    ("discovery", "발굴과 선별", ()),
    ("titles", "제목 만들기", ()),
    ("operations", "운영과 재사용", ()),
)

_GUIDE_BLUEPRINTS: tuple[dict[str, object], ...] = (
    {
        "slug": "quickstart-basics",
        "title": "처음 시작할 때 보는 3패널",
        "subtitle": "상단의 시작모드, 실행버튼, 2축선별만 이해하면 첫 실행은 바로 할 수 있습니다.",
        "group": "basics",
        "sections": (
            {"title": "시작모드", "summary": "키워드 발굴, 보유 키워드 분석, 제목 생성 중 오늘 할 일을 먼저 고릅니다."},
            {"title": "실행버튼", "summary": "실행, 확장만, 분석만, 제목만 등 현재 목적에 맞는 흐름을 한 번에 시작합니다."},
            {"title": "관련 설정 보기", "summary": "상세 설정은 모달로 열어 화면을 어지럽히지 않고, 필요할 때만 펼칠 수 있습니다."},
        ),
        "detail_sections": (
            {
                "kicker": "빠른 진입",
                "title": "처음에는 상단 3패널만 보세요",
                "paragraphs": (
                    "이 앱은 처음부터 모든 패널을 이해하는 방식이 아니라, 상단의 세 블록만 보고 실행을 시작하는 흐름에 맞춰져 있습니다.",
                    "시작모드는 오늘 할 일을 정하고, 실행버튼은 실제 파이프라인을 돌리며, 2축선별은 결과를 어떤 기준으로 남길지 결정합니다.",
                ),
                "points": (
                    "키워드 발굴: 시드에서 수집, 확장, 분석, 선별까지 한 번에 이어집니다.",
                    "보유 키워드 분석: 이미 가진 키워드나 외부 결과를 붙여 넣고 분석과 선별만 빠르게 돌립니다.",
                    "제목 생성: 선별된 키워드나 직접 입력한 키워드에서 제목만 집중적으로 만듭니다.",
                ),
            },
            {
                "kicker": "모달 설정",
                "title": "관련 설정 보기는 모드별로 다르게 열립니다",
                "paragraphs": (
                    "키워드 발굴에서는 수집 설정이 열리고, 보유 키워드 분석에서는 분석 시작점, 제목 생성에서는 제목 시작점 설정이 열립니다.",
                    "자주 쓰는 값은 최소한만 바꾸고, 나머지는 실행 후 결과를 보면서 조정하는 편이 더 빠릅니다.",
                ),
                "points": (
                    "시작모드를 먼저 고른 뒤 관련 설정을 여는 순서가 가장 덜 헷갈립니다.",
                    "상단에서 바로 보이지 않는 상세 값은 모달 안에서만 바꾸고 닫으면 됩니다.",
                ),
            },
            {
                "kicker": "결과 중심",
                "title": "실행 후에는 결과와 선별이 메인입니다",
                "paragraphs": (
                    "이 앱의 핵심은 표 전체보다 살아남은 선별 결과를 빠르게 보고, 다시 시드화하거나 출력으로 이어지는 루프에 있습니다.",
                    "실행 중에는 선별 결과가 먼저 보이면 그걸 우선 검토하고, 선별 0건이면 분석이나 확장 결과로 바로 내려가 다음 결정을 하면 됩니다.",
                ),
            },
        ),
    },
    {
        "slug": "discovery-workflow",
        "title": "키워드 발굴은 어떻게 흘러가는가",
        "subtitle": "수집과 확장은 백엔드에서 처리하고, 결과는 단계별로 저장·복사·재활용하는 흐름을 권장합니다.",
        "group": "discovery",
        "sections": (
            {"title": "수집 설정", "summary": "카테고리, 수집 소스, 트렌드 날짜, 로그인 브라우저를 모달에서 정리한 뒤 실행합니다."},
            {"title": "실시간 선별", "summary": "확장과 분석이 진행되는 동안 조건에 맞는 후보는 선별 결과로 먼저 확인할 수 있습니다."},
            {"title": "0건 대응", "summary": "선별이 0건이어도 확장·분석 결과는 남으므로 다음 시드를 찾는 재료로 쓸 수 있습니다."},
        ),
        "detail_sections": (
            {
                "kicker": "발굴 루프",
                "title": "키워드 발굴 모드의 기본 순서",
                "paragraphs": (
                    "시드 입력 또는 주제 시드 생성을 준비한 뒤 실행하면, 수집과 확장은 백엔드에서 무겁게 처리되고 프론트는 결과를 소비하는 쪽에 집중합니다.",
                    "이 구조는 브라우저 부담을 줄이면서도 실행 중 살아남는 후보를 빨리 확인할 수 있게 하려는 의도입니다.",
                ),
                "points": (
                    "수집: 카테고리, 트렌드 소스, 로그인 상태가 반영됩니다.",
                    "확장: 연관·자동완성·조합 전략이 누적되며 다음 분석 대상으로 이어집니다.",
                    "분석: 조회수, 블로그 수, 입찰가, 경쟁 신호를 정리합니다.",
                    "선별: 2축 조합 조건을 만족한 후보만 앞단에 남깁니다.",
                ),
            },
            {
                "kicker": "실행 중 판단",
                "title": "선별 결과가 먼저 보이면 바로 활용하세요",
                "paragraphs": (
                    "선별된 키워드는 실행이 완전히 끝나기 전에도 결과 작업대에서 먼저 확인할 수 있습니다.",
                    "좋은 키워드는 보관함으로 넘기거나 제목 생성 전 단계로 묶어두고, 애매한 키워드는 시드화 버튼으로 다시 탐색하는 것이 가장 효율적입니다.",
                ),
            },
            {
                "kicker": "실패가 아닌 재료",
                "title": "선별 0건도 다음 실행의 재료입니다",
                "paragraphs": (
                    "선별이 0건이라고 해서 실행이 헛돈 것은 아닙니다. 확장과 분석에서 나온 후보가 그대로 남아 있으므로, 왜 탈락했는지 보고 다음 시드나 프리셋을 바꾸면 됩니다.",
                    "수익성은 좋지만 노출도가 약한지, 반대로 노출 가능성은 있으나 수익성이 약한지 먼저 가른 뒤 재실행하는 편이 빠릅니다.",
                ),
            },
        ),
    },
    {
        "slug": "dual-axis-selection",
        "title": "2축 선별을 제대로 쓰는 방법",
        "subtitle": "수익성 A~F와 노출도 1~6을 조합해, 황금형과 롱테일 탐색형 사이를 세밀하게 고릅니다.",
        "group": "discovery",
        "sections": (
            {"title": "수익성 축", "summary": "입찰가 비중이 가장 크고, 검색량과 클릭 잠재력은 보조 신호로만 반영됩니다."},
            {"title": "노출도 축", "summary": "경쟁, 기회비율, 검색량, 클릭 신호를 묶어 실제 공략 가능성을 봅니다."},
            {"title": "프리셋", "summary": "전체, 균형형, 황금형, 수익형, 노출형, 롱테일 탐색형을 상황에 따라 바꿔 씁니다."},
        ),
        "detail_sections": (
            {
                "kicker": "축의 의미",
                "title": "수익성과 노출도는 비슷해 보여도 역할이 다릅니다",
                "paragraphs": (
                    "수익성 축은 광고 단가를 중심에 두고, 검색량과 클릭 잠재력을 약하게 보정합니다. 검색량이 적더라도 고단가 키워드를 완전히 버리지 않도록 설계된 축입니다.",
                    "노출도 축은 경쟁비율, 기회비율, 검색량, 클릭 신호를 묶어 실제로 뚫을 수 있는지에 더 가깝게 봅니다.",
                ),
                "points": (
                    "수익성 A가 곧 노출형 키워드라는 뜻은 아닙니다.",
                    "노출도 1이 곧 고수익 키워드라는 뜻도 아닙니다.",
                    "좋은 키워드는 두 축이 모두 일정 수준 이상인 지점에서 주로 나옵니다.",
                ),
            },
            {
                "kicker": "프리셋 운용",
                "title": "6개 프리셋은 이렇게 나눠 쓰면 됩니다",
                "points": (
                    "전체: 처음 시장을 넓게 볼 때 가장 안전한 기본값입니다.",
                    "균형형: 과도한 모험 없이 발굴 품질을 유지할 때 좋습니다.",
                    "황금형: 높은 수익성과 높은 노출 가능성이 동시에 필요한 경우에 씁니다.",
                    "수익형: 보험, 금융, 고단가 제휴처럼 단가 중심 발굴에 유리합니다.",
                    "노출형: 트래픽과 확장 아이디어가 더 중요한 주제에 맞습니다.",
                    "롱테일 탐색형: 메인 키워드보다 파생 글감과 빈틈을 찾는 데 적합합니다.",
                ),
            },
            {
                "kicker": "실전 팁",
                "title": "최대 수익을 노릴 때의 기본 원칙",
                "paragraphs": (
                    "처음부터 황금형만 고집하면 시드가 약할 때 아무것도 안 남을 수 있습니다. 전체나 균형형으로 한 번 시장을 넓게 본 뒤, 좋은 묶음이 보이면 수익형이나 황금형으로 다시 조이는 방식이 안정적입니다.",
                    "선별 결과가 적게 남아도, 그 안에서 시드화와 제목 생성을 바로 이어 붙이면 작은 고단가 키워드를 연속적으로 공략할 수 있습니다.",
                ),
            },
        ),
    },
    {
        "slug": "results-export-and-seedify",
        "title": "결과를 다시 돈이 되는 입력으로 바꾸는 법",
        "subtitle": "출력 및 복사, 시드화, 단계별 파일 내보내기를 이용하면 좋은 키워드를 다음 사이클로 바로 넘길 수 있습니다.",
        "group": "operations",
        "sections": (
            {"title": "출력 및 복사", "summary": "상단 플로팅의 출력 및 복사에서 CSV, TXT, 줄바꿈 복사, 콤마 복사를 단계별로 바로 실행합니다."},
            {"title": "시드화", "summary": "확장·분석 결과에서 좋은 후보를 눌러 시드 입력으로 바로 올리고 다음 탐색의 시작점으로 씁니다."},
            {"title": "단계 보존", "summary": "수집, 확장, 분석, 선별 결과는 각각 저장할 수 있으므로 실험 기록을 남기기 쉽습니다."},
        ),
        "detail_sections": (
            {
                "kicker": "도크 활용",
                "title": "출력 및 복사는 상단 도크에서 여는 것이 기준입니다",
                "paragraphs": (
                    "결과 작업대 안에 버튼을 늘어놓는 대신, 상단 플로팅 도크에서 필요할 때만 펼쳐 쓰는 구조로 바뀌었습니다.",
                    "이제 실행 화면은 깔끔하게 두고, 저장과 복사는 작업 흐름이 필요할 때만 꺼내 쓰는 방식이 자연스럽습니다.",
                ),
            },
            {
                "kicker": "재발굴",
                "title": "시드화는 좋은 후보를 즉시 다음 탐색으로 연결합니다",
                "paragraphs": (
                    "확장 결과나 분석 결과에서 가능성이 보이는 키워드는 시드화 버튼으로 바로 시드 입력칸으로 올릴 수 있습니다.",
                    "실행은 자동으로 시작하지 않으므로, 여러 개를 모아서 다시 돌리거나 2축 프리셋을 바꾼 뒤 재실행하는 데 유리합니다.",
                ),
            },
            {
                "kicker": "보존 전략",
                "title": "단계별 파일은 비교와 복기에 쓸 때 강합니다",
                "points": (
                    "수집 결과: 소스 품질과 시드 방향을 비교할 때 사용합니다.",
                    "확장 결과: 어떤 조합 전략이 후보를 가장 잘 늘렸는지 확인할 때 좋습니다.",
                    "분석 결과: 조회수, 블로그 수, 입찰가 기준으로 다시 필터링할 때 씁니다.",
                    "선별 결과: 실제 운영 후보를 보관함, 제목, 외부 시트로 넘길 때 가장 많이 쓰입니다.",
                ),
            },
        ),
    },
    {
        "slug": "title-generation-setup",
        "title": "제목 생성은 필요한 만큼만 만드는 것이 핵심",
        "subtitle": "홈판, 블로그형, 둘다를 각각 켜고 개수까지 따로 정할 수 있으므로 한 번에 과하게 만들 필요가 없습니다.",
        "group": "titles",
        "sections": (
            {"title": "영역 선택", "summary": "홈판, 블로그형, 둘다를 각각 켜고 끌 수 있으며, 목적에 맞는 영역만 남길 수 있습니다."},
            {"title": "개수 조절", "summary": "영역별로 1~4개를 따로 정해 최소 1개부터 최대 12개까지 유연하게 생성할 수 있습니다."},
            {"title": "평가와 정렬", "summary": "생성 뒤에는 빠른 평가를 거쳐 높은 점수 순으로 정렬되므로 검토 시간이 줄어듭니다."},
        ),
        "detail_sections": (
            {
                "kicker": "표면 선택",
                "title": "세 영역을 모두 켤 필요는 없습니다",
                "paragraphs": (
                    "홈판은 클릭률과 이슈 반영, 블로그형은 검색 의도와 정보형 문장, 둘다는 두 성격을 함께 노리는 공용 제목에 가깝습니다.",
                    "주제가 명확할수록 필요한 영역만 켜는 편이 결과 관리가 쉽고, API 사용량도 덜 낭비됩니다.",
                ),
                "points": (
                    "빠른 검토가 목적이면 홈판 1~2개만 먼저 만드는 방식이 가볍습니다.",
                    "정보형 글감이면 블로그형 위주로 개수를 늘리는 편이 낫습니다.",
                    "둘다는 메인 제목이 아니라 후보 확장용으로 보는 것이 안전합니다.",
                ),
            },
            {
                "kicker": "정렬 기준",
                "title": "결과는 많이 만드는 것보다 점수순으로 버리는 것이 중요합니다",
                "paragraphs": (
                    "동일 키워드에서 제목을 여러 개 생성해도 빠른 평가와 정렬이 먼저 이뤄지므로, 실제로는 상위 몇 개만 검토하면 됩니다.",
                    "내보내기 파일에는 홈판, 블로그형, 둘다 구분이 붙으므로 작업 전달이나 기록 정리도 편합니다.",
                ),
            },
            {
                "kicker": "권장 루틴",
                "title": "제목은 선별 이후에 붙여도 충분합니다",
                "paragraphs": (
                    "이 앱의 우선순위는 발굴과 선별입니다. 제목은 선별된 키워드가 어느 정도 모인 뒤 한 번에 생성해도 흐름이 끊기지 않습니다.",
                    "제목 생성 중에는 현재 이슈 반영, 자동 재시도, 평가 프롬프트 같은 옵션을 상황에 맞게만 켜고 나머지는 기본값으로 두는 편이 안정적입니다.",
                ),
            },
        ),
    },
    {
        "slug": "history-vault-and-queue",
        "title": "기록, 보관함, 예약 큐를 같이 써야 반복 수익이 쌓입니다",
        "subtitle": "좋은 키워드를 한 번 쓰고 버리지 않으려면 기록과 재실행 체계를 같이 굴려야 합니다.",
        "group": "operations",
        "sections": (
            {"title": "실행 기록", "summary": "어떤 시드와 어떤 프리셋이 잘 먹혔는지 복기할 때 가장 먼저 보는 곳입니다."},
            {"title": "보관함", "summary": "좋은 키워드 묶음을 발행 전, 발행 후, 다시보기 기준으로 나눠 관리할 수 있습니다."},
            {"title": "예약 큐", "summary": "오늘 바로 못 돌릴 주제나 루틴 발굴 작업을 쌓아두고 순차 실행하는 데 쓸 수 있습니다."},
        ),
        "detail_sections": (
            {
                "kicker": "복기",
                "title": "실행 기록은 잘된 시드를 재현하는 용도입니다",
                "paragraphs": (
                    "수익이 난 키워드는 결과 자체보다도 어떤 시작모드, 어떤 2축 프리셋, 어떤 소스 조합에서 나왔는지가 더 중요합니다.",
                    "실행 기록은 이 조합을 다시 불러오기 위한 장부라고 생각하면 됩니다.",
                ),
            },
            {
                "kicker": "누적 자산",
                "title": "보관함은 운영 단계별 후보 창고입니다",
                "points": (
                    "발행 전: 제목과 본문 작업 대기 중인 후보",
                    "발행 완료: 이미 사용했지만 시즌이나 업데이트로 다시 볼 수 있는 후보",
                    "다시 보기: 선별 당시에는 보류했지만 나중에 가치가 생길 수 있는 후보",
                ),
            },
            {
                "kicker": "반복 실행",
                "title": "예약 큐는 루틴을 고정할 때 힘을 발휘합니다",
                "paragraphs": (
                    "좋은 주제를 찾았다고 해서 매번 손으로 다시 입력할 필요는 없습니다. 큐와 루틴을 이용하면 고수익 주제를 일정 주기로 다시 탐색할 수 있습니다.",
                    "특히 금융, 보험, 비교 키워드처럼 시즌별로 변하는 분야에서는 큐를 써 두는 편이 꾸준한 수익 관리에 유리합니다.",
                ),
            },
        ),
    },
    {
        "slug": "session-and-safety",
        "title": "로그인 세션과 보호 설정은 실무 안정장치입니다",
        "subtitle": "트렌드 수집과 로그인 기반 기능을 오래 안정적으로 쓰려면 세션과 보호값을 가볍게 점검해야 합니다.",
        "group": "operations",
        "sections": (
            {"title": "현재 브라우저 쿠키 읽기", "summary": "로그인해 둔 브라우저에서 쿠키를 읽어와 수집에 필요한 세션을 재사용합니다."},
            {"title": "로그인 상태 확인", "summary": "세션이 유효한지 먼저 확인하면 실행 중 불필요한 실패를 줄일 수 있습니다."},
            {"title": "보호 설정", "summary": "운영 드로어의 지연·보호 옵션을 함께 쓰면 장시간 실행에서 더 안정적입니다."},
        ),
        "detail_sections": (
            {
                "kicker": "세션 관리",
                "title": "Creator Advisor 로그인은 보조 카드로 분리됐습니다",
                "paragraphs": (
                    "수집 설정 안에서는 카테고리와 트렌드 값을 먼저 고르고, 로그인 관련 작업은 하단의 넓은 카드에서 따로 처리하게 바뀌었습니다.",
                    "이 구조는 설정을 읽기 쉽게 만들고, 로그인 버튼이 좁은 칸을 밀어내지 않게 하기 위한 조정입니다.",
                ),
            },
            {
                "kicker": "실행 전 확인",
                "title": "세션이 불안하면 상태 확인부터 누르세요",
                "paragraphs": (
                    "로그인이 풀린 상태에서 장시간 실행을 시작하면 수집 품질이 급격히 흔들릴 수 있습니다.",
                    "짧게 상태를 확인하고, 필요하면 현재 브라우저 쿠키 읽기로 다시 맞춘 뒤 실행하는 습관이 좋습니다.",
                ),
            },
            {
                "kicker": "안정성",
                "title": "보호 설정은 속도보다 지속 가능성을 위한 옵션입니다",
                "points": (
                    "짧은 테스트는 기본값으로 충분합니다.",
                    "장시간 발굴은 요청 간격과 보호 옵션을 조금 높이는 편이 안전합니다.",
                    "큐를 오래 돌릴 때일수록 진단 로그와 기록을 함께 보는 습관이 중요합니다.",
                ),
            },
        ),
    },
)


def _render_category_options() -> str:
    rendered_groups: list[str] = []
    for group_name, categories in CATEGORY_GROUPS:
        options = "".join(
            f'<option value="{category}"{" selected" if category == DEFAULT_CATEGORY else ""}>{category}</option>'
            for category in categories
        )
        rendered_groups.append(f'<optgroup label="{group_name}">{options}</optgroup>')

    return "".join(rendered_groups)


def _render_queue_routine_category_picker() -> str:
    rendered_groups: list[str] = []
    for group_name, categories in CATEGORY_GROUPS:
        chips = "".join(
            (
                '<label class="check-chip queue-category-chip">'
                f'<input type="checkbox" value="{escape(category)}" data-queue-category />'
                f"{escape(category)}"
                "</label>"
            )
            for category in categories
        )
        rendered_groups.append(
            '<div class="queue-category-group">'
            f'<span class="queue-category-group-label">{escape(group_name)}</span>'
            f'<div class="queue-category-chip-grid">{chips}</div>'
            "</div>"
        )
    return "".join(rendered_groups)


def _render_title_issue_source_mode_options() -> str:
    return "".join(
        f'<option value="{escape(str(item["key"]))}"{" selected" if item["key"] == "mixed" else ""}>'
        f'{escape(str(item["label"]))}'
        "</option>"
        for item in build_issue_source_mode_payload()
    )


def _render_title_community_source_chips() -> str:
    return "".join(
        (
            '<label class="check-chip">'
            f'<input type="checkbox" value="{escape(str(item["key"]))}" data-title-community-source'
            f'{" checked" if item["key"] in DEFAULT_COMMUNITY_SOURCE_KEYS else ""} />'
            f'{escape(str(item["label"]))}'
            "</label>"
        )
        for item in build_community_source_payload()
    )


def _replace_sample_site_name(value: str) -> str:
    replaced = str(value or "")
    replaced = replaced.replace("키워드마스터", "본 사이트")
    replaced = replaced.replace("KeywordMaster", "본 사이트")
    replaced = replaced.replace("keywordmaster.net", "본 사이트")
    return replaced


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").split())


def _render_help_tooltip(text: str, *, label: str = "도움말") -> str:
    lines = [escape(_clean_text(line)) for line in str(text or "").splitlines() if _clean_text(line)]
    if not lines:
        return ""
    return (
        '<span class="inline-help">'
        f'<button type="button" class="help-icon-btn" aria-label="{escape(label)}">?</button>'
        f'<span class="help-tooltip">{"<br />".join(lines)}</span>'
        "</span>"
    )


def _build_guide_slug(index: int, path: Path) -> str:
    stem = re.sub(r"-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}$", "", path.stem)
    base = normalize_key(_replace_sample_site_name(stem)) or f"guide{index}"
    return f"guide-{index:02d}-{base[:48]}"


def _pick_guide_group(title: str) -> str:
    for key, _label, keywords in _GUIDE_GROUPS:
        if any(keyword in title for keyword in keywords):
            return key
    return "discovery"


def _sanitize_guide_content(article_html: str, *, title_map: dict[str, str]) -> str:
    soup = BeautifulSoup(article_html, "html.parser")

    for element in soup.select("script, style, nav, footer"):
        element.decompose()

    for text_node in soup.find_all(string=True):
        parent_name = getattr(text_node.parent, "name", "")
        if parent_name in {"script", "style"}:
            continue
        replaced = _replace_sample_site_name(str(text_node))
        if replaced != str(text_node):
            text_node.replace_with(replaced)

    for anchor in soup.find_all("a"):
        href = str(anchor.get("href") or "").strip()
        label = _clean_text(anchor.get_text(" ", strip=True))
        local_slug = title_map.get(label)
        if local_slug:
            anchor["href"] = f"/guides/{local_slug}"
            anchor.attrs.pop("target", None)
            anchor.attrs.pop("rel", None)
            continue

        if "keywordmaster.net" in href:
            anchor["href"] = "/" if "page=search" in href else "/guides"
            anchor.attrs.pop("target", None)
            anchor.attrs.pop("rel", None)
            continue

        if href.startswith(("http://", "https://")):
            anchor["target"] = "_blank"
            anchor["rel"] = "noopener noreferrer"

    return str(soup)


def _render_doc_list(items: list[object] | tuple[object, ...]) -> str:
    entries = [f"<li>{escape(str(item))}</li>" for item in items if str(item).strip()]
    return f"<ul>{''.join(entries)}</ul>" if entries else ""


def _render_guide_content_html(sections: list[dict[str, object]] | tuple[dict[str, object], ...]) -> str:
    rendered: list[str] = []
    for section in sections:
        title = str(section.get("title") or "").strip()
        if not title:
            continue
        kicker = str(section.get("kicker") or "").strip()
        paragraphs = "".join(
            f"<p>{escape(str(text))}</p>"
            for text in section.get("paragraphs", [])
            if str(text).strip()
        )
        points = _render_doc_list(section.get("points", []))
        rendered.append(
            f"""
            <section class="doc-section">
                <div class="doc-section-head">
                    {f'<p class="panel-kicker">{escape(kicker)}</p>' if kicker else ''}
                    <h2>{escape(title)}</h2>
                </div>
                {paragraphs}
                {points}
            </section>
            """
        )
    return "".join(rendered)


@lru_cache
def _load_study_guides() -> list[dict[str, object]]:
    return [
        {
            "slug": str(guide["slug"]),
            "title": str(guide["title"]),
            "subtitle": str(guide["subtitle"]),
            "group": str(guide["group"]),
            "sections": list(guide.get("sections", [])),
            "content_html": _render_guide_content_html(list(guide.get("detail_sections", []))),
        }
        for guide in _GUIDE_BLUEPRINTS
    ]


def _render_guide_card(guide: dict[str, object]) -> str:
    section_items = "".join(
        f"<li><strong>{escape(str(section['title']))}</strong><span>{escape(str(section['summary']))}</span></li>"
        for section in guide.get("sections", [])
        if str(section.get("title") or "").strip()
    )
    return f"""
        <article class="guide-article-card">
            <div class="guide-article-head">
                <h4>{escape(str(guide['title']))}</h4>
                <p>{escape(str(guide['subtitle']))}</p>
            </div>
            <ul class="guide-article-points">
                {section_items}
            </ul>
            <a class="secondary-link guide-article-link" href="/guides/{escape(str(guide['slug']))}">문서 보기</a>
        </article>
    """


def _render_guide_panel() -> str:
    guides = _load_study_guides()
    if not guides:
        return ""

    grouped: dict[str, list[dict[str, object]]] = {key: [] for key, _label, _keywords in _GUIDE_GROUPS}
    for guide in guides:
        group_key = str(guide.get("group") or "discovery")
        grouped.setdefault(group_key, []).append(guide)

    tab_buttons = "".join(
        f'<button type="button" class="guide-tab-button{" active" if index == 0 else ""}" '
        f'data-guide-tab="{escape(key)}">{escape(label)}</button>'
        for index, (key, label, _keywords) in enumerate(_GUIDE_GROUPS)
    )

    tab_panels = []
    for index, (key, label, _keywords) in enumerate(_GUIDE_GROUPS):
        cards = "".join(_render_guide_card(guide) for guide in grouped.get(key, []))

        tab_panels.append(
            f"""
            <section class="guide-tab-panel{' active' if index == 0 else ''}" data-guide-panel="{escape(key)}" {'hidden' if index != 0 else ''}>
                <div class="guide-card-grid">
                    {cards if cards else '<div class="placeholder">해당 분류의 문서가 없습니다.</div>'}
                    <button type="button" class="ghost-chip" id="exportCollectedCsvButtonUtility">?섏쭛 CSV</button>
                    <button type="button" class="ghost-chip" id="exportSelectedCsvButtonUtility">?좊퀎 CSV</button>
                </div>
            </section>
            """
        )

    return f"""
        <section class="panel guide-panel">
            <div class="panel-head">
                <div>
                    <p class="panel-kicker">가이드</p>
                    <h2>사용 가이드</h2>
                </div>
                <span class="status-pill success">Study {len(guides)}편 반영</span>
            </div>
            <p class="input-help compact-help">
                Study 폴더 문서를 주제별로 묶었습니다. 본 사이트 사용 흐름과 운영 팁을 홈 화면에서 바로 열어볼 수 있습니다.
            </p>
            <div class="guide-tab-strip">
                {tab_buttons}
            </div>
            <div class="guide-tab-panels">
                {''.join(tab_panels)}
            </div>
        </section>
    """


def _render_static_shell(*, title: str, description: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(title)} | 키워드 포지</title>
    <meta name="description" content="{escape(description)}" />
    <link rel="stylesheet" href="/assets/app.css?v={_ASSET_VERSION}" />
</head>
<body>
    <div class="app-topbar">
        <div class="app-topbar-inner">
            <a class="app-topbar-brand" href="#section-progress" aria-label="Keyword Forge 상단으로 이동">
                <span class="app-topbar-brand-mark">KF</span>
                <span class="app-topbar-brand-copy">
                    <strong>Keyword Forge</strong>
                    <span>Local-first keyword workflow</span>
                </span>
            </a>
            <nav class="app-topbar-links" aria-label="주요 탐색">
                <a class="app-topbar-link" href="#section-controls">실행 조건</a>
                <a class="app-topbar-link" href="#section-select">2축 선별</a>
                <a class="app-topbar-link" href="#section-results">결과 작업대</a>
                <a class="app-topbar-link" href="/guides">가이드</a>
            </nav>
            <div class="app-topbar-actions">
                <button type="button" class="ghost-chip topbar-chip" data-utility-open="history" aria-pressed="false">실행 기록</button>
                <button type="button" class="ghost-chip topbar-chip" data-utility-open="vault" aria-pressed="false">보관함</button>
                <button type="button" class="ghost-chip topbar-chip" data-utility-open="queue" aria-pressed="false">예약</button>
            </div>
        </div>
    </div>
    <div class="bg-orb bg-orb-a"></div>
    <div class="bg-orb bg-orb-b"></div>
    <div class="bg-grid"></div>
    {body}
</body>
</html>
"""


def _render_title_prompt_editor() -> str:
    title_presets = build_title_preset_payload()
    title_preset_payload = json.dumps(title_presets, ensure_ascii=False).replace("</", "<\\/")
    default_system_prompt_payload = json.dumps(get_default_system_prompt(), ensure_ascii=False).replace("</", "<\\/")
    default_evaluation_prompt_payload = json.dumps(
        DEFAULT_TITLE_EVALUATION_PROMPT,
        ensure_ascii=False,
    ).replace("</", "<\\/")
    default_preset_key_payload = json.dumps(DEFAULT_TITLE_PRESET_KEY, ensure_ascii=False)
    title_prompt_settings_payload = json.dumps(get_title_prompt_settings(), ensure_ascii=False).replace("</", "<\\/")
    body = f"""
    <div class="bg-orb bg-orb-a"></div>
    <div class="bg-orb bg-orb-b"></div>
    <div class="bg-grid"></div>
    <script>
        window.KEYWORD_FORGE_TITLE_PRESETS = {title_preset_payload};
        window.KEYWORD_FORGE_TITLE_DEFAULT_SYSTEM_PROMPT = {default_system_prompt_payload};
        window.KEYWORD_FORGE_TITLE_DEFAULT_EVALUATION_PROMPT = {default_evaluation_prompt_payload};
        window.KEYWORD_FORGE_TITLE_DEFAULT_PRESET_KEY = {default_preset_key_payload};
        window.KEYWORD_FORGE_TITLE_PROMPT_SETTINGS = {title_prompt_settings_payload};
    </script>
    <main class="doc-shell title-prompt-shell">
        <div class="doc-stack">
            <section class="doc-hero doc-hero-compact">
                <div class="doc-breadcrumbs">
                    <a href="/">키워드 포지</a>
                    <span>/</span>
                    <span>제목 프롬프트</span>
                </div>
                <div class="doc-hero-copy">
                    <p class="panel-kicker">제목 프롬프트</p>
                    <h1>AI 제목 프롬프트 관리</h1>
                    <p>
                        기본 시스템 프롬프트와 선택된 프리셋 안내는 계속 고정됩니다.
                        여기서는 그 뒤에 붙는 사용자 저장본을 만들고, 저장하고, 불러와서 현재 적용본으로 바꿀 수 있습니다.
                    </p>
                </div>
                <div class="title-prompt-guide">
                    <div class="title-prompt-guide-card">
                        <strong>현재 구조</strong>
                        <p>기본 시스템 프롬프트 + 선택한 프리셋 안내 + 저장본 또는 직접 입력 지침 순서로 실제 프롬프트가 구성됩니다.</p>
                    </div>
                    <div class="title-prompt-guide-card">
                        <strong>권장 운영</strong>
                        <p>홈판형, 리뷰형, 보수형 같은 저장본을 따로 만들어 두고 필요할 때 선택해서 쓰는 방식이 가장 관리하기 쉽습니다.</p>
                    </div>
                </div>
            </section>

            <section class="panel">
                <div class="panel-head">
                    <div>
                        <p class="panel-kicker">미리보기</p>
                        <h2>현재 적용 프롬프트 미리보기</h2>
                    </div>
                    <span class="status-pill" id="titlePromptEditorStatus">불러오는 중</span>
                </div>
                <div class="form-grid">
                    <div class="field-block">
                        <span class="field-label">현재 프리셋</span>
                        <div id="titlePromptPresetLabel" class="title-prompt-summary">불러오는 중</div>
                    </div>
                    <div class="field-block">
                        <span class="field-label">현재 적용 저장본</span>
                        <div id="titlePromptAppliedProfile" class="title-prompt-summary">불러오는 중</div>
                    </div>
                    <label class="field-block field-block-wide">
                        <span class="field-label">기본 시스템 + 프리셋 안내</span>
                        <textarea
                            id="titlePromptBasePreview"
                            class="title-prompt-textarea"
                            rows="14"
                            readonly
                        ></textarea>
                    </label>
                    <label class="field-block field-block-wide">
                        <span class="field-label">실제 적용 프롬프트 전체 미리보기</span>
                        <textarea
                            id="titlePromptEffectivePreview"
                            class="title-prompt-textarea"
                            rows="18"
                            readonly
                        ></textarea>
                    </label>
                </div>
            </section>

            <section class="panel">
                <div class="panel-head">
                    <div>
                        <p class="panel-kicker">저장본</p>
                        <h2>저장본 편집 및 선택</h2>
                    </div>
                    <span class="status-pill" id="titlePromptProfileStatus">저장본 불러오는 중</span>
                </div>
                <div class="form-grid">
                    <label class="field-block">
                        <span class="field-label">저장본 선택</span>
                        <select id="titlePromptProfileSelect"></select>
                    </label>
                    <label class="field-block">
                        <span class="field-label">저장본 이름</span>
                        <input
                            id="titlePromptProfileName"
                            type="text"
                            maxlength="40"
                            placeholder="예: 홈판 공격형"
                        />
                    </label>
                </div>
                <label class="field-block field-block-wide">
                    <span class="field-label">추가 지침 편집</span>
                    <textarea
                        id="titlePromptEditorInput"
                        class="title-prompt-textarea"
                        rows="16"
                        placeholder="예: 키워드는 항상 제목 맨 앞에 두고, 홈판용은 최신 이슈를 우선 반영하며, 과장형 금지 표현은 더 엄격하게 적용하세요."
                    ></textarea>
                </label>
                <p class="input-help compact-help">
                    저장본을 선택한 뒤 저장하면 메인 화면에서 바로 적용됩니다. 직접 입력으로 두면 저장본 없이 현재 지침만 적용합니다.
                </p>
                <div class="doc-actions title-prompt-actions">
                    <button type="button" class="subtle-btn" id="saveTitlePromptButton">현재 적용 저장</button>
                    <button type="button" class="ghost-btn" id="saveAsTitlePromptButton">새 저장본</button>
                    <button type="button" class="ghost-btn" id="deleteTitlePromptButton">저장본 삭제</button>
                    <button type="button" class="ghost-btn" id="clearTitlePromptEditorButton">현재 비우기</button>
                    <button type="button" class="ghost-chip" id="closeTitlePromptEditorButton">탭 닫기</button>
                </div>
            </section>
        </div>
    </main>
    <script>
        (function() {{
            const STORAGE_KEY = "keyword_forge_title_settings";
            const PROMPT_SETTINGS_ENDPOINT = "/settings/title-prompt";
            const presets = Array.isArray(window.KEYWORD_FORGE_TITLE_PRESETS) ? window.KEYWORD_FORGE_TITLE_PRESETS : [];
            const presetMap = presets.reduce((map, item) => {{
                const key = String(item && item.key || "").trim();
                if (key) {{
                    map[key] = item;
                }}
                return map;
            }}, {{}});
            const defaultSystemPrompt = String(window.KEYWORD_FORGE_TITLE_DEFAULT_SYSTEM_PROMPT || "").replace(/\\r\\n/g, "\\n").trim();
            const defaultPresetKey = String(window.KEYWORD_FORGE_TITLE_DEFAULT_PRESET_KEY || "").trim();
            const input = document.getElementById("titlePromptEditorInput");
            const status = document.getElementById("titlePromptEditorStatus");
            const profileStatus = document.getElementById("titlePromptProfileStatus");
            const profileSelect = document.getElementById("titlePromptProfileSelect");
            const profileNameInput = document.getElementById("titlePromptProfileName");
            const presetLabel = document.getElementById("titlePromptPresetLabel");
            const appliedProfile = document.getElementById("titlePromptAppliedProfile");
            const basePreview = document.getElementById("titlePromptBasePreview");
            const effectivePreview = document.getElementById("titlePromptEffectivePreview");
            const saveButton = document.getElementById("saveTitlePromptButton");
            const saveAsButton = document.getElementById("saveAsTitlePromptButton");
            const deleteButton = document.getElementById("deleteTitlePromptButton");
            const clearButton = document.getElementById("clearTitlePromptEditorButton");
            const closeButton = document.getElementById("closeTitlePromptEditorButton");
            let serverPromptSettings = {{}};
            let promptSettingsSyncSequence = 0;

            function readStoredSettings() {{
                try {{
                    return JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "{{}}");
                }} catch (error) {{
                    return {{}};
                }}
            }}

            function normalizePrompt(value) {{
                return String(value || "").replace(/\\r\\n/g, "\\n").trim();
            }}

            function normalizeProfileName(value) {{
                return String(value || "").replace(/\\s+/g, " ").trim();
            }}

            function normalizeProfileId(value) {{
                return String(value || "").trim();
            }}

            function resolveDirectPrompt(settings) {{
                const directPrompt = normalizePrompt(settings.direct_system_prompt || "");
                if (directPrompt) {{
                    return directPrompt;
                }}
                return normalizePrompt(settings.system_prompt || "");
            }}

            function normalizePromptProfiles(value) {{
                if (!Array.isArray(value)) {{
                    return [];
                }}
                const seenIds = new Set();
                const output = [];
                value.forEach((item, index) => {{
                    if (!item || typeof item !== "object") {{
                        return;
                    }}
                    const id = normalizeProfileId(item.id || `profile-${{index + 1}}`);
                    const name = normalizeProfileName(item.name || `저장본 ${{output.length + 1}}`);
                    const prompt = normalizePrompt(item.prompt);
                    if (!id || seenIds.has(id)) {{
                        return;
                    }}
                    seenIds.add(id);
                    output.push({{
                        id,
                        name,
                        prompt,
                        updated_at: String(item.updated_at || "").trim(),
                    }});
                }});
                return output;
            }}

            function normalizePromptSettings(settings) {{
                const source = settings && typeof settings === "object" ? settings : {{}};
                const profiles = normalizePromptProfiles(source.prompt_profiles);
                const activeProfile = resolveActiveProfile(source, profiles);
                const directPrompt = normalizePrompt(
                    source.direct_system_prompt || (activeProfile ? "" : source.system_prompt),
                );
                return {{
                    preset_key: String(source.preset_key || "").trim().toLowerCase(),
                    direct_system_prompt: directPrompt,
                    system_prompt: activeProfile ? activeProfile.prompt : directPrompt,
                    prompt_profiles: profiles,
                    active_prompt_profile_id: activeProfile ? activeProfile.id : "",
                }};
            }}

            function hasMeaningfulPromptSettings(settings = {{}}) {{
                const normalized = normalizePromptSettings(settings);
                return Boolean(
                    normalized.prompt_profiles.length
                    || normalized.active_prompt_profile_id
                    || normalized.direct_system_prompt
                    || (normalized.preset_key && normalized.preset_key !== defaultPresetKey)
                );
            }}

            function readSettings() {{
                const storedSettings = readStoredSettings();
                const localPromptSettings = normalizePromptSettings(storedSettings);
                const effectivePromptSettings = hasMeaningfulPromptSettings(serverPromptSettings)
                    ? serverPromptSettings
                    : localPromptSettings;
                return {{
                    ...storedSettings,
                    ...effectivePromptSettings,
                }};
            }}

            async function writeSettings(settings) {{
                const nextSettings = settings && typeof settings === "object" ? {{ ...settings }} : {{}};
                const normalizedPromptSettings = normalizePromptSettings(nextSettings);
                const mergedSettings = {{
                    ...nextSettings,
                    ...normalizedPromptSettings,
                }};
                window.localStorage.setItem(STORAGE_KEY, JSON.stringify(mergedSettings));

                serverPromptSettings = normalizedPromptSettings;
                window.KEYWORD_FORGE_TITLE_PROMPT_SETTINGS = normalizedPromptSettings;

                const syncId = ++promptSettingsSyncSequence;
                const response = await fetch(PROMPT_SETTINGS_ENDPOINT, {{
                    method: "POST",
                    headers: {{
                        "Content-Type": "application/json",
                    }},
                    body: JSON.stringify(normalizedPromptSettings),
                }});
                if (!response.ok) {{
                    throw new Error(`title_prompt_sync_failed:${{response.status}}`);
                }}
                const payload = await response.json();
                const savedPromptSettings = normalizePromptSettings(
                    payload && payload.title_prompt_settings ? payload.title_prompt_settings : normalizedPromptSettings,
                );
                serverPromptSettings = savedPromptSettings;
                window.KEYWORD_FORGE_TITLE_PROMPT_SETTINGS = savedPromptSettings;
                if (syncId === promptSettingsSyncSequence) {{
                    const latestLocalSettings = readStoredSettings();
                    window.localStorage.setItem(
                        STORAGE_KEY,
                        JSON.stringify({{
                            ...latestLocalSettings,
                            ...savedPromptSettings,
                        }}),
                    );
                }}
                return savedPromptSettings;
            }}

            function createProfileId() {{
                return `profile-${{Date.now()}}-${{Math.random().toString(36).slice(2, 8)}}`;
            }}

            function getPresetFromSettings(settings) {{
                const presetKey = String(settings.preset_key || "").trim().toLowerCase();
                return presetMap[presetKey] || presetMap[defaultPresetKey] || null;
            }}

            function resolveActiveProfile(settings, profiles = normalizePromptProfiles(settings.prompt_profiles)) {{
                const activeProfileId = normalizeProfileId(settings.active_prompt_profile_id);
                return profiles.find((profile) => profile.id === activeProfileId) || null;
            }}

            function resolveAppliedPrompt(settings, profiles = normalizePromptProfiles(settings.prompt_profiles)) {{
                const activeProfile = resolveActiveProfile(settings, profiles);
                if (activeProfile) {{
                    return activeProfile.prompt;
                }}
                return resolveDirectPrompt(settings);
            }}

            function buildBasePrompt(settings) {{
                const sections = [defaultSystemPrompt];
                const preset = getPresetFromSettings(settings);
                const presetPrompt = normalizePrompt(preset && preset.prompt_guidance || "");
                if (presetPrompt) {{
                    sections.push(`Preset guidance:\\n${{presetPrompt}}`);
                }}
                return sections.filter(Boolean).join("\\n\\n");
            }}

            function buildEffectivePrompt(settings, promptValue) {{
                const sections = [buildBasePrompt(settings)];
                const extraPrompt = normalizePrompt(promptValue);
                if (extraPrompt) {{
                    sections.push(`Additional guidance:\\n${{extraPrompt}}`);
                }}
                return sections.filter(Boolean).join("\\n\\n");
            }}

            function updateStatus(message, kind) {{
                status.textContent = message;
                status.classList.remove("success", "error");
                if (kind) {{
                    status.classList.add(kind);
                }}
            }}

            function updateProfileStatus(message, kind) {{
                profileStatus.textContent = message;
                profileStatus.classList.remove("success", "error");
                if (kind) {{
                    profileStatus.classList.add(kind);
                }}
            }}

            function renderProfileOptions(settings, selectedProfileId = "") {{
                const profiles = normalizePromptProfiles(settings.prompt_profiles);
                const activeProfileId = normalizeProfileId(selectedProfileId || settings.active_prompt_profile_id);
                profileSelect.innerHTML = "";

                const directOption = document.createElement("option");
                directOption.value = "";
                directOption.textContent = profiles.length ? "직접 입력 / 저장본 미선택" : "직접 입력";
                profileSelect.appendChild(directOption);

                profiles.forEach((profile) => {{
                    const option = document.createElement("option");
                    option.value = profile.id;
                    option.textContent = profile.name;
                    profileSelect.appendChild(option);
                }});

                profileSelect.value = activeProfileId;
                if (profileSelect.value !== activeProfileId) {{
                    profileSelect.value = "";
                }}
            }}

            function updatePreview(settings) {{
                const profiles = normalizePromptProfiles(settings.prompt_profiles);
                const selectedProfile = profiles.find((profile) => profile.id === normalizeProfileId(profileSelect.value)) || null;
                const promptValue = normalizePrompt(input.value);
                const preset = getPresetFromSettings(settings);

                presetLabel.textContent = preset
                    ? `${{preset.label}} / ${{preset.provider}} / ${{preset.model}} / temperature ${{preset.temperature}}`
                    : "직접 설정";
                appliedProfile.textContent = selectedProfile
                    ? `저장본 적용 예정: ${{selectedProfile.name}}`
                    : (promptValue ? "직접 입력 적용 예정" : "추가 지침 없음");
                basePreview.value = buildBasePrompt(settings);
                effectivePreview.value = buildEffectivePrompt(settings, promptValue);
            }}

            function loadEditorState(selectedProfileId = "") {{
                const settings = readSettings();
                const profiles = normalizePromptProfiles(settings.prompt_profiles);
                const activeProfile = resolveActiveProfile(settings, profiles);
                renderProfileOptions(settings, selectedProfileId || (activeProfile && activeProfile.id) || "");

                const selectedProfile = profiles.find((profile) => profile.id === normalizeProfileId(profileSelect.value)) || null;
                if (selectedProfile) {{
                    profileNameInput.value = selectedProfile.name;
                    input.value = selectedProfile.prompt;
                }} else {{
                    profileNameInput.value = "";
                    input.value = resolveDirectPrompt(settings);
                }}

                deleteButton.disabled = !selectedProfile;
                updatePreview(settings);
                updateStatus(
                    input.value
                        ? `현재 추가 지침 ${{input.value.length}}자`
                        : "기본 시스템 프롬프트만 사용 중",
                );
                updateProfileStatus(
                    selectedProfile
                        ? `선택 저장본: ${{selectedProfile.name}}`
                        : `저장본 ${{profiles.length}}개 / 직접 입력`,
                );
            }}

            async function saveCurrentPrompt() {{
                const settings = readSettings();
                const profiles = normalizePromptProfiles(settings.prompt_profiles);
                const selectedProfileId = normalizeProfileId(profileSelect.value);
                const prompt = normalizePrompt(input.value);
                const name = normalizeProfileName(profileNameInput.value);

                if (selectedProfileId) {{
                    const nextProfiles = profiles.map((profile) => (
                        profile.id === selectedProfileId
                            ? {{
                                ...profile,
                                name: name || profile.name,
                                prompt,
                                updated_at: new Date().toISOString(),
                            }}
                            : profile
                    ));
                    try {{
                        await writeSettings({{
                            ...settings,
                            prompt_profiles: nextProfiles,
                            active_prompt_profile_id: selectedProfileId,
                            direct_system_prompt: resolveDirectPrompt(settings),
                            system_prompt: prompt,
                        }});
                    }} catch (error) {{
                        loadEditorState(selectedProfileId);
                        updateStatus("브라우저 저장됨 · repo 저장 실패", "error");
                        updateProfileStatus("공유 프롬프트 파일 저장 실패", "error");
                        return;
                    }}
                    loadEditorState(selectedProfileId);
                    updateStatus(`저장됨 · ${{prompt.length}}자`, "success");
                    updateProfileStatus(`저장본 업데이트: ${{name || "이름 없음"}}`, "success");
                    return;
                }}

                try {{
                    await writeSettings({{
                        ...settings,
                        active_prompt_profile_id: "",
                        direct_system_prompt: prompt,
                        system_prompt: prompt,
                    }});
                }} catch (error) {{
                    loadEditorState("");
                    updateStatus("브라우저 저장됨 · repo 저장 실패", "error");
                    updateProfileStatus("공유 프롬프트 파일 저장 실패", "error");
                    return;
                }}
                loadEditorState("");
                updateStatus(prompt ? `직접 입력 저장됨 · ${{prompt.length}}자` : "기본 시스템 프롬프트만 사용 중", "success");
                updateProfileStatus("직접 입력 적용", "success");
            }}

            async function saveAsNewProfile() {{
                const settings = readSettings();
                const profiles = normalizePromptProfiles(settings.prompt_profiles);
                const prompt = normalizePrompt(input.value);
                const name = normalizeProfileName(profileNameInput.value) || `저장본 ${{profiles.length + 1}}`;
                const newProfileId = createProfileId();
                const nextProfiles = [
                    ...profiles,
                    {{
                        id: newProfileId,
                        name,
                        prompt,
                        updated_at: new Date().toISOString(),
                    }},
                ];

                try {{
                    await writeSettings({{
                        ...settings,
                        prompt_profiles: nextProfiles,
                        active_prompt_profile_id: newProfileId,
                        direct_system_prompt: resolveDirectPrompt(settings),
                        system_prompt: prompt,
                    }});
                }} catch (error) {{
                    loadEditorState(newProfileId);
                    updateStatus("브라우저 저장됨 · repo 저장 실패", "error");
                    updateProfileStatus("공유 프롬프트 파일 저장 실패", "error");
                    return;
                }}
                loadEditorState(newProfileId);
                updateStatus(`새 저장본 저장됨 · ${{prompt.length}}자`, "success");
                updateProfileStatus(`저장본 생성: ${{name}}`, "success");
            }}

            async function deleteSelectedProfile() {{
                const settings = readSettings();
                const profiles = normalizePromptProfiles(settings.prompt_profiles);
                const selectedProfileId = normalizeProfileId(profileSelect.value);
                if (!selectedProfileId) {{
                    updateProfileStatus("삭제할 저장본이 없습니다.", "error");
                    return;
                }}

                const nextProfiles = profiles.filter((profile) => profile.id !== selectedProfileId);
                const directPrompt = resolveDirectPrompt(settings);
                try {{
                    await writeSettings({{
                        ...settings,
                        prompt_profiles: nextProfiles,
                        active_prompt_profile_id: "",
                        direct_system_prompt: directPrompt,
                        system_prompt: directPrompt,
                    }});
                }} catch (error) {{
                    loadEditorState("");
                    updateStatus("브라우저 저장됨 · repo 저장 실패", "error");
                    updateProfileStatus("공유 프롬프트 파일 저장 실패", "error");
                    return;
                }}
                loadEditorState("");
                updateStatus(
                    directPrompt
                        ? `직접 입력 유지 · ${{directPrompt.length}}자`
                        : "기본 시스템 프롬프트만 사용 중",
                    "success",
                );
                updateProfileStatus("저장본 삭제 완료", "success");
            }}

            function clearCurrentPrompt() {{
                input.value = "";
                updatePreview(readSettings());
                updateStatus("현재 입력 비움");
            }}

            serverPromptSettings = normalizePromptSettings(window.KEYWORD_FORGE_TITLE_PROMPT_SETTINGS || {{}});

            saveButton.addEventListener("click", () => {{
                void saveCurrentPrompt();
            }});
            saveAsButton.addEventListener("click", () => {{
                void saveAsNewProfile();
            }});
            deleteButton.addEventListener("click", () => {{
                void deleteSelectedProfile();
            }});
            clearButton.addEventListener("click", () => {{
                clearCurrentPrompt();
            }});
            closeButton.addEventListener("click", () => {{
                window.close();
            }});
            profileSelect.addEventListener("change", () => {{
                loadEditorState(profileSelect.value);
            }});
            input.addEventListener("input", () => {{
                updatePreview(readSettings());
                updateStatus(
                    input.value
                        ? `현재 추가 지침 ${{normalizePrompt(input.value).length}}자`
                        : "기본 시스템 프롬프트만 사용 중",
                );
            }});
            input.addEventListener("keydown", (event) => {{
                if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {{
                    event.preventDefault();
                    void saveCurrentPrompt();
                }}
            }});

            loadEditorState();
            if (!hasMeaningfulPromptSettings(serverPromptSettings)) {{
                const initialSettings = readSettings();
                if (hasMeaningfulPromptSettings(initialSettings)) {{
                    void writeSettings(initialSettings).catch(() => {{}});
                }}
            }}
        }})();
    </script>
    """
    return _render_static_shell(
        title="제목 프롬프트 편집",
        description="AI 제목 생성용 추가 시스템 프롬프트를 수정합니다.",
        body=body,
    )


def _render_title_quality_prompt_editor() -> str:
    default_evaluation_prompt_payload = json.dumps(
        DEFAULT_TITLE_EVALUATION_PROMPT,
        ensure_ascii=False,
    ).replace("</", "<\\/")
    title_prompt_settings_payload = json.dumps(get_title_prompt_settings(), ensure_ascii=False).replace("</", "<\\/")
    body = f"""
    <script>
        window.KEYWORD_FORGE_TITLE_DEFAULT_EVALUATION_PROMPT = {default_evaluation_prompt_payload};
        window.KEYWORD_FORGE_TITLE_PROMPT_SETTINGS = {title_prompt_settings_payload};
    </script>
    <main class="doc-shell title-prompt-shell">
        <div class="doc-stack">
            <section class="doc-hero doc-hero-compact">
                <div class="doc-breadcrumbs">
                    <a href="/">키워드 작업대</a>
                    <span>/</span>
                    <span>홈판 평가 프롬프트</span>
                </div>
                <div class="doc-hero-copy">
                    <p class="panel-kicker">홈판 평가</p>
                    <h1>홈판 제목 평가 프롬프트 관리</h1>
                    <p>
                        네이버 홈판 제목 평가 규칙만 따로 관리합니다.
                        저장본을 만들면 홈 화면의 평가 프롬프트 선택기에서 바로 고를 수 있고,
                        저장 후 제목 평가에 즉시 반영됩니다.
                    </p>
                </div>
                <div class="title-prompt-guide">
                    <div class="title-prompt-guide-card">
                        <strong>적용 범위</strong>
                        <p>홈판 CTR 평가에만 적용됩니다. 워드프레스형 블로그 평가는 기존 규칙을 그대로 사용합니다.</p>
                    </div>
                    <div class="title-prompt-guide-card">
                        <strong>권장 사용법</strong>
                        <p>새 규칙은 먼저 직접 입력으로 시험하고, 안정화되면 저장본으로 이름을 붙여 관리하세요.</p>
                    </div>
                </div>
            </section>

            <section class="panel">
                <div class="panel-head">
                    <div>
                        <p class="panel-kicker">미리보기</p>
                        <h2>현재 적용 평가 프롬프트</h2>
                    </div>
                    <span class="status-pill" id="titleQualityPromptEditorStatus">불러오는 중</span>
                </div>
                <div class="form-grid">
                    <div class="field-block">
                        <span class="field-label">현재 적용 저장본</span>
                        <div id="titleQualityPromptAppliedProfile" class="title-prompt-summary">불러오는 중</div>
                    </div>
                    <label class="field-block field-block-wide">
                        <span class="field-label">현재 적용 프롬프트</span>
                        <textarea
                            id="titleQualityPromptPreview"
                            class="title-prompt-textarea"
                            rows="18"
                            readonly
                        ></textarea>
                    </label>
                </div>
            </section>

            <section class="panel">
                <div class="panel-head">
                    <div>
                        <p class="panel-kicker">저장본</p>
                        <h2>홈판 평가 프롬프트 편집</h2>
                    </div>
                    <span class="status-pill" id="titleQualityPromptProfileStatus">저장본 불러오는 중</span>
                </div>
                <div class="form-grid">
                    <label class="field-block">
                        <span class="field-label">저장본 선택</span>
                        <select id="titleQualityPromptProfileSelect"></select>
                    </label>
                    <label class="field-block">
                        <span class="field-label">저장본 이름</span>
                        <input
                            id="titleQualityPromptProfileName"
                            type="text"
                            maxlength="40"
                            placeholder="예: 홈판 CTR v2"
                        />
                    </label>
                </div>
                <label class="field-block field-block-wide">
                    <span class="field-label">평가 프롬프트 편집</span>
                    <textarea
                        id="titleQualityPromptEditorInput"
                        class="title-prompt-textarea"
                        rows="18"
                        placeholder="홈판 제목 평가 규칙을 입력하세요."
                    ></textarea>
                </label>
                <p class="input-help compact-help">
                    저장본을 고른 상태에서 저장하면 해당 저장본이 수정되고,
                    저장본을 고르지 않으면 현재 입력값이 직접 입력 프롬프트로 적용됩니다.
                </p>
                <div class="doc-actions title-prompt-actions">
                    <button type="button" class="subtle-btn" id="saveTitleQualityPromptButton">현재 적용 저장</button>
                    <button type="button" class="ghost-btn" id="saveAsTitleQualityPromptButton">새 저장본</button>
                    <button type="button" class="ghost-btn" id="deleteTitleQualityPromptButton">저장본 삭제</button>
                    <button type="button" class="ghost-btn" id="resetTitleQualityPromptEditorButton">기본값 복원</button>
                    <button type="button" class="ghost-chip" id="closeTitleQualityPromptEditorButton">창 닫기</button>
                </div>
            </section>
        </div>
    </main>
    <script>
        (function() {{
            const STORAGE_KEY = "keyword_forge_title_settings";
            const PROMPT_SETTINGS_ENDPOINT = "/settings/title-prompt";
            const DEFAULT_PROMPT = String(window.KEYWORD_FORGE_TITLE_DEFAULT_EVALUATION_PROMPT || "")
                .replace(/\\r\\n/g, "\\n")
                .trim();
            const input = document.getElementById("titleQualityPromptEditorInput");
            const status = document.getElementById("titleQualityPromptEditorStatus");
            const profileStatus = document.getElementById("titleQualityPromptProfileStatus");
            const profileSelect = document.getElementById("titleQualityPromptProfileSelect");
            const profileNameInput = document.getElementById("titleQualityPromptProfileName");
            const appliedProfile = document.getElementById("titleQualityPromptAppliedProfile");
            const preview = document.getElementById("titleQualityPromptPreview");
            const saveButton = document.getElementById("saveTitleQualityPromptButton");
            const saveAsButton = document.getElementById("saveAsTitleQualityPromptButton");
            const deleteButton = document.getElementById("deleteTitleQualityPromptButton");
            const resetButton = document.getElementById("resetTitleQualityPromptEditorButton");
            const closeButton = document.getElementById("closeTitleQualityPromptEditorButton");
            let serverPromptSettings = {{}};
            let promptSettingsSyncSequence = 0;

            function readStoredSettings() {{
                try {{
                    return JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "{{}}");
                }} catch (error) {{
                    return {{}};
                }}
            }}

            function normalizePrompt(value) {{
                return String(value || "").replace(/\\r\\n/g, "\\n").trim();
            }}

            function normalizeProfileId(value) {{
                return String(value || "").trim();
            }}

            function normalizeProfileName(value) {{
                return String(value || "").replace(/\\s+/g, " ").trim();
            }}

            function normalizeProfiles(value) {{
                if (!Array.isArray(value)) {{
                    return [];
                }}
                const seenIds = new Set();
                const output = [];
                value.forEach((item, index) => {{
                    if (!item || typeof item !== "object") {{
                        return;
                    }}
                    const id = normalizeProfileId(item.id || `quality-profile-${{index + 1}}`);
                    if (!id || seenIds.has(id)) {{
                        return;
                    }}
                    seenIds.add(id);
                    output.push({{
                        id,
                        name: normalizeProfileName(item.name || `저장본 ${{output.length + 1}}`),
                        prompt: normalizePrompt(item.prompt),
                        updated_at: String(item.updated_at || "").trim(),
                    }});
                }});
                return output;
            }}

            function resolveActiveProfile(settings, profiles = normalizeProfiles(settings.evaluation_prompt_profiles)) {{
                const activeProfileId = normalizeProfileId(settings.active_evaluation_prompt_profile_id);
                return profiles.find((profile) => profile.id === activeProfileId) || null;
            }}

            function resolveDirectPrompt(settings) {{
                const directPrompt = normalizePrompt(settings.evaluation_direct_prompt);
                if (directPrompt) {{
                    return directPrompt;
                }}
                return normalizePrompt(settings.evaluation_prompt) || DEFAULT_PROMPT;
            }}

            function normalizePromptSettings(settings) {{
                const source = settings && typeof settings === "object" ? settings : {{}};
                const profiles = normalizeProfiles(source.evaluation_prompt_profiles);
                const activeProfile = resolveActiveProfile(source, profiles);
                const directPrompt = normalizePrompt(
                    source.evaluation_direct_prompt || (activeProfile ? "" : source.evaluation_prompt),
                ) || DEFAULT_PROMPT;
                return {{
                    evaluation_direct_prompt: activeProfile ? "" : directPrompt,
                    evaluation_prompt: activeProfile ? activeProfile.prompt : directPrompt,
                    evaluation_prompt_profiles: profiles,
                    active_evaluation_prompt_profile_id: activeProfile ? activeProfile.id : "",
                }};
            }}

            function readSettings() {{
                const storedSettings = readStoredSettings();
                const localPromptSettings = normalizePromptSettings(storedSettings);
                const effectivePromptSettings = {{
                    ...localPromptSettings,
                    ...normalizePromptSettings(serverPromptSettings),
                }};
                return {{
                    ...storedSettings,
                    ...effectivePromptSettings,
                }};
            }}

            async function writeSettings(settings) {{
                const nextSettings = settings && typeof settings === "object" ? {{ ...settings }} : {{}};
                const normalizedPromptSettings = normalizePromptSettings(nextSettings);
                const mergedSettings = {{
                    ...nextSettings,
                    ...normalizedPromptSettings,
                }};
                window.localStorage.setItem(STORAGE_KEY, JSON.stringify(mergedSettings));

                serverPromptSettings = normalizedPromptSettings;
                window.KEYWORD_FORGE_TITLE_PROMPT_SETTINGS = {{
                    ...(window.KEYWORD_FORGE_TITLE_PROMPT_SETTINGS || {{}}),
                    ...normalizedPromptSettings,
                }};

                const syncId = ++promptSettingsSyncSequence;
                const response = await fetch(PROMPT_SETTINGS_ENDPOINT, {{
                    method: "POST",
                    headers: {{
                        "Content-Type": "application/json",
                    }},
                    body: JSON.stringify(normalizedPromptSettings),
                }});
                if (!response.ok) {{
                    throw new Error(`title_quality_prompt_sync_failed:${{response.status}}`);
                }}
                const payload = await response.json();
                const savedPromptSettings = normalizePromptSettings(
                    payload && payload.title_prompt_settings ? payload.title_prompt_settings : normalizedPromptSettings,
                );
                serverPromptSettings = savedPromptSettings;
                window.KEYWORD_FORGE_TITLE_PROMPT_SETTINGS = {{
                    ...(window.KEYWORD_FORGE_TITLE_PROMPT_SETTINGS || {{}}),
                    ...savedPromptSettings,
                }};
                if (syncId === promptSettingsSyncSequence) {{
                    const latestLocalSettings = readStoredSettings();
                    window.localStorage.setItem(
                        STORAGE_KEY,
                        JSON.stringify({{
                            ...latestLocalSettings,
                            ...savedPromptSettings,
                        }}),
                    );
                }}
                return savedPromptSettings;
            }}

            function createProfileId() {{
                return `quality-profile-${{Date.now()}}-${{Math.random().toString(36).slice(2, 8)}}`;
            }}

            function updateStatus(message, kind) {{
                status.textContent = message;
                status.classList.remove("success", "error");
                if (kind) {{
                    status.classList.add(kind);
                }}
            }}

            function updateProfileStatus(message, kind) {{
                profileStatus.textContent = message;
                profileStatus.classList.remove("success", "error");
                if (kind) {{
                    profileStatus.classList.add(kind);
                }}
            }}

            function renderProfileOptions(settings, selectedProfileId = "") {{
                const profiles = normalizeProfiles(settings.evaluation_prompt_profiles);
                const activeProfileId = normalizeProfileId(
                    selectedProfileId || settings.active_evaluation_prompt_profile_id,
                );
                profileSelect.innerHTML = "";

                const directOption = document.createElement("option");
                directOption.value = "";
                directOption.textContent = profiles.length ? "직접 입력" : "직접 입력 (저장본 없음)";
                profileSelect.appendChild(directOption);

                profiles.forEach((profile) => {{
                    const option = document.createElement("option");
                    option.value = profile.id;
                    option.textContent = profile.name;
                    profileSelect.appendChild(option);
                }});

                profileSelect.value = activeProfileId;
                if (profileSelect.value !== activeProfileId) {{
                    profileSelect.value = "";
                }}
            }}

            function updatePreview(settings) {{
                const profiles = normalizeProfiles(settings.evaluation_prompt_profiles);
                const selectedProfile = profiles.find((profile) => profile.id === normalizeProfileId(profileSelect.value)) || null;
                const promptValue = normalizePrompt(input.value) || DEFAULT_PROMPT;
                appliedProfile.textContent = selectedProfile
                    ? `저장본 적용 중: ${{selectedProfile.name}}`
                    : "직접 입력 적용 중";
                preview.value = promptValue;
                deleteButton.disabled = !selectedProfile;
            }}

            function loadEditorState(selectedProfileId = "") {{
                const settings = readSettings();
                const profiles = normalizeProfiles(settings.evaluation_prompt_profiles);
                const activeProfile = resolveActiveProfile(settings, profiles);
                renderProfileOptions(settings, selectedProfileId || (activeProfile && activeProfile.id) || "");

                const selectedProfile = profiles.find((profile) => profile.id === normalizeProfileId(profileSelect.value)) || null;
                if (selectedProfile) {{
                    profileNameInput.value = selectedProfile.name;
                    input.value = selectedProfile.prompt;
                }} else {{
                    profileNameInput.value = "";
                    input.value = resolveDirectPrompt(settings);
                }}

                updatePreview(settings);
                updateStatus(
                    input.value
                        ? `현재 평가 프롬프트 ${{normalizePrompt(input.value).length}}자`
                        : "기본 홈판 평가 프롬프트 사용 중",
                );
                updateProfileStatus(
                    selectedProfile
                        ? `선택 저장본: ${{selectedProfile.name}}`
                        : `저장본 ${{profiles.length}}개 / 직접 입력`,
                );
            }}

            async function saveCurrentPrompt() {{
                const settings = readSettings();
                const profiles = normalizeProfiles(settings.evaluation_prompt_profiles);
                const selectedProfileId = normalizeProfileId(profileSelect.value);
                const prompt = normalizePrompt(input.value) || DEFAULT_PROMPT;
                const name = normalizeProfileName(profileNameInput.value);

                if (selectedProfileId) {{
                    const nextProfiles = profiles.map((profile) => (
                        profile.id === selectedProfileId
                            ? {{
                                ...profile,
                                name: name || profile.name,
                                prompt,
                                updated_at: new Date().toISOString(),
                            }}
                            : profile
                    ));
                    try {{
                        await writeSettings({{
                            ...settings,
                            evaluation_prompt_profiles: nextProfiles,
                            active_evaluation_prompt_profile_id: selectedProfileId,
                            evaluation_direct_prompt: "",
                            evaluation_prompt: prompt,
                        }});
                    }} catch (error) {{
                        loadEditorState(selectedProfileId);
                        updateStatus("브라우저/서버 저장에 실패했습니다.", "error");
                        updateProfileStatus("공유 설정 저장 실패", "error");
                        return;
                    }}
                    loadEditorState(selectedProfileId);
                    updateStatus(`저장 완료 / ${{prompt.length}}자`, "success");
                    updateProfileStatus(`저장본 업데이트: ${{name || "이름 없음"}}`, "success");
                    return;
                }}

                try {{
                    await writeSettings({{
                        ...settings,
                        active_evaluation_prompt_profile_id: "",
                        evaluation_direct_prompt: prompt,
                        evaluation_prompt: prompt,
                    }});
                }} catch (error) {{
                    loadEditorState("");
                    updateStatus("브라우저/서버 저장에 실패했습니다.", "error");
                    updateProfileStatus("공유 설정 저장 실패", "error");
                    return;
                }}
                loadEditorState("");
                updateStatus(
                    prompt === DEFAULT_PROMPT
                        ? "기본 홈판 평가 프롬프트로 적용했습니다."
                        : `직접 입력 저장 완료 / ${{prompt.length}}자`,
                    "success",
                );
                updateProfileStatus("직접 입력 적용", "success");
            }}

            async function saveAsNewProfile() {{
                const settings = readSettings();
                const profiles = normalizeProfiles(settings.evaluation_prompt_profiles);
                const prompt = normalizePrompt(input.value) || DEFAULT_PROMPT;
                const name = normalizeProfileName(profileNameInput.value) || `저장본 ${{profiles.length + 1}}`;
                const newProfileId = createProfileId();
                const nextProfiles = [
                    ...profiles,
                    {{
                        id: newProfileId,
                        name,
                        prompt,
                        updated_at: new Date().toISOString(),
                    }},
                ];

                try {{
                    await writeSettings({{
                        ...settings,
                        evaluation_prompt_profiles: nextProfiles,
                        active_evaluation_prompt_profile_id: newProfileId,
                        evaluation_direct_prompt: "",
                        evaluation_prompt: prompt,
                    }});
                }} catch (error) {{
                    loadEditorState(newProfileId);
                    updateStatus("브라우저/서버 저장에 실패했습니다.", "error");
                    updateProfileStatus("공유 설정 저장 실패", "error");
                    return;
                }}
                loadEditorState(newProfileId);
                updateStatus(`새 저장본 저장 완료 / ${{prompt.length}}자`, "success");
                updateProfileStatus(`저장본 생성: ${{name}}`, "success");
            }}

            async function deleteSelectedProfile() {{
                const settings = readSettings();
                const profiles = normalizeProfiles(settings.evaluation_prompt_profiles);
                const selectedProfileId = normalizeProfileId(profileSelect.value);
                if (!selectedProfileId) {{
                    updateProfileStatus("삭제할 저장본이 없습니다.", "error");
                    return;
                }}

                const nextProfiles = profiles.filter((profile) => profile.id !== selectedProfileId);
                try {{
                    await writeSettings({{
                        ...settings,
                        evaluation_prompt_profiles: nextProfiles,
                        active_evaluation_prompt_profile_id: "",
                        evaluation_direct_prompt: DEFAULT_PROMPT,
                        evaluation_prompt: DEFAULT_PROMPT,
                    }});
                }} catch (error) {{
                    loadEditorState("");
                    updateStatus("브라우저/서버 저장에 실패했습니다.", "error");
                    updateProfileStatus("공유 설정 저장 실패", "error");
                    return;
                }}
                loadEditorState("");
                updateStatus("기본 홈판 평가 프롬프트로 되돌렸습니다.", "success");
                updateProfileStatus("저장본 삭제 완료", "success");
            }}

            function resetToDefaultPrompt() {{
                profileSelect.value = "";
                profileNameInput.value = "";
                input.value = DEFAULT_PROMPT;
                updatePreview(readSettings());
                updateStatus("기본 홈판 평가 프롬프트로 되돌렸습니다.");
            }}

            serverPromptSettings = normalizePromptSettings(window.KEYWORD_FORGE_TITLE_PROMPT_SETTINGS || {{}});

            saveButton.addEventListener("click", () => {{
                void saveCurrentPrompt();
            }});
            saveAsButton.addEventListener("click", () => {{
                void saveAsNewProfile();
            }});
            deleteButton.addEventListener("click", () => {{
                void deleteSelectedProfile();
            }});
            resetButton.addEventListener("click", () => {{
                resetToDefaultPrompt();
            }});
            closeButton.addEventListener("click", () => {{
                window.close();
            }});
            profileSelect.addEventListener("change", () => {{
                loadEditorState(profileSelect.value);
            }});
            input.addEventListener("input", () => {{
                updatePreview(readSettings());
                updateStatus(`현재 평가 프롬프트 ${{normalizePrompt(input.value).length}}자`);
            }});
            input.addEventListener("keydown", (event) => {{
                if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {{
                    event.preventDefault();
                    void saveCurrentPrompt();
                }}
            }});

            loadEditorState();
        }})();
    </script>
    """
    return _render_static_shell(
        title="홈판 평가 프롬프트 편집",
        description="네이버 홈판 제목 평가 프롬프트를 저장본으로 관리합니다.",
        body=body,
    )


def _render_guides_index() -> str:
    guides = _load_study_guides()
    grouped: dict[str, list[dict[str, object]]] = {key: [] for key, _label, _keywords in _GUIDE_GROUPS}
    for guide in guides:
        grouped.setdefault(str(guide.get("group") or "discovery"), []).append(guide)

    sections: list[str] = []
    for key, label, _keywords in _GUIDE_GROUPS:
        cards = "".join(_render_guide_card(guide) for guide in grouped.get(key, []))
        sections.append(
            f"""
            <section class="doc-section">
                <div class="doc-section-head">
                    <p class="panel-kicker">가이드 묶음</p>
                    <h2>{escape(label)}</h2>
                </div>
                <div class="guide-card-grid">
                    {cards if cards else '<div class="placeholder">해당 분류의 문서가 없습니다.</div>'}
                </div>
            </section>
            """
        )

    return _render_static_shell(
        title="사용 가이드",
        description="Study 문서를 본 사이트 안에서 볼 수 있는 가이드 인덱스입니다.",
        body=f"""
        <div class="doc-shell">
            <header class="doc-hero">
                <div class="doc-breadcrumbs"><a href="/">홈</a><span>/</span><strong>사용 가이드</strong></div>
                <div class="doc-actions">
                    <a class="secondary-link" href="/">대시보드</a>
                    <a class="secondary-link" href="/api-docs" target="_blank" rel="noopener noreferrer">API 문서</a>
                </div>
                <div class="doc-hero-copy">
                    <p class="eyebrow">가이드</p>
                    <h1>Study 문서 모음</h1>
                    <p>기능 설명서와 운영 팁을 주제별로 묶었습니다. 각 문서는 본 사이트 안에서 바로 열립니다.</p>
                </div>
            </header>
            <main class="doc-stack">
                {''.join(sections)}
            </main>
        </div>
        """,
    )


def _render_guide_detail(guide_slug: str) -> str:
    guide = next((item for item in _load_study_guides() if str(item.get("slug")) == guide_slug), None)
    if guide is None:
        raise HTTPException(status_code=404, detail="가이드를 찾을 수 없습니다.")

    return _render_static_shell(
        title=str(guide["title"]),
        description=str(guide.get("subtitle") or ""),
        body=f"""
        <div class="doc-shell">
            <header class="doc-hero doc-hero-compact">
                <div class="doc-breadcrumbs">
                    <a href="/">홈</a><span>/</span><a href="/guides">사용 가이드</a><span>/</span><strong>{escape(str(guide['title']))}</strong>
                </div>
                <div class="doc-actions">
                    <a class="secondary-link" href="/guides">가이드 목록</a>
                    <a class="secondary-link" href="/">대시보드</a>
                </div>
                <div class="doc-hero-copy">
                    <p class="eyebrow">가이드 상세</p>
                    <h1>{escape(str(guide['title']))}</h1>
                    <p>{escape(str(guide.get('subtitle') or ''))}</p>
                </div>
            </header>
            <main class="doc-content">
                <article class="doc-article">
                    {str(guide.get("content_html") or "")}
                </article>
            </main>
        </div>
        """,
    )


def _render_recommended_usage() -> str:
    return _render_static_shell(
        title="추천 사용법",
        description="자동화 블로그 작성 흐름에 맞춘 키워드 포지 운영 방법을 정리했습니다.",
        body="""
        <div class="doc-shell">
            <header class="doc-hero">
                <div class="doc-breadcrumbs">
                    <a href="/">홈</a><span>/</span><strong>추천 사용법</strong>
                </div>
                <div class="doc-actions">
                    <a class="secondary-link" href="/">대시보드</a>
                    <a class="secondary-link" href="/guides">사용 가이드</a>
                </div>
                <div class="doc-hero-copy">
                    <p class="eyebrow">추천 사용법</p>
                    <h1>자동화 블로그 작성 기준 운영안</h1>
                    <p>
                        이 프로그램은 `돈 되는 키워드만 찾는 도구`로 보기보다
                        `글감 후보를 고르고, 제목 방향을 정하는 도구`로 쓰는 편이 더 잘 맞습니다.
                        제목만 자동 작성기로 넘겨 글을 만들고 있다면,
                        점수 하나보다 `무슨 글을 써야 하는지`가 제목에 분명히 담기는 것이 더 중요합니다.
                    </p>
                </div>
            </header>
            <main class="doc-stack">
                <section class="panel">
                    <div class="panel-head">
                        <div>
                            <p class="panel-kicker">한눈에 이해</p>
                            <h2>이 도구는 이렇게 생각하면 쉽습니다</h2>
                        </div>
                    </div>
                    <div class="guide-card-grid">
                        <article class="guide-article-card">
                            <div class="guide-article-head">
                                <h4>글감 후보를 추리는 단계</h4>
                                <p>수집과 확장으로 후보를 모으고, 분석과 선별로 지금 써 볼 만한 주제를 줄이는 단계입니다.</p>
                            </div>
                        </article>
                        <article class="guide-article-card">
                            <div class="guide-article-head">
                                <h4>제목 방향을 고정하는 단계</h4>
                                <p>제목은 단순 문장이 아니라 글의 방향을 정하는 장치입니다. 제목이 또렷해야 뒤의 자동 작성기도 덜 흔들립니다.</p>
                            </div>
                        </article>
                        <article class="guide-article-card">
                            <div class="guide-article-head">
                                <h4>혼자 쓰는 실무 도구</h4>
                                <p>남에게 보여주기 위한 서비스보다, 좋은 후보를 빠르게 걸러서 다음 단계로 넘기는 작업용 도구라고 생각하면 됩니다.</p>
                            </div>
                        </article>
                    </div>
                </section>

                <section class="panel">
                    <div class="panel-head">
                        <div>
                            <p class="panel-kicker">가장 쉬운 사용 순서</p>
                            <h2>처음에는 이 순서로 쓰면 됩니다</h2>
                        </div>
                    </div>
                    <ul class="guide-article-points">
                        <li><strong>1. 균형형으로 시작</strong><span>평소에는 `균형형`을 기본으로 돌리면 너무 공격적이지 않으면서도 쓸 만한 후보를 넓게 확보할 수 있습니다.</span></li>
                        <li><strong>2. 자동 선별 결과 확인</strong><span>수익형 후보만 보지 말고 `글감 후보`까지 같이 봐야 롱테일용 글을 놓치지 않습니다.</span></li>
                        <li><strong>3. 제목은 단일 + 롱테일 1단계 우선</strong><span>자동 작성기에 바로 넘길 때는 단일 키워드와 롱테일 1단계를 먼저 쓰는 편이 가장 안전합니다.</span></li>
                        <li><strong>4. 낮은 품질 제목은 자동 보정 결과만 확인</strong><span>기준 미달 제목은 내부에서 자동으로 다시 만들고, 2번 연속 미달이면 더 강한 생성기로 한 번 더 보정합니다.</span></li>
                    </ul>
                </section>

                <section class="panel">
                    <div class="panel-head">
                        <div>
                            <p class="panel-kicker">모드 선택</p>
                            <h2>상황별로 어떤 모드를 쓰면 좋은가</h2>
                        </div>
                    </div>
                    <div class="guide-card-grid">
                        <article class="guide-article-card">
                            <div class="guide-article-head">
                                <h4>균형형</h4>
                                <p>가장 기본입니다. 매일 돌리기 좋고, 자동 작성기에 넘길 후보를 안정적으로 모으는 데 적합합니다.</p>
                            </div>
                        </article>
                        <article class="guide-article-card">
                            <div class="guide-article-head">
                                <h4>수익형</h4>
                                <p>광고 단가나 수익 가능성을 더 중시할 때 씁니다. 매일 기본값으로 두기보다 따로 묶어서 보는 용도가 좋습니다.</p>
                            </div>
                        </article>
                        <article class="guide-article-card">
                            <div class="guide-article-head">
                                <h4>롱테일 탐색형</h4>
                                <p>수익성이 약해도 누군가에게 필요한 주제를 찾는 모드입니다. 글감 채우기와 커버리지 확보용으로 좋습니다.</p>
                            </div>
                        </article>
                    </div>
                </section>

                <section class="panel">
                    <div class="panel-head">
                        <div>
                            <p class="panel-kicker">제목 운영</p>
                            <h2>자동 작성기에 넘길 제목은 이렇게 고르세요</h2>
                        </div>
                    </div>
                    <div class="guide-card-grid">
                        <article class="guide-article-card">
                            <div class="guide-article-head">
                                <h4>단일 키워드</h4>
                                <p>가장 단순하고 안전합니다. 글의 주제가 흔들리면 안 되는 자동 작성 흐름에서 기본값으로 좋습니다.</p>
                            </div>
                        </article>
                        <article class="guide-article-card">
                            <div class="guide-article-head">
                                <h4>롱테일 1단계</h4>
                                <p>선별된 키워드를 바탕으로 만든 첫 번째 롱테일입니다. 지금 구조에서는 자동 작성기에 바로 넘기기 가장 좋은 롱테일입니다.</p>
                            </div>
                        </article>
                        <article class="guide-article-card">
                            <div class="guide-article-head">
                                <h4>롱테일 2~3단계</h4>
                                <p>아이디어를 넓히는 데는 좋지만, 자동 작성기에 바로 넣기에는 노이즈가 더 많을 수 있습니다. 검토용으로 먼저 보는 편이 안전합니다.</p>
                            </div>
                        </article>
                        <article class="guide-article-card">
                            <div class="guide-article-head">
                                <h4>규칙형과 인공지능 생성</h4>
                                <p>빠르고 일정한 결과가 필요하면 규칙형, 조금 더 다양한 제목이 필요하면 인공지능 생성을 쓰면 됩니다. 자동화 본선은 안정성이 우선입니다.</p>
                            </div>
                        </article>
                    </div>
                </section>

                <section class="panel">
                    <div class="panel-head">
                        <div>
                            <p class="panel-kicker">자동 보정</p>
                            <h2>제목 품질이 낮게 나와도 사용자는 중간 개입이 거의 필요 없습니다</h2>
                        </div>
                    </div>
                    <div class="guide-card-grid">
                        <article class="guide-article-card">
                            <div class="guide-article-head">
                                <h4>자동 재작성</h4>
                                <p>제목 품질이 기준보다 낮으면 내부에서 자동으로 다시 만듭니다. 사용자가 다시 누르지 않아도 됩니다.</p>
                            </div>
                        </article>
                        <article class="guide-article-card">
                            <div class="guide-article-head">
                                <h4>더 강한 생성기로 한 번 더 시도</h4>
                                <p>두 번 연속으로 기준에 못 미치면 더 강한 생성기로 한 번 더 시도합니다. 사용자는 최종 결과만 확인하면 됩니다.</p>
                            </div>
                        </article>
                        <article class="guide-article-card">
                            <div class="guide-article-head">
                                <h4>그래도 애매하면</h4>
                                <p>같은 키워드로 무한 재생성하기보다, 키워드 각도나 롱테일 단계 자체를 바꾸는 편이 더 효과적입니다.</p>
                            </div>
                        </article>
                    </div>
                </section>

                <section class="panel">
                    <div class="panel-head">
                        <div>
                            <p class="panel-kicker">권장 루틴</p>
                            <h2>혼자 쓸 때 가장 현실적인 운영안</h2>
                        </div>
                    </div>
                    <ul class="guide-article-points">
                        <li><strong>매일 1회 균형형</strong><span>기본 생산 라인으로 사용합니다.</span></li>
                        <li><strong>매일 1회 롱테일 탐색형</strong><span>필요 글과 틈새 주제를 채우는 용도로 봅니다.</span></li>
                        <li><strong>주 2~3회 수익형</strong><span>수익성 높은 묶음이 필요할 때만 추가로 돌립니다.</span></li>
                        <li><strong>자동 작성기 전송 기준</strong><span>단일 키워드와 롱테일 1단계를 먼저 쓰고, 나머지는 검토 후 넣습니다.</span></li>
                        <li><strong>최신 이슈형 제목은 따로 확인</strong><span>본문 작성기가 사실 확인을 못 하면 최신 이슈형 제목은 바로 발행하지 않는 편이 안전합니다.</span></li>
                    </ul>
                </section>

                <section class="panel">
                    <div class="panel-head">
                        <div>
                            <p class="panel-kicker">다음 확장 추천</p>
                            <h2>너 혼자 쓸 때 먼저 붙이면 좋은 최소 기능</h2>
                        </div>
                    </div>
                    <div class="guide-card-grid">
                        <article class="guide-article-card">
                            <div class="guide-article-head">
                                <h4>1순위: 실행 기록과 재실행</h4>
                                <p>어떤 시드, 어떤 모드, 어떤 제목 설정이 잘 먹혔는지 남겨 두고 다시 돌릴 수 있으면 실험이 자산이 됩니다.</p>
                            </div>
                        </article>
                        <article class="guide-article-card">
                            <div class="guide-article-head">
                                <h4>2순위: 키워드 보관함</h4>
                                <p>좋았던 후보를 `보류`, `발행완료`, `다시볼 것`처럼 묶어 두면 중복 발행과 같은 고민을 줄일 수 있습니다.</p>
                            </div>
                        </article>
                        <article class="guide-article-card">
                            <div class="guide-article-head">
                                <h4>3순위: 주제에서 시드 자동 만들기</h4>
                                <p>시드가 떠오르지 않을 때 주제만 넣고 첫 후보 묶음을 자동으로 만들면 탐색 속도가 빨라집니다.</p>
                            </div>
                        </article>
                    </div>
                </section>
            </main>
        </div>
        """,
    )


def _render_home() -> str:
    category_options = _render_category_options()
    queue_routine_category_picker = _render_queue_routine_category_picker()
    category_source_options = "".join(
        f'<option value="{source}"{" selected" if source == DEFAULT_CATEGORY_SOURCE else ""}>'
        f'{"네이버 트렌드" if source == "naver_trend" else "검색 예비안"}'
        "</option>"
        for source in CATEGORY_SOURCE_CHOICES
    )
    trend_service_options = "".join(
        f'<option value="{service}"{" selected" if service == DEFAULT_TREND_SERVICE else ""}>'
        f'{"네이버 블로그" if service == "naver_blog" else "인플루언서"}'
        "</option>"
        for service in TREND_SERVICE_CHOICES
    )
    title_presets = build_title_preset_payload()
    title_issue_source_modes = build_issue_source_mode_payload()
    title_community_sources = build_community_source_payload()
    title_preset_options = "".join(
        f'<option value="{escape(str(item["key"]))}"{" selected" if item["key"] == DEFAULT_TITLE_PRESET_KEY else ""}>'
        f'{escape(str(item["label"]))}'
        "</option>"
        for item in title_presets
    )
    title_issue_source_mode_options = _render_title_issue_source_mode_options()
    title_community_source_chips = _render_title_community_source_chips()
    title_preset_payload = json.dumps(title_presets, ensure_ascii=False).replace("</", "<\\/")
    title_issue_source_payload = json.dumps(title_issue_source_modes, ensure_ascii=False).replace("</", "<\\/")
    title_community_source_payload = json.dumps(title_community_sources, ensure_ascii=False).replace("</", "<\\/")
    title_prompt_settings_payload = json.dumps(get_title_prompt_settings(), ensure_ascii=False).replace("</", "<\\/")
    default_evaluation_prompt_payload = json.dumps(
        DEFAULT_TITLE_EVALUATION_PROMPT,
        ensure_ascii=False,
    ).replace("</", "<\\/")
    title_mode_help = _render_help_tooltip(
        "template는 규칙 기반으로 바로 생성합니다.\n"
        "AI는 provider/model을 사용해 더 유연하게 생성하고, 저점수 자동 재작성도 함께 쓸 수 있습니다.\n"
        "Vertex AI는 Express Mode API key로 붙이면 Google Cloud 크레딧/쿼터 체계로 운용할 수 있습니다."
    )
    title_keyword_modes_help = _render_help_tooltip(
        "단일은 안전형입니다.\n"
        "V1은 선별 결과 기반 롱테일입니다.\n"
        "V2는 관련 탈락 키워드 연계 확장입니다.\n"
        "V3는 저검색량까지 넓히는 실험형입니다."
    )
    title_surface_help = _render_help_tooltip(
        "홈판, 블로그형, 둘다를 각각 켜고 끌 수 있습니다.\n"
        "켜진 영역은 1개부터 4개까지 개수를 따로 정합니다.\n"
        "둘다는 홈 유입과 블로그 검색을 함께 노리는 공용형 제목입니다."
    )
    title_auto_retry_help = _render_help_tooltip(
        "AI 모드에서 품질 점수가 기준보다 낮은 제목은 자동으로 다시 생성합니다.\n"
        "2회 연속 기준 미달이면 더 강한 모델로 자동 승격해 한 번 더 보정합니다.\n"
        "기준 점수를 올리면 더 엄격하게 다시 쓰고, 너무 높이면 호출량과 시간이 늘어납니다."
    )
    title_issue_context_help = _render_help_tooltip(
        "AI 제목 생성 직전에 네이버 검색 상위 결과를 확인해 최근 뉴스/이슈 표현을 프롬프트에 반영합니다.\n"
        "조회 개수는 이번 호출에서 실시간 맥락을 붙일 키워드 수입니다. 높일수록 느려질 수 있습니다.\n"
        "반응형을 고르면 선택한 커뮤니티 도메인 제목만 따로 압축해 프롬프트에 붙입니다."
    )
    title_api_key_help = _render_help_tooltip(
        "API 키는 서버에 저장하지 않고 현재 브라우저 localStorage에만 보관합니다.\n"
        "Gemini는 Google AI Studio 키, Vertex AI는 Express Mode API key를 사용합니다."
    )
    title_prompt_help = _render_help_tooltip(
        "새 탭에서 제목 생성용 추가 지침을 수정합니다. 저장하면 현재 작업대에 바로 반영됩니다."
    )
    title_quality_prompt_help = _render_help_tooltip(
        '홈판 제목 평가 기준을 직접 수정합니다.' + "\n"
        '저장본으로 관리하면 테스트마다 빠르게 바꿔가며 비교할 수 있습니다.' + "\n"
        '이 프롬프트는 홈판 평가에만 적용되고 워드프레스형 블로그 평가는 그대로 유지됩니다.'
    )
    creator_login_help = _render_help_tooltip(
        "먼저 이 페이지를 연 브라우저에서 네이버 로그인 후 세션을 불러오세요." + "\n"
        "같은 브라우저에서 바로 가져오는 방식이 우선이며, 그게 막힐 때만 전용 로그인 브라우저를 여는 흐름을 권장합니다."
    )

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>수익형 키워드 발굴&amp;제목 생성기</title>
    <meta
        name="description"
        content="수익형 키워드를 수집, 확장, 분석, 선별하고 제목까지 생성하는 로컬 도구"
    />
    <script>
        window.KEYWORD_FORGE_TITLE_PRESETS = {title_preset_payload};
        window.KEYWORD_FORGE_TITLE_ISSUE_SOURCE_MODES = {title_issue_source_payload};
        window.KEYWORD_FORGE_TITLE_COMMUNITY_SOURCES = {title_community_source_payload};
        window.KEYWORD_FORGE_TITLE_PROMPT_SETTINGS = {title_prompt_settings_payload};
        window.KEYWORD_FORGE_TITLE_DEFAULT_EVALUATION_PROMPT = {default_evaluation_prompt_payload};
    </script>
    <link rel="stylesheet" href="/assets/app.css?v={_ASSET_VERSION}" />
    <script src="/assets/app.js?v={_ASSET_VERSION}" defer></script>
    <script src="/assets/app_workflow_utils.js?v={_ASSET_VERSION}" defer></script>
    <script src="/assets/app_overrides.js?v={_ASSET_VERSION}" defer></script>
</head>
<body>
    <div class="bg-orb bg-orb-a"></div>
    <div class="bg-orb bg-orb-b"></div>
    <div class="bg-grid"></div>
    <div class="page-shell">
        <header class="hero">
            <div class="hero-copy">
                <p class="eyebrow">키워드 포지</p>
                <h1>수익형 키워드 발굴&amp;제목 생성기</h1>
                <aside class="hero-panel hero-panel-legacy" hidden>
                    <div class="hero-stat"><span>수집</span><strong id="countCollected">0</strong></div>
                    <div class="hero-stat"><span>확장</span><strong id="countExpanded">0</strong></div>
                    <div class="hero-stat"><span>분석</span><strong id="countAnalyzed">0</strong></div>
                    <div class="hero-stat"><span>선별</span><strong id="countSelected">0</strong></div>
                    <div class="hero-stat"><span>제목</span><strong id="countTitled">0</strong></div>
                </aside>
                <aside class="hero-panel" aria-label="현재 적용 설정 요약">
                    <article class="hero-status-card hero-status-card-input">
                        <span class="hero-status-label">입력 상태</span>
                        <strong id="heroInputStatusValue">시드 · 입력 필요</strong>
                        <p id="heroInputStatusMeta" class="hero-status-meta">카테고리 또는 시드 기준을 먼저 정해 주세요.</p>
                    </article>
                    <article class="hero-status-card hero-status-card-selection">
                        <span class="hero-status-label">선별 기준</span>
                        <strong id="heroSelectionStatusValue">자동 선별</strong>
                        <p id="heroSelectionStatusMeta" class="hero-status-meta">필요하면 2축 조합을 바로 적용해 다시 선별할 수 있습니다.</p>
                    </article>
                    <article class="hero-status-card hero-status-card-title">
                        <span class="hero-status-label">제목 설정</span>
                        <strong id="heroTitleStatusValue">템플릿 생성</strong>
                        <p id="heroTitleStatusMeta" class="hero-status-meta">표면과 개수는 제목 설정에서 바로 바꿀 수 있습니다.</p>
                    </article>
                    <article class="hero-status-card hero-status-card-operation">
                        <span class="hero-status-label">운영 상태</span>
                        <strong id="heroOperationStatusValue">상시 슬로우</strong>
                        <p id="heroOperationStatusMeta" class="hero-status-meta">요청 간격과 일일 한도는 운영 설정에서 관리합니다.</p>
                    </article>
                    <article class="hero-status-card hero-status-card-login">
                        <span class="hero-status-label">네이버 로그인</span>
                        <strong id="heroNaverLoginStatusValue">미확인</strong>
                        <p id="heroNaverLoginStatusMeta" class="hero-status-meta">로그인 상태 확인 버튼으로 Creator Advisor 세션을 검증할 수 있습니다.</p>
                    </article>
                </aside>
                <p class="hero-text">
                    시드 검색과 카테고리 수집을 바탕으로 키워드를 확장하고, 분석 후 제목용 후보까지 바로 추립니다.
                </p>
                <div class="hero-actions">
                    <button type="button" class="primary-btn" id="runFullButton">전체 실행</button>
                    <button type="button" class="ghost-chip" data-utility-open="settings" aria-pressed="false">운영 설정</button>
                    <button type="button" class="ghost-chip" data-utility-open="history" aria-pressed="false">실행 기록</button>
                    <button type="button" class="ghost-chip" data-utility-open="vault" aria-pressed="false">키워드 보관함</button>
                    <button type="button" class="ghost-chip" data-utility-open="queue" aria-pressed="false">예약 / 대기열</button>
                    <button type="button" class="ghost-chip" data-utility-open="diagnostics" aria-pressed="false">진단 / 로그</button>
                    <a class="secondary-link" href="/guides">사용 가이드</a>
                    <a class="secondary-link" href="/recommended-usage">추천 사용 순서</a>
                    <a class="secondary-link" href="/api-docs" target="_blank" rel="noopener noreferrer">API 문서</a>
                </div>
            </div>
        </header>

        <nav class="workspace-nav" aria-label="워크스페이스 탐색">
            <a class="workspace-nav-link" href="#section-controls">
                <span class="workspace-nav-index">01</span>
                <span>실행 조건</span>
            </a>
            <a class="workspace-nav-link" href="#section-select">
                <span class="workspace-nav-index">02</span>
                <span>2축 선별</span>
            </a>
            <div id="resultStageDock" class="result-stage-dock workspace-nav-stage-dock"></div>
            <div class="results-panel-tools workspace-nav-output-panel" id="resultsPanelTools" hidden>
                <div class="results-tool-group">
                    <span class="results-tool-label">단계 파일</span>
                    <button type="button" class="ghost-chip" id="resultsExportCollectedCsvButton">수집 CSV</button>
                    <button type="button" class="ghost-chip" id="resultsExportCollectedTxtButton">수집 TXT</button>
                    <button type="button" class="ghost-chip" id="resultsCopyCollectedLinesButton">수집 복사(줄)</button>
                    <button type="button" class="ghost-chip" id="resultsCopyCollectedCommaButton">수집 복사(,)</button>
                    <button type="button" class="ghost-chip" id="resultsExportExpandedCsvButton">확장 CSV</button>
                    <button type="button" class="ghost-chip" id="resultsExportExpandedTxtButton">확장 TXT</button>
                    <button type="button" class="ghost-chip" id="resultsCopyExpandedLinesButton">확장 복사(줄)</button>
                    <button type="button" class="ghost-chip" id="resultsCopyExpandedCommaButton">확장 복사(,)</button>
                    <button type="button" class="ghost-chip" id="resultsExportAnalyzedCsvButton">분석 CSV</button>
                    <button type="button" class="ghost-chip" id="resultsExportAnalyzedTxtButton">분석 TXT</button>
                    <button type="button" class="ghost-chip" id="resultsCopyAnalyzedLinesButton">분석 복사(줄)</button>
                    <button type="button" class="ghost-chip" id="resultsCopyAnalyzedCommaButton">분석 복사(,)</button>
                    <button type="button" class="ghost-chip" id="resultsExportSelectedCsvButton">선별 CSV</button>
                    <button type="button" class="ghost-chip" id="resultsExportSelectedTxtButton">선별 TXT</button>
                    <button type="button" class="ghost-chip" id="resultsCopySelectedLinesButton">선별 복사(줄)</button>
                    <button type="button" class="ghost-chip" id="resultsCopySelectedCommaButton">선별 복사(,)</button>
                </div>
                <div class="results-tool-group">
                    <span class="results-tool-label">보조 도구</span>
                    <button type="button" class="ghost-chip" data-utility-open="history" aria-pressed="false">실행 기록</button>
                    <button type="button" class="ghost-chip" data-utility-open="vault" aria-pressed="false">키워드 보관함</button>
                    <button type="button" class="ghost-chip" data-utility-open="diagnostics" aria-pressed="false">오류 / 진단</button>
                    <button type="button" class="ghost-chip" data-utility-open="logs" aria-pressed="false">실행 로그</button>
                    <button type="button" class="ghost-chip" id="exportTitleCsvButton">제목 결과 CSV</button>
                </div>
            </div>
        </nav>

        <main class="layout-grid workspace-cockpit">
            <div class="workspace-main-column">
            <section class="panel results-panel" id="section-results">
                <div class="panel-head results-panel-head">
                    <div class="results-panel-lead">
                        <p class="panel-kicker">작업대</p>
                        <h2>키워드 작업대</h2>
                        <p class="panel-copy results-panel-copy">확장과 분석은 백엔드에서 계속 진행하고, 먼저 살아남는 후보는 여기에서 바로 확인하고 다음 작업으로 넘깁니다.</p>
                    </div>
                    <div class="results-panel-badges">
                        <span class="badge">실시간 선별 우선</span>
                        <span class="badge">CSV / TXT / 클립보드</span>
                    </div>
                </div>
                <div id="resultsGrid" class="results-grid"></div>
            </section>
            </div>

            <div class="workspace-side-column">
            <div class="control-column">
            <section class="panel control-panel" id="section-controls">
                <div class="panel-head">
                    <div>
                        <p class="panel-kicker">실행</p>
                        <h2>실행 센터</h2>
                    </div>
                </div>

                <div class="control-stack" id="controlStack">
                <div class="control-primary-column">
                <section class="control-stage-block collector-quick-panel">
                    <div class="control-stage-head">
                        <div>
                            <p class="panel-kicker">빠른 입력</p>
                            <h3>빠른 수집 입력</h3>
                        </div>
                        <span class="badge">홈 고정</span>
                    </div>
                    <div class="collector-quick-grid">
                        <div class="field-block collector-mode-inline">
                            <span class="field-label">수집 모드</span>
                            <div class="option-row">
                                <label class="check-chip"><input type="radio" name="collectorMode" value="category" checked />카테고리</label>
                                <label class="check-chip"><input type="radio" name="collectorMode" value="seed" />시드</label>
                            </div>
                        </div>

                        <label class="field-block collector-quick-field" data-mode-visibility="category">
                            <span class="field-label">카테고리</span>
                            <select id="categoryInput">
                                {category_options}
                            </select>
                        </label>

                        <label class="field-block collector-quick-field" data-mode-visibility="seed" hidden>
                            <span class="field-label">시드 키워드</span>
                            <input id="seedInput" type="text" placeholder="예: 보험, 대출, 모니터암" />
                        </label>

                    </div>
                </section>
                <section class="quickstart-panel control-stage-quickstart">
                    <div class="quickstart-head">
                        <div>
                            <p class="panel-kicker">실행 흐름</p>
                            <h3>모드별 실행</h3>
                        </div>
                        <span class="badge">왼쪽 고정</span>
                    </div>
                    <div class="quickstart-mode-list">
                        <div class="quickstart-mode-row" data-quickstart-mode-row="discover">
                            <div class="quickstart-mode-label-group">
                                <div class="quickstart-mode-label">키워드 발굴</div>
                                <span class="quickstart-mode-caption">수집 → 확장</span>
                            </div>
                            <div class="quickstart-mode-actions">
                                <button type="button" class="ghost-chip quickstart-inline-btn" data-quickstart-help="discover">설명</button>
                                <button type="button" class="ghost-chip quickstart-inline-btn" data-quickstart-settings="discover">설정</button>
                                <button type="button" class="subtle-btn quickstart-run-btn" id="runExpandButton">실행</button>
                            </div>
                        </div>
                        <div class="quickstart-mode-row" data-quickstart-mode-row="analyze">
                            <div class="quickstart-mode-label-group">
                                <div class="quickstart-mode-label">보유 키워드 분석</div>
                                <span class="quickstart-mode-caption">필요 시 수집 → 확장 포함</span>
                            </div>
                            <div class="quickstart-mode-actions">
                                <button type="button" class="ghost-chip quickstart-inline-btn" data-quickstart-help="analyze">설명</button>
                                <button type="button" class="ghost-chip quickstart-inline-btn" data-quickstart-settings="analyze">설정</button>
                                <button type="button" class="subtle-btn quickstart-run-btn" id="runAnalyzeButton">실행</button>
                            </div>
                        </div>
                        <div class="quickstart-mode-row" data-quickstart-mode-row="title">
                            <div class="quickstart-mode-label-group">
                                <div class="quickstart-mode-label">제목 생성</div>
                                <span class="quickstart-mode-caption">필요 시 앞단계 전체 포함</span>
                            </div>
                            <div class="quickstart-mode-actions">
                                <button type="button" class="ghost-chip quickstart-inline-btn" data-quickstart-help="title">설명</button>
                                <button type="button" class="ghost-chip quickstart-inline-btn" data-quickstart-settings="title">설정</button>
                                <button type="button" class="subtle-btn quickstart-run-btn" id="runTitleButton">실행</button>
                            </div>
                        </div>
                    </div>
                    <div class="quickstart-utility-row">
                        <div class="field-block collector-limit-card quickstart-expand-card">
                            <span class="field-label">확장 개수</span>
                            <div class="option-row collector-limit-presets">
                                <button type="button" class="ghost-chip" data-expand-limit="100">100개</button>
                                <button type="button" class="ghost-chip" data-expand-limit="1000">1,000개</button>
                                <button type="button" class="ghost-chip" data-expand-limit="10000">10,000개</button>
                                <button type="button" class="ghost-chip" data-expand-limit="infinite">무제한</button>
                            </div>
                            <input id="expandMaxResultsInput" type="number" min="1" step="1" value="1000" placeholder="예: 1000" />
                        </div>
                        <div class="quickstart-utility-actions">
                            <button type="button" class="ghost-btn" id="stopStreamButton" disabled>중지</button>
                            <button type="button" class="ghost-btn" id="resetButton">결과 초기화</button>
                        </div>
                    </div>
                </section>
                <section class="control-stage-block control-stage-collect" data-control-block="collect" hidden>
                    <div class="control-stage-head">
                        <div>
                            <p class="panel-kicker">수집 설정</p>
                            <h3>수집 설정</h3>
                        </div>
                        <span class="badge">1단계</span>
                    </div>

                    <div class="form-grid">
                    <div class="category-settings-grid" data-mode-visibility="category">
                        <label class="field-block category-setting-card">
                            <span class="field-label">카테고리 수집 소스</span>
                            <select id="categorySourceInput">
                                {category_source_options}
                            </select>
                        </label>

                        <label class="field-block category-setting-card">
                            <span class="field-label">Creator Advisor 서비스</span>
                            <select id="trendServiceInput">
                                {trend_service_options}
                            </select>
                        </label>

                        <label class="field-block category-setting-card">
                            <span class="field-label">트렌드 날짜</span>
                            <input id="trendDateInput" type="date" />
                        </label>

                        <label class="field-block category-setting-card">
                            <span class="field-label">로그인한 브라우저</span>
                            <select id="trendBrowserInput">
                                <option value="auto">현재 접속 브라우저 자동 감지</option>
                                <option value="edge">Microsoft Edge</option>
                                <option value="chrome">Google Chrome</option>
                                <option value="firefox">Mozilla Firefox</option>
                            </select>
                        </label>
                    </div>

                    <div class="field-block field-block-wide session-helper-card session-helper-wide-card" data-mode-visibility="category">
                        <span class="field-label field-label-row">
                            <span>Creator Advisor 로그인</span>
                            {creator_login_help}
                        </span>
                        <input
                            id="trendCookieInput"
                            type="hidden"
                            value=""
                        />
                        <div class="session-helper-actions">
                            <button type="button" class="primary-btn session-helper-btn" id="loadLocalCookieButton">현재 브라우저 쿠키 읽기</button>
                            <button type="button" class="ghost-chip session-helper-btn" id="validateTrendSessionButton">로그인 상태 확인</button>
                            <button type="button" class="ghost-chip session-helper-btn" id="launchLoginBrowserButton">전용 로그인 브라우저 열기</button>
                        </div>
                        <p class="input-help session-helper-status" id="localCookieStatus">
                            현재 브라우저 세션이나 저장된 전용 세션으로 로그인 상태를 확인할 수 있습니다.
                        </p>
                    </div>

                    <div class="field-block field-block-wide topic-seed-generator-card">
                        <div class="field-label-row">
                            <span class="field-label">주제에서 시드 만들기</span>
                            <span class="input-help compact-help">아이디어만 넣으면 시작용 시드 묶음을 자동으로 만듭니다. 칩을 누르면 바로 시드 입력으로 옮길 수 있습니다.</span>
                        </div>
                        <div class="topic-seed-generator-row">
                            <input id="topicSeedInput" type="text" placeholder="예: 자취 가전, 초등 영어, 중고 모니터" />
                            <select id="topicSeedIntent">
                                <option value="balanced">균형형</option>
                                <option value="need">정보형</option>
                                <option value="profit">수익형</option>
                            </select>
                            <select id="topicSeedCount">
                                <option value="8">8개</option>
                                <option value="12" selected>12개</option>
                                <option value="20">20개</option>
                            </select>
                            <button type="button" class="ghost-btn" id="generateTopicSeedsButton">시드 만들기</button>
                        </div>
                        <p class="input-help" id="topicSeedStatus">아직 주제 시드를 만들지 않았습니다.</p>
                        <div id="topicSeedSuggestionList" class="topic-seed-suggestion-list"></div>
                    </div>

                    <div class="field-block field-block-wide collector-inline-actions">
                        <div class="collector-action-row">
                            <button type="button" class="subtle-btn collector-run-btn" data-run-action="collect">수집만 실행</button>
                            <div class="collector-option-row">
                                <label class="launcher-toggle-chip collector-toggle-chip">
                                    <input id="optionRelated" type="checkbox" checked />
                                    <span>연관 키워드 수집</span>
                                </label>
                                <label class="launcher-toggle-chip collector-toggle-chip">
                                    <input id="optionAutocomplete" type="checkbox" checked />
                                    <span>자동완성 우선 사용</span>
                                </label>
                                <label class="launcher-toggle-chip collector-toggle-chip">
                                    <input id="optionDebug" type="checkbox" checked />
                                    <span>디버그 정보 포함</span>
                                </label>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="option-row collect-category-options" data-mode-visibility="category">
                    <label class="check-chip"><input id="optionBulk" type="checkbox" checked />카테고리 다중 쿼리 사용</label>
                    <label class="check-chip"><input id="trendFallbackInput" type="checkbox" />트렌드 실패 시 검색 예비안 사용</label>
                </div>

                <p class="input-help" id="trendSourceHelp" data-mode-visibility="category">
                    카테고리 모드에서 네이버 트렌드를 고르면 Creator Advisor 주제 기반 인기 키워드를 먼저 조회합니다.
                    먼저 현재 브라우저의 로컬 쿠키를 읽어 보지만, 브라우저 권한이나 쿠키 DB 잠금 때문에 실패할 수 있습니다.
                    그럴 때는 `전용 로그인 브라우저 열기`가 더 안정적이며, 저장된 전용 세션이 있으면 자동으로 이어서 사용합니다.
                    세션이 없거나 실패하면 아래 fallback 설정에 따라 검색 preset으로 전환합니다.
                </p>

                </section>
                </div>

                </div>
            </section>
            </div>
            <section class="panel summary-panel" id="section-progress">
                <div class="panel-head">
                    <div>
                        <p class="panel-kicker">진행 현황</p>
                        <h2>진행 현황</h2>
                        <p class="panel-copy">실행 상태를 먼저 확인하고, 아래 작업대로 바로 이어집니다.</p>
                    </div>
                    <span class="status-pill" id="pipelineStatus">대기 중</span>
                </div>

                <div class="progress-card">
                    <div class="progress-track">
                        <div id="progressBar" class="progress-bar"></div>
                    </div>
                    <div class="progress-meta">
                        <strong id="progressText">0 / 5 단계 완료</strong>
                        <span id="progressDetail">아직 실행하지 않았습니다.</span>
                    </div>
                </div>

                <div id="recoveryGuide" class="recovery-guide-card empty">
                    <strong>다음 액션 안내</strong>
                    <p>실행 상태에 맞는 복구 힌트가 여기에 표시됩니다.</p>
                </div>

                <div class="status-list" id="statusList"></div>

            </section>
            </div>

            <div class="workspace-right-column">
            <section class="panel select-panel-shell" id="section-select">
                <section class="control-stage-block grade-select-panel control-stage-select" data-control-block="select">
                    <div class="control-stage-head">
                        <div>
                            <p class="panel-kicker">2축 선별</p>
                            <h3>2축 선별</h3>
                        </div>
                        <span class="badge">선별 기준</span>
                    </div>
                    <div class="grade-select-head">
                        <div>
                            <span class="field-label">2축 선별</span>
                            <p class="grade-select-summary" id="gradeSelectSummary">전체 · 전체 조합</p>
                        </div>
                        <p class="input-help compact-help">수익성 A~F와 노출도 1~6 조합으로 선별합니다. 오른쪽에서 조합을 바꾸고 바로 다시 선별하면 됩니다.</p>
                    </div>
                    <div class="grade-select-presets">
                        <button type="button" class="ghost-chip" data-selection-preset="all">전체</button>
                        <button type="button" class="ghost-chip" data-selection-preset="balanced">균형형</button>
                        <button type="button" class="ghost-chip" data-selection-preset="golden_core">황금형</button>
                        <button type="button" class="ghost-chip" data-selection-preset="profit_focus">수익형</button>
                        <button type="button" class="ghost-chip" data-selection-preset="exposure_focus">노출형</button>
                        <button type="button" class="ghost-chip" data-selection-preset="longtail_explore">롱테일 탐색형</button>
                    </div>
                    <p class="input-help compact-help" id="gradeSelectDescription">수익성과 노출도 전체 조합을 열어두고 분석된 후보를 넓게 검토합니다.</p>
                    <div class="grade-select-row grade-select-axis-row">
                        <span class="grade-select-axis-label">수익성</span>
                        <button type="button" class="ghost-chip grade-toggle-chip" data-profitability-toggle="A">A</button>
                        <button type="button" class="ghost-chip grade-toggle-chip" data-profitability-toggle="B">B</button>
                        <button type="button" class="ghost-chip grade-toggle-chip" data-profitability-toggle="C">C</button>
                        <button type="button" class="ghost-chip grade-toggle-chip" data-profitability-toggle="D">D</button>
                        <button type="button" class="ghost-chip grade-toggle-chip" data-profitability-toggle="E">E</button>
                        <button type="button" class="ghost-chip grade-toggle-chip" data-profitability-toggle="F">F</button>
                    </div>
                    <div class="grade-select-row grade-select-axis-row">
                        <span class="grade-select-axis-label">노출도</span>
                        <button type="button" class="ghost-chip grade-toggle-chip" data-attackability-toggle="1">1</button>
                        <button type="button" class="ghost-chip grade-toggle-chip" data-attackability-toggle="2">2</button>
                        <button type="button" class="ghost-chip grade-toggle-chip" data-attackability-toggle="3">3</button>
                        <button type="button" class="ghost-chip grade-toggle-chip" data-attackability-toggle="4">4</button>
                        <button type="button" class="ghost-chip grade-toggle-chip" data-attackability-toggle="5">5</button>
                        <button type="button" class="ghost-chip grade-toggle-chip" data-attackability-toggle="6">6</button>
                    </div>
                    <div class="grade-select-actions">
                        <button type="button" class="subtle-btn grade-select-run" id="runGradeSelectButton">조합 적용 + 선별 실행</button>
                    </div>
                </section>
            </section>
            </div>

            <section class="panel launcher-panel" id="section-launcher" hidden>
                <div class="panel-head">
                    <div>
                        <p class="panel-kicker">세부 실행</p>
                        <h2>확장 · 분석 · 제목</h2>
                    </div>
                </div>
                <p class="input-help compact-help launcher-panel-note">
                    상단 시작 모드로 큰 흐름을 정하고, 여기서는 확장·분석·제목 단계의 세부 입력과 옵션만 조정하면 됩니다.
                </p>

                <div class="control-launcher-column">
                    <section class="control-stage-block launcher-card control-stage-expand" data-control-block="expand" data-control-card="expand">
                        <div class="launcher-head">
                            <div>
                                <p class="panel-kicker">확장 시작점</p>
                                <h3>확장 시작점</h3>
                            </div>
                            <span class="badge" id="selectedCollectedCount">선택 0건</span>
                        </div>
                        <label class="field-block">
                            <span class="field-label">확장 입력 소스</span>
                            <select id="expandInputSource">
                                <option value="collector_all">수집 결과 전체</option>
                                <option value="collector_selected">수집 결과 중 선택 항목</option>
                                <option value="manual_text">직접 붙여넣기</option>
                            </select>
                        </label>
                        <div class="launcher-source-details" data-expand-source-visibility="collector_selected" hidden>
                            <div class="launcher-note-card">
                                수집 결과에서 체크한 키워드만 확장에 사용합니다. 아래 수집 결과 카드에서 원하는 항목만 선택하면 됩니다.
                            </div>
                        </div>
                        <div class="launcher-source-details" data-expand-source-visibility="manual_text" hidden>
                            <label class="field-block">
                                <span class="field-label">직접 붙여넣을 키워드</span>
                                <textarea
                                    id="expandManualInput"
                                    rows="5"
                                    placeholder="예: 보험&#10;카드 비교&#10;대출 추천"
                                ></textarea>
                            </label>
                            <p class="input-help compact-help">줄바꿈, 콤마, 세미콜론으로 여러 키워드를 나눌 수 있습니다.</p>
                        </div>
                        <div class="launcher-inline-grid">
                            <div class="field-block">
                                <span class="field-label">확장 옵션</span>
                                <div class="option-row launcher-toggle-row">
                                    <label class="launcher-toggle-chip">
                                        <input id="expandOptionRelated" type="checkbox" checked />
                                        <span>연관확장</span>
                                    </label>
                                    <label class="launcher-toggle-chip">
                                        <input id="expandOptionAutocomplete" type="checkbox" checked />
                                        <span>자동완성</span>
                                    </label>
                                    <label class="launcher-toggle-chip">
                                        <input id="expandOptionSeedFilter" type="checkbox" checked />
                                        <span>원문포함</span>
                                    </label>
                                </div>
                            </div>
                        </div>
                    </section>

                    <section class="control-stage-block launcher-card control-stage-analyze" data-control-block="analyze" data-control-card="analyze">
                        <div class="launcher-head">
                            <div>
                                <p class="panel-kicker">분석 시작점</p>
                                <h3>분석 시작점</h3>
                            </div>
                            <span class="badge" id="manualAnalyzeCount">직접 입력 0건</span>
                        </div>
                        <label class="field-block">
                            <span class="field-label">분석 입력 소스</span>
                            <select id="analyzeInputSource">
                                <option value="expanded_results">확장 결과 사용</option>
                                <option value="manual_text">직접 붙여넣기</option>
                            </select>
                        </label>
                        <div class="launcher-source-details" data-analyze-source-visibility="manual_text" hidden>
                            <label class="field-block">
                                <span class="field-label">직접 붙여넣을 키워드</span>
                                <textarea
                                    id="analyzeManualInput"
                                    rows="5"
                                    placeholder="예: 보험 추천, 카드 비교, 대출 금리"
                                ></textarea>
                            </label>
                        </div>
                        <details class="launcher-advanced">
                            <summary>실측 데이터 / CSV</summary>
                            <div class="launcher-advanced-body">
                                <label class="field-block field-block-wide">
                                    <span class="field-label">실측 데이터 붙여넣기</span>
                                    <textarea
                                        id="analyzeKeywordStatsInput"
                                        rows="6"
                                        placeholder="분석 HTML 전체 또는 data-line 행을 그대로 붙여넣으세요."
                                    ></textarea>
                                </label>
                                <p class="input-help compact-help">분석 HTML 전체나 data-line 행을 붙여넣으면 PC/MO조회, 블로그수, 입찰가를 우선 사용합니다.</p>
                                <div class="field-block field-block-wide">
                                    <span class="field-label">분석/출력</span>
                                    <div class="option-row">
                                        <button type="button" class="ghost-chip" id="exportCollectedCsvButton">수집 결과 CSV</button>
                                        <button type="button" class="ghost-chip" id="exportCollectedTxtButton">수집 결과 TXT</button>
                                        <button type="button" class="ghost-chip" id="copyCollectedLinesButton">수집 복사(줄)</button>
                                        <button type="button" class="ghost-chip" id="copyCollectedCommaButton">수집 복사(,)</button>
                                        <button type="button" class="ghost-chip" id="exportExpandedCsvButton">확장 결과 CSV</button>
                                        <button type="button" class="ghost-chip" id="exportExpandedTxtButton">확장 결과 TXT</button>
                                        <button type="button" class="ghost-chip" id="copyExpandedLinesButton">확장 복사(줄)</button>
                                        <button type="button" class="ghost-chip" id="copyExpandedCommaButton">확장 복사(,)</button>
                                        <button type="button" class="ghost-chip" id="exportCsvButton">분석 결과 CSV</button>
                                        <button type="button" class="ghost-chip" id="exportAnalyzedTxtButton">분석 결과 TXT</button>
                                        <button type="button" class="ghost-chip" id="copyAnalyzedLinesButton">분석 복사(줄)</button>
                                        <button type="button" class="ghost-chip" id="copyAnalyzedCommaButton">분석 복사(,)</button>
                                        <button type="button" class="ghost-chip" id="exportSelectedCsvButton">선별 결과 CSV</button>
                                        <button type="button" class="ghost-chip" id="exportSelectedTxtButton">선별 결과 TXT</button>
                                        <button type="button" class="ghost-chip" id="copySelectedLinesButton">선별 복사(줄)</button>
                                        <button type="button" class="ghost-chip" id="copySelectedCommaButton">선별 복사(,)</button>
                                    </div>
                                </div>
                                <p class="input-help compact-help">확장 없이 분석만 실행하거나, 분석 결과를 내려받는 용도로 씁니다.</p>
                            </div>
                        </details>
                    </section>

                <section class="title-settings-card launcher-card control-stage-block control-stage-title" data-control-block="title">
                    <div class="launcher-head">
                        <div>
                            <p class="panel-kicker">제목 생성 시작점</p>
                            <h3>제목 생성 시작점</h3>
                        </div>
                        <span class="badge" id="titleModeBadge">템플릿</span>
                    </div>
                    <div class="form-grid">
                        <input id="titleMode" type="hidden" value="template" />

                        <div class="field-block mode-block title-mode-block">
                            <span class="field-label field-label-row">
                                <span>제목 생성 모드</span>
                                {title_mode_help}
                            </span>
                            <label class="mode-card">
                                <input type="radio" name="titleModeOption" value="template" checked />
                                <span>
                                    <strong>템플릿 모드</strong>
                                    <em>추가 설정 없이 즉시 제목을 생성합니다. 빠르게 후보를 뽑을 때 적합합니다.</em>
                                </span>
                            </label>
                            <label class="mode-card">
                                <input type="radio" name="titleModeOption" value="ai" />
                                <span>
                                    <strong>AI 모드</strong>
                                    <em>운영 설정에 등록한 Provider와 모델을 사용해 더 유연한 제목을 생성합니다.</em>
                                </span>
                            </label>
                        </div>

                        <div class="field-block field-block-wide">
                            <span class="field-label field-label-row">
                                <span>제목 키워드 조합</span>
                                {title_keyword_modes_help}
                            </span>
                            <div class="option-row" id="titleKeywordModes">
                                <label class="check-chip"><input id="titleModeSingle" type="checkbox" checked />단일 키워드</label>
                                <label class="check-chip"><input id="titleModeLongtailSelected" type="checkbox" checked />롱테일 V1</label>
                                <label class="check-chip"><input id="titleModeLongtailExploratory" type="checkbox" />롱테일 V2</label>
                                <label class="check-chip"><input id="titleModeLongtailExperimental" type="checkbox" />롱테일 V3</label>
                            </div>
                            <p id="titleKeywordModeSummary" class="input-help compact-help">
                                선택: 단일 + V1
                            </p>
                        </div>

                        <div class="field-block field-block-wide">
                            <span class="field-label field-label-row">
                                <span>제목 영역 및 개수</span>
                                {title_surface_help}
                            </span>
                            <div class="title-surface-grid" id="titleSurfaceGrid">
                                <label class="title-surface-card">
                                    <span class="check-chip"><input id="titleSurfaceHome" type="checkbox" checked />홈판</span>
                                    <select id="titleSurfaceHomeCount" class="title-surface-count">
                                        <option value="1">1개</option>
                                        <option value="2" selected>2개</option>
                                        <option value="3">3개</option>
                                        <option value="4">4개</option>
                                    </select>
                                </label>
                                <label class="title-surface-card">
                                    <span class="check-chip"><input id="titleSurfaceBlog" type="checkbox" checked />블로그형</span>
                                    <select id="titleSurfaceBlogCount" class="title-surface-count">
                                        <option value="1">1개</option>
                                        <option value="2" selected>2개</option>
                                        <option value="3">3개</option>
                                        <option value="4">4개</option>
                                    </select>
                                </label>
                                <label class="title-surface-card">
                                    <span class="check-chip"><input id="titleSurfaceHybrid" type="checkbox" />둘다</span>
                                    <select id="titleSurfaceHybridCount" class="title-surface-count">
                                        <option value="1" selected>1개</option>
                                        <option value="2">2개</option>
                                        <option value="3">3개</option>
                                        <option value="4">4개</option>
                                    </select>
                                </label>
                            </div>
                            <p id="titleSurfaceSummary" class="input-help compact-help">
                                선택: 홈판 2개 + 블로그형 2개, 필요하면 둘다 포함 각 1-4개
                            </p>
                        </div>

                        <div class="title-advanced-toggle-row">
                            <button
                                type="button"
                                class="ghost-chip title-advanced-toggle"
                                id="toggleTitleAdvancedButton"
                                aria-expanded="false"
                                aria-controls="titleAdvancedSettings"
                            >추가설정</button>
                            <p class="input-help compact-help title-advanced-copy">
                                자동 재시도, AI 소스 반영, 모델, 프롬프트, API 설정을 펼쳐서 봅니다.
                            </p>
                        </div>

                        <div id="titleAdvancedSettings" class="title-advanced-settings" hidden>
                        <div class="field-block field-block-wide">
                            <span class="field-label field-label-row">
                                <span>저점수 자동 재작성</span>
                                {title_auto_retry_help}
                            </span>
                            <div class="title-auto-retry-row">
                                <label class="check-chip"><input id="titleAutoRetryEnabled" type="checkbox" checked />기준 미달 제목 자동 재작성</label>
                                <label class="title-auto-retry-threshold">
                                    <span>최소 점수</span>
                                    <input id="titleAutoRetryThreshold" type="number" min="70" max="100" step="1" value="84" />
                                </label>
                            </div>
                            <p id="titleAutoRetrySummary" class="input-help compact-help">
                                84점 미만은 자동 재작성 후 2회 실패 시 상위 모델로 자동 승격
                            </p>
                        </div>

                        <div class="field-block field-block-wide" data-title-mode-visibility="ai" hidden>
                            <span class="field-label field-label-row">
                                <span>실시간 이슈 반영</span>
                                {title_issue_context_help}
                            </span>
                            <div class="title-auto-retry-row">
                                <label class="check-chip"><input id="titleIssueContextEnabled" type="checkbox" checked />네이버 검색 상위 뉴스/콘텐츠 이슈 반영</label>
                                <label class="title-auto-retry-threshold">
                                    <span>조회 개수</span>
                                    <input id="titleIssueContextLimit" type="number" min="1" max="5" step="1" value="3" />
                                </label>
                            </div>
                            <p id="titleIssueContextSummary" class="input-help compact-help">
                                AI 요청당 상위 3개 키워드에 실시간 이슈 반영
                            </p>
                        </div>

                        <div class="field-block field-block-wide" data-title-mode-visibility="ai" hidden>
                            <span class="field-label field-label-row">
                                <span>이슈 소스 선택</span>
                            </span>
                            <div class="form-grid">
                                <label class="field-block">
                                    <span class="field-label">소스 모드</span>
                                    <select id="titleIssueSourceMode">
                                        {title_issue_source_mode_options}
                                    </select>
                                </label>
                                <label class="field-block">
                                    <span class="field-label">커스텀 도메인</span>
                                    <input id="titleCommunityCustomDomains" type="text" placeholder="clien.net, dcinside.com" />
                                </label>
                            </div>
                            <div class="option-row" id="titleCommunitySources">
                                {title_community_source_chips}
                            </div>
                            <p id="titleCommunitySourceSummary" class="input-help compact-help">
                                기본값은 네이버 카페, 블로그, 포스트를 반응형 소스로 사용합니다.
                            </p>
                        </div>

                        <label class="field-block" data-title-mode-visibility="ai" hidden>
                            <span class="field-label field-label-row">
                                <span>프롬프트 / 모델 프리셋</span>
                                <span class="inline-help">
                                    <button type="button" class="help-icon-btn" aria-label="프리셋 도움말">?</button>
                                    <span id="titlePresetDescription" class="help-tooltip">홈판 이슈형을 기본값으로 두고, 필요하면 직접 설정으로 바꿔 세부값을 조정합니다.</span>
                                </span>
                            </span>
                            <select id="titlePreset">
                                {title_preset_options}
                            </select>
                        </label>

                        <div class="field-block field-block-wide title-prompt-block" data-title-mode-visibility="ai" hidden>
                            <div class="title-prompt-head">
                                <div>
                                    <span class="field-label">사용자 프리셋</span>
                                </div>
                                <div class="title-prompt-actions">
                                    <button type="button" class="ghost-chip" id="saveTitleCustomPresetButton">현재 설정 저장</button>
                                    <button type="button" class="ghost-chip" id="deleteTitleCustomPresetButton">삭제</button>
                                </div>
                            </div>
                            <label class="field-block">
                                <span class="field-label">저장본 선택</span>
                                <select id="titleCustomPresetPicker">
                                    <option value="">직접 설정</option>
                                </select>
                            </label>
                            <p id="titleCustomPresetSummary" class="input-help compact-help">저장된 사용자 프리셋 없음</p>
                        </div>

                        <div class="field-block field-block-wide title-ai-layout" data-title-mode-visibility="ai" hidden>
                            <article class="title-ai-card title-ai-card-primary">
                                <div class="title-ai-card-head">
                                    <div>
                                        <span class="field-label field-label-row">
                                            <span>제목 작성 AI</span>
                                            <button type="button" class="ghost-chip inline-cta-chip" id="openApiRegistrySettingsButton">API 등록</button>
                                        </span>
                                        <p class="title-ai-card-copy">제목 최초 생성에 사용할 provider/model입니다.</p>
                                    </div>
                                </div>
                                <div class="title-ai-card-grid">
                                    <label class="field-block">
                                        <span class="field-label">AI 연결</span>
                                        <select id="titleProvider"></select>
                                        <p id="titleProviderRegistryHint" class="input-help compact-help">
                                            운영 설정에서 등록한 API만 여기 표시됩니다.
                                        </p>
                                    </label>
                                    <label class="field-block">
                                        <span class="field-label">모델</span>
                                        <select id="titleModel"></select>
                                    </label>
                                </div>
                            </article>

                            <article class="title-ai-card title-ai-card-secondary">
                                <div class="title-ai-card-head">
                                    <div>
                                        <span class="field-label">제목 재작성 AI</span>
                                        <p class="title-ai-card-copy">저점수 자동 재작성과 모델 승격에 사용할 전용 AI입니다.</p>
                                    </div>
                                </div>
                                <div class="title-ai-card-grid">
                                    <label class="field-block">
                                        <span class="field-label">AI 연결</span>
                                        <select id="titleRewriteProvider">
                                            <option value="">생성과 동일</option>
                                        </select>
                                    </label>
                                    <label class="field-block">
                                        <span class="field-label">모델</span>
                                        <select id="titleRewriteModel">
                                            <option value="">생성과 동일</option>
                                        </select>
                                    </label>
                                </div>
                                <p id="titleRewriteSummary" class="input-help compact-help">
                                    재작성은 제목 생성 AI와 같은 provider/model을 그대로 사용합니다.
                                </p>
                            </article>
                        </div>

                        <div class="field-block" data-title-mode-visibility="ai" hidden>
                            <span class="field-label field-label-row">
                                <span>창의성 프리셋</span>
                                <span class="inline-help">
                                    <button type="button" class="help-icon-btn" aria-label="창의성 프리셋 도움말">?</button>
                                    <span id="titleTemperatureDescription" class="help-tooltip">규칙 준수와 표현 다양성의 균형이 가장 무난한 기본값입니다.</span>
                                </span>
                            </span>
                            <select id="titleTemperature">
                                <option value="0.2">안정형</option>
                                <option value="0.5">절충형</option>
                                <option value="0.7">(추천) 균형형</option>
                                <option value="1.0">확장형</option>
                            </select>
                        </div>

                        <label class="field-block" data-title-mode-visibility="ai" hidden>
                            <span class="field-label">예비 처리</span>
                            <label class="check-chip"><input id="titleFallback" type="checkbox" checked />AI 실패 시 템플릿 사용</label>
                        </label>

                        <div class="field-block field-block-wide title-prompt-block" data-title-mode-visibility="ai" hidden>
                            <div class="title-prompt-head">
                                <div>
                                    <span class="field-label field-label-row">
                                        <span>AI 프롬프트</span>
                                        {title_prompt_help}
                                    </span>
                                </div>
                            <div class="title-prompt-actions">
                                    <button type="button" class="ghost-chip" id="openTitlePromptEditorButton">프롬프트 편집</button>
                                    <button type="button" class="ghost-chip" id="clearTitlePromptButton">비우기</button>
                                </div>
                            </div>
                            <label class="field-block">
                                <span class="field-label">저장본 선택</span>
                                <select id="titlePromptProfilePicker">
                                    <option value="">직접 입력</option>
                                </select>
                            </label>
                            <div id="titlePromptSummary" class="title-prompt-summary">추가 지침 없음</div>
                            <input id="titleSystemPrompt" type="hidden" value="" />
                        </div>

                        <div class="field-block field-block-wide title-prompt-block" data-title-mode-visibility="ai" hidden>
                            <div class="title-prompt-head">
                                <div>
                                    <span class="field-label field-label-row">
                                        <span>홈판 평가 프롬프트</span>
                                        {title_quality_prompt_help}
                                    </span>
                                </div>
                                <div class="title-prompt-actions">
                                    <button type="button" class="ghost-chip" id="openTitleQualityPromptEditorButton">프롬프트 편집</button>
                                    <button type="button" class="ghost-chip" id="clearTitleQualityPromptButton">기본값 복원</button>
                                </div>
                            </div>
                            <label class="field-block">
                                <span class="field-label">저장본 선택</span>
                                <select id="titleQualityPromptProfilePicker">
                                    <option value="">직접 입력</option>
                                </select>
                            </label>
                            <div id="titleQualityPromptSummary" class="title-prompt-summary">기본 홈판 평가 프롬프트를 사용 중입니다.</div>
                            <input id="titleQualitySystemPrompt" type="hidden" value="" />
                        </div>
                        </div>
                    </div>
                </section>
                </div>

            </section>
            </div>
        </main>
        <div id="workspaceSettingsModal" class="workspace-settings-modal" hidden>
            <button
                type="button"
                class="workspace-settings-backdrop"
                id="workspaceSettingsBackdrop"
                aria-label="관련 설정 닫기"
            ></button>
            <section class="workspace-settings-panel" role="dialog" aria-modal="true" aria-labelledby="workspaceSettingsTitle">
                <div class="workspace-settings-head">
                    <div>
                        <p class="panel-kicker">관련 설정</p>
                        <h2 id="workspaceSettingsTitle">수집 설정</h2>
                    </div>
                    <button type="button" class="ghost-btn" id="workspaceSettingsClose">닫기</button>
                </div>
                <div id="workspaceSettingsBody" class="workspace-settings-body"></div>
            </section>
        </div>
        <div id="utilityDrawer" class="utility-drawer" hidden>
            <button type="button" class="utility-drawer-backdrop" id="utilityDrawerBackdrop" aria-label="보조 패널 닫기"></button>
            <section class="utility-drawer-panel">
                <div class="utility-drawer-head">
                    <div class="utility-drawer-tabs">
                        <button type="button" class="ghost-chip" data-utility-tab="settings" aria-pressed="false">운영 설정</button>
                        <button type="button" class="ghost-chip" data-utility-tab="history" aria-pressed="false">실행 기록</button>
                        <button type="button" class="ghost-chip" data-utility-tab="vault" aria-pressed="false">키워드 보관함</button>
                        <button type="button" class="ghost-chip" data-utility-tab="queue" aria-pressed="false">예약 / 대기열</button>
                        <button type="button" class="ghost-chip" data-utility-tab="diagnostics" aria-pressed="true">오류 / 진단</button>
                        <button type="button" class="ghost-chip" data-utility-tab="logs" aria-pressed="false">실행 로그</button>
                    </div>
                    <button type="button" class="ghost-btn" id="utilityDrawerClose">닫기</button>
                </div>
                <div class="utility-drawer-body">
                    <section class="utility-drawer-view" data-utility-panel="settings" hidden>
                        <div class="settings-shell">
                            <div class="settings-hero">
                                <div>
                                    <p class="panel-kicker">운영</p>
                                    <h2>운영 설정</h2>
                                    <p class="settings-copy">
                                        예약모드와 장시간 실행을 대비해 요청 간격, 일일 한도, 인증 오류 보호를 여기서 관리합니다.
                                    </p>
                                </div>
                                <div class="settings-hero-actions">
                                    <button type="button" class="ghost-chip" id="refreshOperationSettingsButton">서버 상태 새로고침</button>
                                    <button type="button" class="ghost-chip" id="resetOperationGuardsButton">인증 잠금 초기화</button>
                                    <button type="button" class="ghost-btn" id="saveOperationSettingsButton">설정 저장 후 적용</button>
                                </div>
                            </div>
                            <div class="settings-status-grid">
                                <article class="collector-stat-card">
                                    <span>현재 모드</span>
                                    <strong id="operationModeStatus">상시 슬로우</strong>
                                </article>
                                <article class="collector-stat-card">
                                    <span>오늘 작업</span>
                                    <strong id="operationDailyUsage">0 / 제한 없음</strong>
                                </article>
                                <article class="collector-stat-card">
                                    <span>오늘 Naver 요청</span>
                                    <strong id="operationRequestUsage">0 / 제한 없음</strong>
                                </article>
                                <article class="collector-stat-card">
                                    <span>보호 상태</span>
                                    <strong id="operationGuardStatus">정상</strong>
                                </article>
                            </div>
                            <div class="settings-hint settings-action-guide">
                                `서버 상태 새로고침`은 서버 런타임 값을 다시 읽습니다.
                                `인증 잠금 초기화`는 인증 오류로 걸린 잠금 상태만 해제하며, 로그인 세션 자체를 복구하지는 않습니다.
                                `설정 저장 후 적용`은 현재 입력값을 서버에 반영하고 잠금 상태도 함께 정리합니다.
                            </div>
                            <div class="settings-panel-grid">
                                <section class="settings-card api-registry-card">
                                    <div class="collector-panel-head">
                                        <div>
                                            <p class="panel-kicker">AI 연결</p>
                                            <h3>AI API 등록</h3>
                                        </div>
                                        <span class="badge" id="titleApiRegistryCount">0개 연결</span>
                                    </div>
                                    <div class="settings-form-grid api-registry-grid">
                                        <label class="field-block">
                                            <span class="field-label">OpenAI</span>
                                            <input id="apiRegistryOpenaiKey" type="password" placeholder="sk-..." />
                                        </label>
                                        <label class="field-block">
                                            <span class="field-label">Gemini</span>
                                            <input id="apiRegistryGeminiKey" type="password" placeholder="AIza..." />
                                        </label>
                                        <label class="field-block">
                                            <span class="field-label">Vertex AI</span>
                                            <input id="apiRegistryVertexKey" type="password" placeholder="AIza..." />
                                        </label>
                                        <label class="field-block">
                                            <span class="field-label">Anthropic</span>
                                            <input id="apiRegistryAnthropicKey" type="password" placeholder="sk-ant-..." />
                                        </label>
                                    </div>
                                    <div id="titleApiRegistryStatus" class="settings-hint">
                                        등록된 API만 제목 생성 AI 설정에 표시됩니다.
                                    </div>
                                    <div class="settings-hero-actions api-registry-actions">
                                        <button type="button" class="ghost-chip" id="saveTitleApiRegistryButton">브라우저에 저장</button>
                                        <button type="button" class="ghost-chip" id="clearTitleApiRegistryButton">모두 지우기</button>
                                    </div>
                                </section>
                                <section class="settings-card">
                                    <div class="collector-panel-head">
                                        <div>
                                            <p class="panel-kicker">모드</p>
                                            <h3>운영 모드</h3>
                                        </div>
                                    </div>
                                    <div class="field-block">
                                        <span class="field-label">모드 선택</span>
                                        <select id="operationMode">
                                            <option value="daily_light">일일 10회 이하</option>
                                            <option value="always_on_slow">상시 슬로우</option>
                                            <option value="custom">직접 설정</option>
                                        </select>
                                    </div>
                                    <div id="operationModeDescription" class="collector-empty">
                                        상시 슬로우를 기본으로 두고, 작업 횟수나 요청 한도가 필요하면 다른 모드로 바꿉니다.
                                    </div>
                                    <div id="operationCustomModeGuide" class="settings-hint">
                                        `직접 설정`을 고르면 새 창이 뜨지 않고, 바로 오른쪽 `보호 옵션`이 편집 가능해집니다. 먼저 추천값을 불러온 뒤 필요한 부분만 조절하면 됩니다.
                                    </div>
                                </section>
                                <section class="settings-card" id="operationGuardCard">
                                    <div class="collector-panel-head">
                                        <div>
                                            <p class="panel-kicker">보호</p>
                                            <h3>보호 옵션</h3>
                                        </div>
                                    </div>
                                    <div id="operationCustomPresetPanel" class="operation-custom-panel" hidden>
                                        <div class="operation-custom-head">
                                            <strong>추천 조절</strong>
                                            <span>숫자를 직접 다 정하지 말고 `안전 / 추천 / 빠름` 중 하나를 먼저 고른 뒤, 아래 값만 미세 조정하세요.</span>
                                        </div>
                                        <div class="operation-custom-chip-row">
                                            <button type="button" class="ghost-chip" data-operation-custom-preset="safe">안전</button>
                                            <button type="button" class="ghost-chip" data-operation-custom-preset="balanced">추천</button>
                                            <button type="button" class="ghost-chip" data-operation-custom-preset="fast">빠름</button>
                                        </div>
                                        <div id="operationCustomPresetDescription" class="collector-empty">
                                            추천값 설명을 불러오는 중입니다.
                                        </div>
                                    </div>
                                    <div class="settings-form-grid">
                                        <label class="field-block">
                                            <span class="field-label">Naver 요청 간격(초)</span>
                                            <input id="operationRequestGap" type="number" min="0" max="120" step="0.5" />
                                        </label>
                                        <label class="field-block">
                                            <span class="field-label">하루 작업 시작 상한</span>
                                            <input id="operationDailyLimit" type="number" min="0" max="1000" step="1" />
                                        </label>
                                        <label class="field-block">
                                            <span class="field-label">하루 Naver 요청 상한</span>
                                            <input id="operationDailyRequestLimit" type="number" min="0" max="100000" step="1" />
                                        </label>
                                        <label class="field-block">
                                            <span class="field-label">연속 실행 보호(분)</span>
                                            <input id="operationMaxContinuousMinutes" type="number" min="0" max="1440" step="5" />
                                        </label>
                                        <label class="field-block field-block-wide">
                                            <span class="field-label">인증 오류 보호</span>
                                            <label class="check-chip">
                                                <input id="operationStopOnAuthError" type="checkbox" checked />
                                                401/403 감지 시 이후 요청 자동 중지
                                            </label>
                                        </label>
                                    </div>
                                    <div id="operationSettingsHint" class="settings-hint">
                                        0을 넣으면 해당 상한은 해제됩니다. 저장 후 즉시 서버 런타임에 반영됩니다.
                                    </div>
                                    <div id="operationSettingsSyncStatus" class="collector-empty">
                                        서버 런타임 상태를 불러오는 중입니다.
                                    </div>
                                </section>
                            </div>
                        </div>
                    </section>
                    <section class="utility-drawer-view" data-utility-panel="history" hidden>
                        <div class="queue-shell">
                            <div class="settings-hero">
                                <div>
                                    <p class="panel-kicker">기록</p>
                                    <h2>실행 기록</h2>
                                    <p class="settings-copy">
                                        어떤 조건으로 돌렸는지, 어디까지 실행했는지, 결과가 몇 건이었는지를 브라우저에 남깁니다.
                                        설정 복원과 같은 단계 재실행을 여기서 바로 할 수 있습니다.
                                    </p>
                                </div>
                                <div class="settings-hero-actions">
                                    <button type="button" class="ghost-chip" id="refreshExecutionHistoryButton">새로고침</button>
                                    <button type="button" class="ghost-btn" id="clearExecutionHistoryButton">기록 비우기</button>
                                </div>
                            </div>
                            <div class="settings-status-grid">
                                <article class="collector-stat-card">
                                    <span>저장된 실행</span>
                                    <strong id="executionHistoryCountLabel">0건</strong>
                                </article>
                                <article class="collector-stat-card">
                                    <span>최근 실행</span>
                                    <strong id="executionHistoryLatestLabel">없음</strong>
                                </article>
                                <article class="collector-stat-card">
                                    <span>마지막 단계</span>
                                    <strong id="executionHistoryStageLabel">-</strong>
                                </article>
                                <article class="collector-stat-card">
                                    <span>현재 검색</span>
                                    <strong id="executionHistoryFilterLabel">전체</strong>
                                </article>
                            </div>
                            <div class="settings-card">
                                <div class="settings-form-grid">
                                    <label class="field-block">
                                        <span class="field-label">기록 검색</span>
                                        <input id="executionHistorySearchInput" type="search" placeholder="카테고리, 시드, 단계 검색" />
                                    </label>
                                    <label class="field-block">
                                        <span class="field-label">표시 개수</span>
                                        <select id="executionHistoryLimitInput">
                                            <option value="10">최근 10건</option>
                                            <option value="20" selected>최근 20건</option>
                                            <option value="50">최근 50건</option>
                                        </select>
                                    </label>
                                </div>
                                <div id="executionHistoryStatus" class="settings-hint">
                                    실행이 끝나면 자동으로 저장됩니다.
                                </div>
                                <div id="executionHistoryList" class="queue-item-list">
                                    <div class="collector-empty">저장된 실행 기록이 없습니다.</div>
                                </div>
                            </div>
                        </div>
                    </section>
                    <section class="utility-drawer-view" data-utility-panel="vault" hidden>
                        <div class="queue-shell">
                            <div class="settings-hero">
                                <div>
                                    <p class="panel-kicker">보관</p>
                                    <h2>키워드 보관함</h2>
                                    <p class="settings-copy">
                                        나중에 다시 쓰고 싶은 키워드를 보관합니다. 선별 결과나 분석 표에서 바로 담아두고,
                                        메모를 남기거나 시드 입력으로 다시 가져올 수 있습니다.
                                    </p>
                                </div>
                                <div class="settings-hero-actions">
                                    <button type="button" class="ghost-chip" id="refreshKeywordVaultButton">새로고침</button>
                                    <button type="button" class="ghost-btn" id="clearKeywordVaultButton">보관함 비우기</button>
                                </div>
                            </div>
                            <div class="settings-status-grid">
                                <article class="collector-stat-card">
                                    <span>보관 키워드</span>
                                    <strong id="keywordVaultCountLabel">0건</strong>
                                </article>
                                <article class="collector-stat-card">
                                    <span>발행 완료</span>
                                    <strong id="keywordVaultPublishedCountLabel">0건</strong>
                                </article>
                                <article class="collector-stat-card">
                                    <span>초안 / 보류</span>
                                    <strong id="keywordVaultDraftCountLabel">0건</strong>
                                </article>
                                <article class="collector-stat-card">
                                    <span>현재 검색</span>
                                    <strong id="keywordVaultFilterLabel">전체</strong>
                                </article>
                            </div>
                            <div class="queue-panel-grid">
                                <section class="settings-card">
                                    <div class="collector-panel-head">
                                        <div>
                                            <p class="panel-kicker">빠른 추가</p>
                                            <h3>직접 넣기</h3>
                                        </div>
                                    </div>
                                    <div class="settings-form-grid">
                                        <label class="field-block field-block-wide">
                                            <span class="field-label">키워드 목록</span>
                                            <textarea
                                                id="keywordVaultQuickAddInput"
                                                rows="5"
                                                placeholder="줄바꿈으로 여러 키워드를 넣으세요&#10;예:&#10;포터블 모니터&#10;삼성 무빙스타일"
                                            ></textarea>
                                        </label>
                                    </div>
                                    <div class="queue-form-actions">
                                        <span id="keywordVaultQuickAddCountLabel" class="queue-inline-meta">0건 준비</span>
                                        <button type="button" class="ghost-btn" id="keywordVaultQuickAddButton">보관함에 추가</button>
                                    </div>
                                </section>
                                <section class="settings-card">
                                    <div class="collector-panel-head">
                                        <div>
                                            <p class="panel-kicker">검색</p>
                                            <h3>보관함 필터</h3>
                                        </div>
                                    </div>
                                    <div class="settings-form-grid">
                                        <label class="field-block">
                                            <span class="field-label">키워드 검색</span>
                                            <input id="keywordVaultSearchInput" type="search" placeholder="키워드, 메모, 출처 검색" />
                                        </label>
                                        <label class="field-block">
                                            <span class="field-label">상태</span>
                                            <select id="keywordVaultStatusFilter">
                                                <option value="all">전체</option>
                                                <option value="saved">보관</option>
                                                <option value="draft">초안 예정</option>
                                                <option value="published">발행 완료</option>
                                                <option value="hold">보류</option>
                                            </select>
                                        </label>
                                    </div>
                                    <div id="keywordVaultStatus" class="settings-hint">
                                        결과 표의 `보관` 버튼으로 담은 키워드도 여기 모입니다.
                                    </div>
                                </section>
                            </div>
                            <div id="keywordVaultList" class="queue-item-list">
                                <div class="collector-empty">보관된 키워드가 없습니다.</div>
                            </div>
                        </div>
                    </section>
                    <section class="utility-drawer-view" data-utility-panel="queue" hidden>
                        <div class="queue-shell">
                            <div class="settings-hero">
                                <div>
                                    <p class="panel-kicker">예약</p>
                                    <h2>예약 작업</h2>
                                    <p class="settings-copy">
                                        예약 작업은 등록 버튼을 누른 시점의 현재 화면 설정을 스냅샷으로 저장해, 시드 배치나 일일 카테고리 루틴에 그대로 사용합니다.
                                    </p>
                                </div>
                                <div class="settings-hero-actions">
                                    <button type="button" class="ghost-chip" id="refreshQueueSnapshotButton">새로고침</button>
                                    <button type="button" class="ghost-chip" id="pauseQueueRunnerButton">일시정지</button>
                                    <button type="button" class="ghost-btn" id="resumeQueueRunnerButton">재개</button>
                                </div>
                            </div>
                            <div class="settings-status-grid">
                                <article class="collector-stat-card">
                                    <span>실행기 상태</span>
                                    <strong id="queueRunnerStateLabel">불러오는 중</strong>
                                </article>
                                <article class="collector-stat-card">
                                    <span>현재 작업</span>
                                    <strong id="queueRunnerJobLabel">대기 중</strong>
                                </article>
                                <article class="collector-stat-card">
                                    <span>등록된 작업</span>
                                    <strong id="queueJobCountLabel">0건</strong>
                                </article>
                                <article class="collector-stat-card">
                                    <span>엑셀 출력 폴더</span>
                                    <strong id="queueOutputDirLabel">-</strong>
                                </article>
                            </div>
                            <div class="queue-panel-grid">
                                <section class="settings-card">
                                    <div class="collector-panel-head">
                                        <div>
                                            <p class="panel-kicker">배치</p>
                                            <h3>시드 배치 예약</h3>
                                        </div>
                                    </div>
                                    <div class="settings-form-grid">
                                        <label class="field-block field-block-wide">
                                            <span class="field-label">배치 이름</span>
                                            <input id="queueSeedBatchNameInput" type="text" placeholder="예: 3월 4주차 보험 시드" />
                                        </label>
                                        <label class="field-block">
                                            <span class="field-label">예약 시각</span>
                                            <input id="queueSeedBatchScheduleInput" type="datetime-local" />
                                        </label>
                                        <label class="field-block field-block-wide">
                                            <span class="field-label">시드 키워드</span>
                                            <textarea
                                                id="queueSeedBatchSeedsInput"
                                                rows="7"
                                                placeholder="줄바꿈으로 여러 시드를 넣으세요&#10;예:&#10;실비보험 추천&#10;운전자보험 비교"
                                            ></textarea>
                                        </label>
                                    </div>
                                    <div id="queueSeedBatchHint" class="settings-hint">
                                        시드 배치는 등록 시점의 현재 화면 설정을 그대로 묶어 시드별 전체 파이프라인을 순차 실행합니다. 등록 후 화면 설정을 바꿔도 이미 등록한 작업에는 반영되지 않으며, API 키나 트렌드 쿠키가 있으면 상태 파일에도 함께 저장됩니다.
                                    </div>
                                    <div class="queue-form-actions">
                                        <span id="queueSeedBatchCountLabel" class="queue-inline-meta">시드 0건</span>
                                        <button type="button" class="ghost-btn" id="submitQueueSeedBatchButton">시드 배치 등록</button>
                                    </div>
                                </section>
                                <section class="settings-card">
                                    <div class="collector-panel-head">
                                        <div>
                                            <p class="panel-kicker">루틴</p>
                                            <h3>일일 카테고리 루틴</h3>
                                        </div>
                                    </div>
                                    <div class="settings-form-grid">
                                        <label class="field-block field-block-wide">
                                            <span class="field-label">루틴 이름</span>
                                            <input id="queueRoutineNameInput" type="text" placeholder="예: 오전 카테고리 루틴" />
                                        </label>
                                        <label class="field-block">
                                            <span class="field-label">실행 시각</span>
                                            <input id="queueRoutineTimeInput" type="time" value="06:00" />
                                        </label>
                                        <div class="field-block field-block-wide">
                                            <span class="field-label">실행 요일</span>
                                            <div class="queue-weekday-grid">
                                                <label class="check-chip queue-weekday-chip">
                                                    <input type="checkbox" value="0" data-queue-weekday checked />
                                                    월
                                                </label>
                                                <label class="check-chip queue-weekday-chip">
                                                    <input type="checkbox" value="1" data-queue-weekday checked />
                                                    화
                                                </label>
                                                <label class="check-chip queue-weekday-chip">
                                                    <input type="checkbox" value="2" data-queue-weekday checked />
                                                    수
                                                </label>
                                                <label class="check-chip queue-weekday-chip">
                                                    <input type="checkbox" value="3" data-queue-weekday checked />
                                                    목
                                                </label>
                                                <label class="check-chip queue-weekday-chip">
                                                    <input type="checkbox" value="4" data-queue-weekday checked />
                                                    금
                                                </label>
                                                <label class="check-chip queue-weekday-chip">
                                                    <input type="checkbox" value="5" data-queue-weekday checked />
                                                    토
                                                </label>
                                                <label class="check-chip queue-weekday-chip">
                                                    <input type="checkbox" value="6" data-queue-weekday checked />
                                                    일
                                                </label>
                                            </div>
                                        </div>
                                        <div class="field-block field-block-wide">
                                            <span class="field-label">카테고리 선택</span>
                                            <div class="queue-category-picker">
                                                {queue_routine_category_picker}
                                            </div>
                                        </div>
                                    </div>
                                    <div id="queueRoutineHint" class="settings-hint">
                                        루틴도 등록 시점의 현재 화면 설정을 기준으로 이후 카테고리 작업을 자동 생성합니다. 앱이 실행 중이어야 내부 예약이 동작하며, 현재 인증 설정도 상태 파일에 저장될 수 있습니다.
                                    </div>
                                    <div class="queue-form-actions">
                                        <span id="queueRoutineCountLabel" class="queue-inline-meta">카테고리 0건</span>
                                        <button type="button" class="ghost-btn" id="submitQueueRoutineButton">루틴 등록</button>
                                    </div>
                                </section>
                            </div>
                            <div class="queue-panel-grid">
                                <section class="settings-card queue-list-card">
                                    <div class="collector-panel-head">
                                        <div>
                                            <p class="panel-kicker">작업</p>
                                            <h3>최근 작업</h3>
                                        </div>
                                    </div>
                                    <div id="queueJobsList" class="queue-item-list">
                                        <div class="collector-empty">등록된 작업이 없습니다.</div>
                                    </div>
                                </section>
                                <section class="settings-card queue-list-card">
                                    <div class="collector-panel-head">
                                        <div>
                                            <p class="panel-kicker">루틴</p>
                                            <h3>등록된 루틴</h3>
                                        </div>
                                    </div>
                                    <div id="queueRoutinesList" class="queue-item-list">
                                        <div class="collector-empty">등록된 루틴이 없습니다.</div>
                                    </div>
                                </section>
                            </div>
                            <div id="queueSnapshotStatus" class="collector-empty">
                                스케줄러 상태를 아직 불러오지 않았습니다.
                            </div>
                        </div>
                    </section>
                    <section class="utility-drawer-view" data-utility-panel="diagnostics">
                        <div class="debug-box">
                            <div class="debug-box-head">
                                <div>
                                    <p class="panel-kicker">진단</p>
                                    <h3>오류 및 진단</h3>
                                </div>
                                <button type="button" class="ghost-btn debug-clear-btn" id="clearDebugButton">진단 초기화</button>
                            </div>
                            <div id="errorConsole" class="error-console empty">오류가 발생하지 않았습니다.</div>
                            <div id="debugPanels" class="debug-panels"></div>
                        </div>
                    </section>
                    <section class="utility-drawer-view" data-utility-panel="logs" hidden>
                        <div class="panel-head">
                            <div>
                                <p class="panel-kicker">실행 로그</p>
                                <h2>실행 로그</h2>
                            </div>
                        </div>
                        <div class="log-box">
                            <div id="activityLog" class="activity-log"></div>
                        </div>
                    </section>
                </div>
            </section>
        </div>
    </div>
</body>
</html>
"""


def _render_static_shell(*, title: str, description: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(title)} | Keyword Forge</title>
    <meta name="description" content="{escape(description)}" />
    <link rel="stylesheet" href="/assets/app.css?v={_ASSET_VERSION}" />
</head>
<body>
    <div class="app-topbar">
        <div class="app-topbar-inner">
            <a class="app-topbar-brand" href="/#section-progress" aria-label="Keyword Forge 홈으로 이동">
                <span class="app-topbar-brand-mark">KF</span>
                <span class="app-topbar-brand-copy">
                    <strong>Keyword Forge</strong>
                    <span>Local-first keyword workflow</span>
                </span>
            </a>
            <nav class="app-topbar-links" aria-label="주요 탐색">
                <a class="app-topbar-link" href="/#section-controls">실행 조건</a>
                <a class="app-topbar-link" href="/#section-results">결과 작업대</a>
                <a class="app-topbar-link" href="/recommended-usage">도움말</a>
                <a class="app-topbar-link" href="/guides">가이드</a>
            </nav>
            <div class="app-topbar-actions">
                <a class="ghost-chip topbar-chip" href="/#utilityDrawer" data-utility-open="history">실행 기록</a>
                <a class="ghost-chip topbar-chip" href="/#utilityDrawer" data-utility-open="vault">보관함</a>
                <a class="ghost-chip topbar-chip" href="/#utilityDrawer" data-utility-open="queue">예약</a>
            </div>
        </div>
    </div>
    <div class="bg-orb bg-orb-a"></div>
    <div class="bg-orb bg-orb-b"></div>
    <div class="bg-grid"></div>
    {body}
</body>
</html>
"""


def _render_guide_card(guide: dict[str, object]) -> str:
    section_items = "".join(
        f"<li><strong>{escape(str(section['title']))}</strong><span>{escape(str(section['summary']))}</span></li>"
        for section in guide.get("sections", [])
        if str(section.get("title") or "").strip()
    )
    return f"""
        <article class="guide-article-card">
            <div class="guide-article-head">
                <h4>{escape(str(guide['title']))}</h4>
                <p>{escape(str(guide['subtitle']))}</p>
            </div>
            <ul class="guide-article-points">
                {section_items}
            </ul>
            <a class="secondary-link guide-article-link" href="/guides/{escape(str(guide['slug']))}">문서 보기</a>
        </article>
    """


def _render_guide_panel() -> str:
    guides = _load_study_guides()
    if not guides:
        return ""

    grouped: dict[str, list[dict[str, object]]] = {key: [] for key, _label, _keywords in _GUIDE_GROUPS}
    for guide in guides:
        group_key = str(guide.get("group") or "discovery")
        grouped.setdefault(group_key, []).append(guide)

    tab_buttons = "".join(
        f'<button type="button" class="guide-tab-button{" active" if index == 0 else ""}" '
        f'data-guide-tab="{escape(key)}">{escape(label)}</button>'
        for index, (key, label, _keywords) in enumerate(_GUIDE_GROUPS)
    )
    tab_panels = []
    for index, (key, _label, _keywords) in enumerate(_GUIDE_GROUPS):
        cards = "".join(_render_guide_card(guide) for guide in grouped.get(key, []))
        tab_panels.append(
            f"""
            <section class="guide-tab-panel{' active' if index == 0 else ''}" data-guide-panel="{escape(key)}" {'hidden' if index != 0 else ''}>
                <div class="guide-card-grid">
                    {cards if cards else '<div class="placeholder">해당 분류에 문서가 없습니다.</div>'}
                </div>
            </section>
            """
        )

    return f"""
        <section class="panel guide-panel">
            <div class="panel-head">
                <div>
                    <p class="panel-kicker">가이드</p>
                    <h2>사용 가이드</h2>
                </div>
                <span class="status-pill success">핵심 문서 {len(guides)}편</span>
            </div>
            <p class="input-help compact-help">
                현재 앱의 실제 흐름만 기준으로 정리한 문서입니다. 화면 구조와 기능이 바뀌면 이 문서 세트도 함께 갱신됩니다.
            </p>
            <div class="guide-tab-strip">
                {tab_buttons}
            </div>
            <div class="guide-tab-panels">
                {''.join(tab_panels)}
            </div>
        </section>
    """


def _render_guides_index() -> str:
    guides = _load_study_guides()
    grouped: dict[str, list[dict[str, object]]] = {key: [] for key, _label, _keywords in _GUIDE_GROUPS}
    for guide in guides:
        grouped.setdefault(str(guide.get("group") or "discovery"), []).append(guide)

    sections: list[str] = []
    for key, label, _keywords in _GUIDE_GROUPS:
        cards = "".join(_render_guide_card(guide) for guide in grouped.get(key, []))
        sections.append(
            f"""
            <section class="doc-section">
                <div class="doc-section-head">
                    <p class="panel-kicker">가이드 묶음</p>
                    <h2>{escape(label)}</h2>
                </div>
                <div class="guide-card-grid">
                    {cards if cards else '<div class="placeholder">해당 분류에 문서가 없습니다.</div>'}
                </div>
            </section>
            """
        )

    return _render_static_shell(
        title="사용 가이드",
        description="현재 Keyword Forge의 화면 구조와 기능을 기준으로 다시 정리한 사용 가이드입니다.",
        body=f"""
        <div class="doc-shell">
            <header class="doc-hero">
                <div class="doc-breadcrumbs"><a href="/">홈</a><span>/</span><strong>사용 가이드</strong></div>
                <div class="doc-actions">
                    <a class="secondary-link" href="/">대시보드</a>
                    <a class="secondary-link" href="/recommended-usage">추천 사용 순서</a>
                </div>
                <div class="doc-hero-copy">
                    <p class="eyebrow">가이드</p>
                    <h1>현재 버전 기준 운영 문서</h1>
                    <p>지금 화면 구조와 실제 동작에 맞는 설명만 추려서 다시 정리했습니다.</p>
                </div>
            </header>
            <main class="doc-stack">
                {''.join(sections)}
            </main>
        </div>
        """,
    )


def _render_guide_detail(guide_slug: str) -> str:
    guide = next((item for item in _load_study_guides() if str(item.get("slug")) == guide_slug), None)
    if guide is None:
        raise HTTPException(status_code=404, detail="가이드를 찾을 수 없습니다.")

    return _render_static_shell(
        title=str(guide["title"]),
        description=str(guide.get("subtitle") or ""),
        body=f"""
        <div class="doc-shell">
            <header class="doc-hero doc-hero-compact">
                <div class="doc-breadcrumbs">
                    <a href="/">홈</a><span>/</span><a href="/guides">사용 가이드</a><span>/</span><strong>{escape(str(guide['title']))}</strong>
                </div>
                <div class="doc-actions">
                    <a class="secondary-link" href="/guides">가이드 목록</a>
                    <a class="secondary-link" href="/recommended-usage">추천 사용 순서</a>
                </div>
                <div class="doc-hero-copy">
                    <p class="eyebrow">가이드 상세</p>
                    <h1>{escape(str(guide['title']))}</h1>
                    <p>{escape(str(guide.get('subtitle') or ''))}</p>
                </div>
            </header>
            <main class="doc-content">
                <article class="doc-article">
                    {str(guide.get("content_html") or "")}
                </article>
            </main>
        </div>
        """,
    )


def _render_recommended_usage() -> str:
    guides = {str(item["slug"]): item for item in _load_study_guides()}
    featured_slugs = (
        "quickstart-basics",
        "dual-axis-selection",
        "results-export-and-seedify",
    )
    featured_cards = "".join(
        _render_guide_card(guides[slug])
        for slug in featured_slugs
        if slug in guides
    )
    return _render_static_shell(
        title="추천 사용 순서",
        description="지금 앱에서 수익형 키워드를 빠르게 발굴하고 재활용하는 가장 실전적인 순서를 정리했습니다.",
        body=f"""
        <div class="doc-shell">
            <header class="doc-hero">
                <div class="doc-breadcrumbs">
                    <a href="/">홈</a><span>/</span><strong>추천 사용 순서</strong>
                </div>
                <div class="doc-actions">
                    <a class="secondary-link" href="/">대시보드</a>
                    <a class="secondary-link" href="/guides">사용 가이드</a>
                </div>
                <div class="doc-hero-copy">
                    <p class="eyebrow">추천 사용법</p>
                    <h1>누구나 바로 따라 할 수 있는 수익형 운영 루틴</h1>
                    <p>처음부터 모든 옵션을 건드리기보다, 발굴과 선별을 먼저 안정화한 뒤 좋은 후보만 제목과 보관함으로 넘기는 순서가 가장 수익화에 유리합니다.</p>
                </div>
            </header>
            <main class="doc-stack">
                <section class="panel">
                    <div class="panel-head">
                        <div>
                            <p class="panel-kicker">가장 쉬운 순서</p>
                            <h2>처음에는 이 5단계만 반복하세요</h2>
                        </div>
                    </div>
                    <ul class="guide-article-points">
                        <li><strong>1. 시작모드에서 키워드 발굴을 고릅니다.</strong><span>특별한 이유가 없으면 키워드 발굴부터 시작하는 편이 가장 무난합니다.</span></li>
                        <li><strong>2. 2축 선별은 전체나 균형형으로 먼저 넓게 봅니다.</strong><span>시드가 강한지 먼저 확인한 뒤 황금형이나 수익형으로 다시 조이는 편이 안정적입니다.</span></li>
                        <li><strong>3. 관련 설정 보기에서 수집 설정만 확인합니다.</strong><span>카테고리, 트렌드 날짜, 로그인 상태만 점검한 뒤 아래 실행 버튼에서 `키워드 발굴 실행`을 누르면 됩니다.</span></li>
                        <li><strong>4. 선별 결과가 뜨면 먼저 검토합니다.</strong><span>좋은 후보는 보관하거나 시드화하고, 필요할 때만 출력 및 복사로 외부 시트에 넘기면 됩니다.</span></li>
                        <li><strong>5. 선별된 키워드가 모이면 제목 생성으로 넘어갑니다.</strong><span>홈판, 블로그형, 둘다를 필요한 만큼만 켜고 상위 점수 결과만 고릅니다.</span></li>
                    </ul>
                </section>

                <section class="panel">
                    <div class="panel-head">
                        <div>
                            <p class="panel-kicker">상황별 프리셋</p>
                            <h2>목표에 따라 2축 시작점을 다르게 잡으세요</h2>
                        </div>
                    </div>
                    <div class="guide-card-grid">
                        <article class="guide-article-card">
                            <div class="guide-article-head">
                                <h4>처음 시장을 볼 때</h4>
                                <p>전체 또는 균형형으로 넓게 보고, 반응이 있는 주제만 다음 실행에서 더 조입니다.</p>
                            </div>
                        </article>
                        <article class="guide-article-card">
                            <div class="guide-article-head">
                                <h4>고단가 주제를 노릴 때</h4>
                                <p>수익형으로 묶고, 살아남은 후보를 시드화해서 더 작은 하위 시장까지 파고듭니다.</p>
                            </div>
                        </article>
                        <article class="guide-article-card">
                            <div class="guide-article-head">
                                <h4>롱테일 글감을 채울 때</h4>
                                <p>노출형이나 롱테일 탐색형으로 빈틈을 찾고, 선별 결과를 제목보다 먼저 보관함에 쌓는 편이 좋습니다.</p>
                            </div>
                        </article>
                    </div>
                </section>

                <section class="panel">
                    <div class="panel-head">
                        <div>
                            <p class="panel-kicker">바로 쓰는 기능</p>
                            <h2>선별 이후는 빠르게 재활용하는 것이 핵심입니다</h2>
                        </div>
                    </div>
                    <div class="guide-card-grid">
                        {featured_cards}
                    </div>
                </section>

                <section class="panel">
                    <div class="panel-head">
                        <div>
                            <p class="panel-kicker">운영 팁</p>
                            <h2>반복 수익을 위해 지켜둘 기본 원칙</h2>
                        </div>
                    </div>
                    <ul class="guide-article-points">
                        <li><strong>선별 0건도 버리지 마세요.</strong><span>확장과 분석 결과는 그대로 남으므로, 다음 시드와 프리셋을 고르는 재료가 됩니다.</span></li>
                        <li><strong>좋은 후보는 바로 시드화하거나 보관하세요.</strong><span>좋은 키워드는 한 번 보고 끝내지 않을수록 수익 기회가 늘어납니다.</span></li>
                        <li><strong>제목은 필요한 만큼만 만드세요.</strong><span>과하게 많이 만들기보다 홈판, 블로그형, 둘다 중 필요한 영역만 켜고 점수순으로 빠르게 고르는 편이 효율적입니다.</span></li>
                        <li><strong>실행 기록과 예약 큐를 같이 쓰세요.</strong><span>잘된 조합을 재현하고 시즌 키워드를 반복 공략할 수 있어 장기적으로 더 강합니다.</span></li>
                    </ul>
                </section>
            </main>
        </div>
        """,
    )


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def home() -> HTMLResponse:
    return HTMLResponse(_render_home())


@router.get("/guides", response_class=HTMLResponse, include_in_schema=False)
def guides_index() -> HTMLResponse:
    return HTMLResponse(_render_guides_index())


@router.get("/guides/{guide_slug}", response_class=HTMLResponse, include_in_schema=False)
def guide_detail(guide_slug: str) -> HTMLResponse:
    return HTMLResponse(_render_guide_detail(guide_slug))


@router.get("/recommended-usage", response_class=HTMLResponse, include_in_schema=False)
def recommended_usage() -> HTMLResponse:
    return HTMLResponse(_render_recommended_usage())


@router.get("/title-prompt-editor", response_class=HTMLResponse, include_in_schema=False)
def title_prompt_editor() -> HTMLResponse:
    return HTMLResponse(_render_title_prompt_editor())


@router.get("/title-quality-prompt-editor", response_class=HTMLResponse, include_in_schema=False)
def title_quality_prompt_editor() -> HTMLResponse:
    return HTMLResponse(_render_title_quality_prompt_editor())
