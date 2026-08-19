from ai_router import AIRouter


def test_router_rejects_empty_request():
    result = AIRouter().route("   ")
    assert result["ok"] is False
    assert result["error"] == "empty_request"


def test_router_has_primary_qwen_agent():
    names = [agent.name for agent in AIRouter().agents()]
    assert "qwen_hf" in names
