from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_title_prompt_editor_page_loads() -> None:
    response = client.get("/title-prompt-editor")

    assert response.status_code == 200
    assert "titlePromptEditorInput" in response.text
    assert "titlePromptProfileSelect" in response.text
    assert "titlePromptEffectivePreview" in response.text


def test_home_page_exposes_title_prompt_profile_picker() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "titlePromptProfilePicker" in response.text
    assert 'data-utility-open="settings"' in response.text
    assert 'data-utility-panel="settings"' in response.text
    assert "operationMode" in response.text
