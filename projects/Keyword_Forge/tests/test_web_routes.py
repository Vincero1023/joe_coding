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


def test_recommended_usage_page_loads() -> None:
    response = client.get("/recommended-usage")

    assert response.status_code == 200
    assert "추천 사용법" in response.text
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
    assert "quickStartPrimaryButton" in response.text
    assert 'data-quickstart-mode="discover"' in response.text
    assert "openApiRegistrySettingsButton" in response.text
    assert "titleProviderRegistryHint" in response.text
    assert "titleCustomPresetPicker" in response.text
    assert "saveTitleCustomPresetButton" in response.text
    assert "deleteTitleCustomPresetButton" in response.text
    assert "titleRewriteProvider" in response.text
    assert "titleRewriteModel" in response.text
    assert "title-ai-layout" in response.text
    assert "resultStageDock" in response.text
    assert "apiRegistryOpenaiKey" in response.text
    assert "saveTitleApiRegistryButton" in response.text
    assert "submitQueueSeedBatchButton" in response.text
    assert "toggleTitleAdvancedButton" in response.text
    assert 'href="/recommended-usage"' in response.text
    assert "추천 사용법" in response.text
    assert "titleIssueSourceMode" in response.text
    assert "titleCommunityCustomDomains" in response.text
    assert "data-title-community-source" in response.text
    assert "자동 선별" in response.text
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
    assert "exportSelectedTxtButton" in response.text
    assert "resultsExportExpandedCsvButton" in response.text
    assert "resultsExportExpandedTxtButton" in response.text
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
