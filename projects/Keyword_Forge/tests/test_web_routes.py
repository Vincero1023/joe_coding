from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_title_prompt_editor_page_loads() -> None:
    response = client.get("/title-prompt-editor")

    assert response.status_code == 200
    assert "titlePromptEditorInput" in response.text
