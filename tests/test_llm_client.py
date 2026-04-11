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
