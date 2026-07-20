"""Provider-agnostic LLM backend.

The mediator's reasoning is decoupled from any single vendor. A provider takes a
system prompt + a list of ``{"role": "user"|"assistant", "content": ...}`` messages
and returns the assistant's reply text. Two backends ship in-box:

- ``anthropic`` — the official Anthropic SDK (Claude).
- ``openai``    — the official OpenAI SDK, which also speaks to any
  OpenAI-compatible endpoint (Azure OpenAI, Ollama, LM Studio, OpenRouter, vLLM,
  Together, …) via the ``OPENAI_BASE_URL`` env var.

Select the provider in ``config.yaml`` (``provider:``) or the ``MEDIATOR_PROVIDER``
env var. Each provider reads its own credentials from the environment, so no API
key is ever hard-coded here.
"""

import os
from typing import Protocol


# Sensible default model per provider when config doesn't pin one.
_DEFAULT_MODELS = {
    "anthropic": "claude-opus-4-8",
    "openai": "gpt-4o",
}


class LLMProvider(Protocol):
    """Anything that can turn a system prompt + messages into reply text."""

    def complete(self, *, system: str, messages: list[dict], model: str, max_tokens: int) -> str:
        ...


class AnthropicProvider:
    """Claude via the official ``anthropic`` SDK.

    Credentials resolve from the environment (``ANTHROPIC_API_KEY``, or an
    ``ant auth login`` profile) — the zero-arg client handles the lookup.
    """

    def __init__(self, options: dict | None = None) -> None:
        import anthropic

        self._client = anthropic.Anthropic()

    def complete(self, *, system: str, messages: list[dict], model: str, max_tokens: int) -> str:
        resp = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        return "".join(b.text for b in resp.content if b.type == "text").strip()


class OpenAIProvider:
    """OpenAI (and any OpenAI-compatible endpoint) via the official ``openai`` SDK.

    Credentials and endpoint resolve from the environment: ``OPENAI_API_KEY`` and
    the optional ``OPENAI_BASE_URL`` (point it at Azure OpenAI, Ollama, LM Studio,
    OpenRouter, etc.). A ``base_url`` in the provider options overrides the env var.
    """

    def __init__(self, options: dict | None = None) -> None:
        from openai import OpenAI

        opts = options or {}
        base_url = opts.get("base_url") or os.environ.get("OPENAI_BASE_URL")
        self._client = OpenAI(base_url=base_url) if base_url else OpenAI()

    def complete(self, *, system: str, messages: list[dict], model: str, max_tokens: int) -> str:
        # OpenAI carries the system prompt as the first message rather than a
        # dedicated field; the user/assistant roles map across unchanged.
        chat = [{"role": "system", "content": system}, *messages]
        resp = self._client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=chat,
        )
        return (resp.choices[0].message.content or "").strip()


_PROVIDERS = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
}


def resolve_provider_name(config: dict) -> str:
    return (
        os.environ.get("MEDIATOR_PROVIDER")
        or config.get("provider")
        or "anthropic"
    ).lower()


def default_model(provider_name: str) -> str:
    return _DEFAULT_MODELS.get(provider_name, _DEFAULT_MODELS["anthropic"])


def get_provider(config: dict) -> tuple[LLMProvider, str]:
    """Build the configured provider and resolve its model.

    Returns ``(provider, model)``. Per-provider options may be given under a
    ``providers:`` map in config, e.g. ``providers: {openai: {base_url: ...}}``.
    """
    name = resolve_provider_name(config)
    if name not in _PROVIDERS:
        raise ValueError(
            f"Unknown provider '{name}'. Available: {', '.join(sorted(_PROVIDERS))}."
        )
    options = (config.get("providers") or {}).get(name, {})
    model = config.get("model") or options.get("model") or default_model(name)
    provider = _PROVIDERS[name](options)
    return provider, model
