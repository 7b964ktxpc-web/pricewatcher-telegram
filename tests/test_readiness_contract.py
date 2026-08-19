import main
from fastapi.testclient import TestClient


def test_readiness_handles_structured_feed_report(monkeypatch):
    monkeypatch.setattr(
        main,
        "adapter_status",
        lambda: [
            {"name": "simaland", "configured": True},
            {"name": "wildberries", "configured": False},
        ],
        raising=False,
    )
    monkeypatch.setattr(
        main,
        "inspect_feeds",
        lambda: {
            "checked": 2,
            "configured": ["simaland"],
            "results": [
                {"name": "simaland", "configured": True},
                {"name": "detmir", "configured": False},
            ],
        },
        raising=False,
    )
    monkeypatch.setattr(
        main,
        "chat_status",
        lambda: {"qwen": False, "deepseek_configured": False, "groq_configured": False, "gemini_configured": False, "providers": []},
        raising=False,
    )
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")

    response = TestClient(main.app).get("/api/readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["feeds"]["configured"] == 1
    assert body["feeds"]["total"] == 2
    assert body["feeds"]["items"]["configured"] == ["simaland"]
