from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.title.topic_seed_generator import generate_topic_seed_keywords


def test_topic_seed_generator_returns_seed_keywords() -> None:
    with patch(
        "app.title.topic_seed_generator._post_json",
        return_value={
            "choices": [
                {
                    "message": {
                        "content": '{"seed_keywords":["자취 가전 추천","원룸 제습기","미니 건조기 비교","전기포트 추천"]}',
                    }
                }
            ]
        },
    ):
        result = generate_topic_seed_keywords(
            {
                "topic": "자취 가전",
                "intent": "balanced",
                "count": 4,
                "title_options": {
                    "mode": "ai",
                    "provider": "openai",
                    "api_key": "test-key",
                    "model": "gpt-4o-mini",
                },
            }
        )

    assert result["provider"] == "openai"
    assert result["model"] == "gpt-4o-mini"
    assert result["intent"] == "balanced"
    assert result["seed_keywords"] == [
        "자취 가전 추천",
        "원룸 제습기",
        "미니 건조기 비교",
        "전기포트 추천",
    ]


def test_topic_seed_api_returns_module_response() -> None:
    client = TestClient(app)

    with patch(
        "app.title.topic_seed_generator._post_json",
        return_value={
            "choices": [
                {
                    "message": {
                        "content": '{"seed_keywords":["포터블 모니터","휴대용 모니터 추천","터치 포터블 모니터"]}',
                    }
                }
            ]
        },
    ):
        response = client.post(
            "/topic-seeds",
            json={
                "input_data": {
                    "topic": "포터블 모니터",
                    "intent": "need",
                    "count": 3,
                    "title_options": {
                        "mode": "ai",
                        "provider": "openai",
                        "api_key": "test-key",
                        "model": "gpt-4o-mini",
                    },
                }
            },
        )

    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["intent"] == "need"
    assert payload["seed_keywords"][0] == "포터블 모니터"
    assert len(payload["seed_keywords"]) == 3
