import pytest
from fastapi.testclient import TestClient

from app.core.title_prompt_settings import (
    reset_title_prompt_settings_for_tests,
    set_title_prompt_settings_path_for_tests,
    update_title_prompt_settings,
)
from app.main import app


client = TestClient(app)


@pytest.fixture(autouse=True)
def isolate_title_prompt_settings(tmp_path) -> None:
    set_title_prompt_settings_path_for_tests(tmp_path / "settings" / "title_prompt_settings.json")
    yield
    reset_title_prompt_settings_for_tests()


def test_title_prompt_editor_page_loads() -> None:
    response = client.get("/title-prompt-editor")

    assert response.status_code == 200
    assert "titlePromptEditorInput" in response.text
    assert "titlePromptProfileSelect" in response.text
    assert "titlePromptEffectivePreview" in response.text
    assert "KEYWORD_FORGE_TITLE_PROMPT_SETTINGS" in response.text


def test_title_quality_prompt_editor_page_loads() -> None:
    response = client.get("/title-quality-prompt-editor")

    assert response.status_code == 200
    assert "titleQualityPromptEditorInput" in response.text
    assert "titleQualityPromptProfileSelect" in response.text
    assert "titleQualityPromptPreview" in response.text
    assert "KEYWORD_FORGE_TITLE_PROMPT_SETTINGS" in response.text


def _legacy_recommended_usage_page_loads_early() -> None:
    response = client.get("/recommended-usage")

    assert response.status_code == 200
    assert "추천 사용 순서" in response.text
    assert "자동화 블로그 작성 기준 운영안" in response.text


def test_home_page_exposes_title_prompt_profile_picker() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "titlePromptProfilePicker" in response.text
    assert "titleQualityPromptProfilePicker" in response.text
    assert "openTitleQualityPromptEditorButton" in response.text
    assert "clearTitleQualityPromptButton" in response.text
    assert "titleQualitySystemPrompt" in response.text
    assert 'data-utility-open="settings"' in response.text
    assert 'data-utility-open="history"' in response.text
    assert 'data-utility-open="vault"' in response.text
    assert 'data-utility-open="queue"' in response.text
    assert 'data-utility-panel="settings"' in response.text
    assert 'data-utility-panel="history"' in response.text
    assert 'data-utility-panel="vault"' in response.text
    assert 'data-utility-panel="queue"' in response.text
    assert "operationMode" in response.text
    assert "operationCustomModeGuide" in response.text
    assert "operationCustomPresetPanel" in response.text
    assert "heroInputStatusValue" in response.text
    assert "heroSelectionStatusValue" in response.text
    assert "heroTitleStatusValue" in response.text
    assert "heroOperationStatusValue" in response.text
    assert "heroNaverLoginStatusValue" in response.text
    assert 'data-quickstart-mode-row="discover"' in response.text
    assert 'data-quickstart-help="discover"' in response.text
    assert 'data-quickstart-settings="discover"' in response.text
    assert "빠른 수집 입력" in response.text
    assert "expandMaxResultsInput" in response.text
    assert "runExpandButton" in response.text
    assert "runAnalyzeButton" in response.text
    assert "runTitleButton" in response.text
    assert "runGradeSelectButton" in response.text
    assert 'href="#section-select"' in response.text
    assert "openApiRegistrySettingsButton" in response.text
    assert "titleProviderRegistryHint" in response.text
    assert "titleCustomPresetPicker" in response.text
    assert "saveTitleCustomPresetButton" in response.text
    assert "deleteTitleCustomPresetButton" in response.text
    assert "titleRewriteProvider" in response.text
    assert "titleRewriteModel" in response.text
    assert "title-ai-layout" in response.text
    assert "resultStageDock" in response.text
    assert "recoveryGuide" in response.text
    assert "apiRegistryOpenaiKey" in response.text
    assert "saveTitleApiRegistryButton" in response.text
    assert "submitQueueSeedBatchButton" in response.text
    assert "toggleTitleAdvancedButton" in response.text
    assert 'href="/recommended-usage"' in response.text
    assert "추천 사용 순서" in response.text
    assert "titleIssueSourceMode" in response.text
    assert "titleCommunityCustomDomains" in response.text
    assert "data-title-community-source" in response.text
    assert "titleSurfaceHome" in response.text
    assert "titleSurfaceBlog" in response.text
    assert "titleSurfaceHybrid" in response.text
    assert "titleSurfaceHomeCount" in response.text
    assert "titleSurfaceBlogCount" in response.text
    assert "titleSurfaceHybridCount" in response.text
    assert "titleSurfaceSummary" in response.text
    assert "보유 키워드 분석" in response.text
    assert "조합 적용 + 선별 실행" in response.text
    assert "황금형" in response.text
    assert "노출형" in response.text
    assert "gradeSelectDescription" in response.text
    assert "롱테일 탐색형" in response.text
    assert "data-queue-category" in response.text
    assert "localCookieStatus" in response.text
    assert "loadLocalCookieButton" in response.text
    assert "현재 브라우저 쿠키 읽기" in response.text
    assert "전용 로그인 브라우저 열기" in response.text
    assert "executionHistoryList" in response.text
    assert "keywordVaultList" in response.text
    assert "topicSeedInput" in response.text
    assert "generateTopicSeedsButton" in response.text
    assert "validateTrendSessionButton" in response.text
    assert "로그인 상태 확인" in response.text
    assert "exportExpandedCsvButton" in response.text
    assert "exportExpandedTxtButton" in response.text
    assert "copyCollectedLinesButton" in response.text
    assert "copyCollectedCommaButton" in response.text
    assert "copyExpandedLinesButton" in response.text
    assert "copyExpandedCommaButton" in response.text
    assert "copyAnalyzedLinesButton" in response.text
    assert "copyAnalyzedCommaButton" in response.text
    assert "copySelectedLinesButton" in response.text
    assert "copySelectedCommaButton" in response.text
    assert "exportSelectedTxtButton" in response.text
    assert "resultsExportExpandedCsvButton" in response.text
    assert "resultsExportExpandedTxtButton" in response.text
    assert "resultsPanelTools" in response.text
    assert "키워드 발굴" in response.text
    assert "보유 키워드 분석" in response.text
    assert "2축 선별" in response.text
    assert "resultsCopyCollectedLinesButton" in response.text
    assert "resultsCopyCollectedCommaButton" in response.text
    assert "resultsCopyExpandedLinesButton" in response.text
    assert "resultsCopyExpandedCommaButton" in response.text
    assert "resultsCopyAnalyzedLinesButton" in response.text
    assert "resultsCopyAnalyzedCommaButton" in response.text
    assert "resultsCopySelectedLinesButton" in response.text
    assert "resultsCopySelectedCommaButton" in response.text
    assert "resultsExportSelectedTxtButton" in response.text


def test_home_page_injects_repo_backed_title_prompt_settings() -> None:
    update_title_prompt_settings(
        {
            "preset_key": "openai_balanced",
            "direct_system_prompt": "공유 프롬프트",
            "system_prompt": "공유 프롬프트",
            "prompt_profiles": [],
            "active_prompt_profile_id": "",
        }
    )

    response = client.get("/")

    assert response.status_code == 200
    assert "KEYWORD_FORGE_TITLE_PROMPT_SETTINGS" in response.text
    assert "공유 프롬프트" in response.text

def test_home_page_injects_custom_title_preset_profiles() -> None:
    update_title_prompt_settings(
        {
            "preset_profiles": [
                {
                    "id": "preset-1",
                    "name": "Custom preset",
                    "provider": "openai",
                    "model": "gpt-4.1-mini",
                    "temperature": 0.7,
                }
            ],
            "active_preset_profile_id": "preset-1",
        }
    )

    response = client.get("/")

    assert response.status_code == 200
    assert "Custom preset" in response.text


def _legacy_recommended_usage_page_loads() -> None:
    response = client.get("/recommended-usage")

    assert response.status_code == 200
    assert "추천 사용 순서" in response.text
    assert "누구나 바로 따라 할 수 있는 수익형 운영 루틴" in response.text
    assert "/guides/quickstart-basics" in response.text


def test_guides_index_page_loads_app_specific_docs() -> None:
    response = client.get("/guides")

    assert response.status_code == 200
    assert "현재 버전 기준 운영 문서" in response.text
    assert "/guides/dual-axis-selection" in response.text
    assert "지금 화면 구조와 실제 동작에 맞는 설명만 추려서 다시 정리했습니다." in response.text


def test_guide_detail_page_loads_app_specific_content() -> None:
    response = client.get("/guides/dual-axis-selection")

    assert response.status_code == 200
    assert "2축 선별을 제대로 쓰는 방법" in response.text
    assert "수익성과 노출도는 비슷해 보여도 역할이 다릅니다" in response.text
