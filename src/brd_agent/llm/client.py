"""LiteLLM client wrapper used by BRD analyzer."""

try:
    from litellm import completion as litellm_completion
except ImportError:
    litellm_completion = None


class LiteLLMClient(object):
    """Thin synchronous wrapper around LiteLLM completion API."""

    def __init__(
        self,
        model_name,
        api_key=None,
        base_url=None,
        completion_fn=None,
    ):
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url
        self.completion_fn = completion_fn or litellm_completion

    def complete(self, system_prompt, user_prompt, temperature=0.0):
        """Execute a chat completion and return response text."""
        if self.completion_fn is None:
            raise RuntimeError(
                "litellm is not available. Install project dependencies first."
            )

        request = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }
        if self.api_key:
            request["api_key"] = self.api_key
        if self.base_url:
            request["base_url"] = self.base_url

        response = self.completion_fn(**request)
        return self._extract_text(response)

    @staticmethod
    def _extract_text(response):
        if isinstance(response, dict):
            choices = response.get("choices", [])
            if not choices:
                raise RuntimeError("LiteLLM response has no choices.")
            message = choices[0].get("message", {})
            content = message.get("content", "")
        else:
            choices = getattr(response, "choices", [])
            if not choices:
                raise RuntimeError("LiteLLM response has no choices.")
            message = getattr(choices[0], "message", None)
            if message is None:
                raise RuntimeError("LiteLLM response has no message content.")
            content = getattr(message, "content", "")

        if isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
            content = "\n".join(text_parts)

        if not isinstance(content, str):
            raise RuntimeError("LiteLLM response content is not a string.")
        return content.strip()
