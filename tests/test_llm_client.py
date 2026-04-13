from brd_agent.llm.client import LiteLLMClient


def test_litellm_client_can_be_mocked_cleanly():
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"project_name":"Demo"}',
                    }
                }
            ]
        }

    client = LiteLLMClient(
        model_name="fake-model",
        api_key="fake-key",
        base_url="https://example.test",
        completion_fn=fake_completion,
    )
    response_text = client.complete(
        system_prompt="system",
        user_prompt="user",
        temperature=0.25,
    )

    assert response_text == '{"project_name":"Demo"}'
    assert captured["model"] == "fake-model"
    assert captured["api_key"] == "fake-key"
    assert captured["base_url"] == "https://example.test"
    assert captured["temperature"] == 0.25
    assert captured["messages"][0]["role"] == "system"
    assert captured["messages"][1]["role"] == "user"


def test_http_fallback_uses_openai_compatible_endpoint():
    import brd_agent.llm.client as client_module

    captured = {}

    class FakeResponse(object):
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"project_name":"FromHTTP"}',
                        }
                    }
                ]
            }

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers or {}
        captured["json"] = json or {}
        captured["timeout"] = timeout
        return FakeResponse()

    original_completion = client_module.litellm_completion
    client_module.litellm_completion = None
    try:
        client = LiteLLMClient(
            model_name="anthropic/claude-3-5-sonnet-20241022",
            api_key="fake-key",
            base_url="https://llmrouter.gft.com",
            completion_fn=None,
            http_post_fn=fake_post,
        )
        response_text = client.complete(
            system_prompt="system",
            user_prompt="user",
            temperature=0.2,
        )
    finally:
        client_module.litellm_completion = original_completion

    assert response_text == '{"project_name":"FromHTTP"}'
    assert captured["url"] == "https://llmrouter.gft.com/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer fake-key"
    assert captured["json"]["model"] == "anthropic/claude-3-5-sonnet-20241022"
