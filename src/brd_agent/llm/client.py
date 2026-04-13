"""LiteLLM client wrapper with resilient HTTP fallback."""

import os

try:
    from litellm import completion as litellm_completion
except Exception:
    # Some environments install litellm but fail import at runtime
    # (for example, due to pydantic major-version mismatches).
    litellm_completion = None


class LiteLLMClient(object):
    """Thin synchronous wrapper around LiteLLM completion API."""

    def __init__(
        self,
        model_name,
        api_key=None,
        base_url=None,
        completion_fn=None,
        http_post_fn=None,
    ):
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url
        self.completion_fn = completion_fn
        self.http_post_fn = http_post_fn

    def complete(self, system_prompt, user_prompt, temperature=0.0):
        """Execute a chat completion and return response text."""
        if self.completion_fn is not None:
            return self._complete_via_litellm(
                self.completion_fn,
                system_prompt,
                user_prompt,
                temperature,
            )
        if litellm_completion is not None:
            return self._complete_via_litellm(
                litellm_completion,
                system_prompt,
                user_prompt,
                temperature,
            )
        return self._complete_via_http(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
        )

    def _complete_via_litellm(self, completion_fn, system_prompt, user_prompt, temperature):
        """Execute completion through litellm-compatible callable."""
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

        response = completion_fn(**request)
        return self._extract_text(response)

    def _complete_via_http(self, system_prompt, user_prompt, temperature):
        """Fallback client when litellm import is unavailable."""
        if self.base_url:
            return self._complete_via_openai_compatible_http(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
            )

        if self.model_name.startswith("anthropic/") or self.model_name.startswith("claude-"):
            return self._complete_via_anthropic_http(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
            )

        raise RuntimeError(
            "litellm is unavailable and no compatible HTTP route was configured. "
            "Set *_LLM_BASE_URL for your router or use an anthropic/* model."
        )

    def _complete_via_openai_compatible_http(self, system_prompt, user_prompt, temperature):
        post = self._http_post_callable()
        base_url = self.base_url.rstrip("/")
        endpoint = "{0}/chat/completions".format(base_url)
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer {0}".format(self.api_key)

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }

        response = post(endpoint, headers=headers, json=payload, timeout=120)
        self._raise_for_status(response)
        return self._extract_text(response.json())

    def _complete_via_anthropic_http(self, system_prompt, user_prompt, temperature):
        post = self._http_post_callable()
        api_key = self.api_key or os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_FOUNDRY_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Anthropic API key is missing. Set *_LLM_API_KEY or ANTHROPIC_API_KEY."
            )

        base_url = (
            self.base_url
            or os.getenv("ANTHROPIC_BASE_URL")
            or "https://api.anthropic.com"
        ).rstrip("/")
        endpoint = "{0}/v1/messages".format(base_url)
        model = self.model_name.replace("anthropic/", "")

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "max_tokens": 4096,
            "temperature": temperature,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }

        response = post(endpoint, headers=headers, json=payload, timeout=120)
        self._raise_for_status(response)
        payload = response.json()
        content = payload.get("content", [])
        text_parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text_parts.append(part.get("text", ""))
        text = "\n".join(text_parts).strip()
        if not text:
            raise RuntimeError("Anthropic response did not contain text content.")
        return text

    @staticmethod
    def _raise_for_status(response):
        if hasattr(response, "raise_for_status"):
            response.raise_for_status()

    def _http_post_callable(self):
        if self.http_post_fn is not None:
            return self.http_post_fn

        try:
            import requests
        except Exception as error:
            raise RuntimeError(
                "HTTP fallback requires requests package: {0}".format(error)
            )
        return requests.post

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
