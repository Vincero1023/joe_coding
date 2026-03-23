from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_title_prompt_editor_page_loads() -> None:
    response = client.get("/title-prompt-editor")

    assert response.status_code == 200
    assert "titlePromptEditorInput" in response.text
    assert "titlePromptProfileSelect" in response.text
    assert "titlePromptEffectivePreview" in response.text


def test_recommended_usage_page_loads() -> None:
    response = client.get("/recommended-usage")

    assert response.status_code == 200
    assert "추천 사용법" in response.text
    assert "자동화 블로그 작성 기준 운영안" in response.text


def test_home_page_exposes_title_prompt_profile_picker() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "titlePromptProfilePicker" in response.text
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
    assert "저장된 전용 로그인 세션" in response.text
    assert "executionHistoryList" in response.text
    assert "keywordVaultList" in response.text
    assert "topicSeedInput" in response.text
    assert "generateTopicSeedsButton" in response.text
