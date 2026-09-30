"""The single place that talks to Claude. Everything else depends on the small `LLM` interface,
so tests (and any future provider) plug in without touching the safety logic."""

from typing import Protocol

from django.conf import settings


class LLMError(Exception):
    """The model call failed for a reason the user cannot fix (network, quota, refusal)."""


class LLM(Protocol):
    model: str

    def complete(self, system: str, user: str) -> str: ...


# One attempt, 20 s: the API function is stopped at 30 s, and a retry on top of a slow first
# attempt would be killed before the failure could be logged and shown.
class AnthropicLLM:
    def __init__(self, api_key: str, model: str):
        import anthropic

        self._anthropic = anthropic
        self._client = anthropic.Anthropic(api_key=api_key, timeout=20.0, max_retries=0)
        self.model = model

    def complete(self, system: str, user: str) -> str:
        a = self._anthropic
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=system,
                output_config={"effort": "low"},
                messages=[{"role": "user", "content": user}],
            )
        except a.RateLimitError as exc:
            raise LLMError("The assistant is busy. Try again shortly.") from exc
        except a.APIConnectionError as exc:
            raise LLMError("Could not reach the model service.") from exc
        except a.APIStatusError as exc:
            raise LLMError(f"The model service returned an error ({exc.status_code}).") from exc
        if response.stop_reason == "refusal":
            raise LLMError("The model declined to answer this question.")
        if response.stop_reason == "max_tokens":
            raise LLMError("The answer was cut off.")
        return "".join(b.text for b in response.content if b.type == "text")


def get_llm() -> LLM | None:
    """None when no API key is configured: the assistant then only lists matching records."""
    key = getattr(settings, "ANTHROPIC_API_KEY", "")
    if not key:
        return None
    return AnthropicLLM(key, getattr(settings, "ASSISTANT_MODEL", "claude-opus-5-5"))
