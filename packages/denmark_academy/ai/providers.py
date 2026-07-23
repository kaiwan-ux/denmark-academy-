from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from hashlib import sha256
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from pydantic import SecretStr

from denmark_academy.ai.schemas import AICompletionRequest, AICompletionResponse, AIProviderKey
from denmark_academy.config import Settings, get_settings
from denmark_academy.ai.api_key_manager import get_api_key_manager


class AIProvider(ABC):
    provider_key: AIProviderKey

    @abstractmethod
    async def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        raise NotImplementedError


class AIProviderError(RuntimeError):
    """Raised when an upstream provider call fails without exposing secrets."""


class DisabledProvider(AIProvider):
    provider_key: AIProviderKey = "disabled"

    async def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        digest = sha256("\n".join(message.content for message in request.messages).encode("utf-8")).hexdigest()[:12]
        content = (
            "AI provider is disabled. Deterministic draft generated for workflow validation. "
            f"Reference hash: {digest}. Admin review is required before publication."
        )
        return AICompletionResponse(
            provider="disabled",
            model=request.model,
            content=content,
            raw={"mode": "disabled", "reference_hash": digest},
            token_usage={"input_tokens": sum(len(m.content.split()) for m in request.messages), "output_tokens": len(content.split())},
        )


class ExternalProviderPlaceholder(AIProvider):
    def __init__(self, provider_key: AIProviderKey) -> None:
        self.provider_key = provider_key

    async def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        raise AIProviderError(
            f"Provider {self.provider_key} is configured but no API key/client is enabled in this environment."
        )


class OpenAICompatibleChatProvider(AIProvider):
    def __init__(
        self,
        provider_key: AIProviderKey,
        api_key: SecretStr,
        base_url: str,
        default_model: str,
        timeout_seconds: float,
    ) -> None:
        self.provider_key = provider_key
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout_seconds = timeout_seconds

    async def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        model = _resolved_model(request.model, self.default_model)
        payload = {
            "model": model,
            "messages": [message.model_dump(mode="json") for message in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        data = await asyncio.to_thread(
            _post_json,
            f"{self.base_url}/chat/completions",
            payload,
            {"Authorization": f"Bearer {self.api_key.get_secret_value()}"},
            self.timeout_seconds,
        )
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        content = message.get("content") or ""
        usage = data.get("usage") or {}
        return AICompletionResponse(
            provider=self.provider_key,
            model=model,
            content=content,
            raw={"id": data.get("id"), "finish_reason": choice.get("finish_reason")},
            token_usage={
                "input_tokens": int(usage.get("prompt_tokens") or 0),
                "output_tokens": int(usage.get("completion_tokens") or 0),
            },
        )


class GeminiChatProvider(AIProvider):
    provider_key: AIProviderKey = "gemini"

    def __init__(self, api_key: SecretStr, base_url: str, default_model: str, timeout_seconds: float) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout_seconds = timeout_seconds

    async def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        model = _resolved_model(request.model, self.default_model)
        system_text = "\n\n".join(message.content for message in request.messages if message.role == "system")
        contents: list[dict[str, Any]] = []
        for message in request.messages:
            if message.role == "system":
                continue
            role = "model" if message.role == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": message.content}]})
        if not contents:
            contents.append({"role": "user", "parts": [{"text": system_text or "Generate the requested educational content."}]})
        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {"temperature": request.temperature, "maxOutputTokens": request.max_tokens},
        }
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}
        url = f"{self.base_url}/models/{quote(model, safe='')}:generateContent?key={quote(self.api_key.get_secret_value(), safe='')}"
        data = await asyncio.to_thread(_post_json, url, payload, {}, self.timeout_seconds)
        candidate = (data.get("candidates") or [{}])[0]
        parts = ((candidate.get("content") or {}).get("parts") or [])
        content = "".join(part.get("text", "") for part in parts)
        usage = data.get("usageMetadata") or {}
        return AICompletionResponse(
            provider="gemini",
            model=model,
            content=content,
            raw={"finish_reason": candidate.get("finishReason")},
            token_usage={
                "input_tokens": int(usage.get("promptTokenCount") or 0),
                "output_tokens": int(usage.get("candidatesTokenCount") or 0),
            },
        )


class AIProviderRegistry:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._providers: dict[AIProviderKey, AIProvider] = {
            "disabled": DisabledProvider(),
            "openai": ExternalProviderPlaceholder("openai"),
            "anthropic": ExternalProviderPlaceholder("anthropic"),
            "grok": ExternalProviderPlaceholder("grok"),
            "gemini": ExternalProviderPlaceholder("gemini"),
        }
        key_manager = get_api_key_manager()
        grok_key = key_manager.get_next_grok_key()
        gemini_key = key_manager.get_next_gemini_key()
        if grok_key:
            self._providers["grok"] = OpenAICompatibleChatProvider(
                "grok",
                grok_key,
                self.settings.grok_base_url,
                self.settings.grok_model,
                self.settings.ai_request_timeout_seconds,
            )
        if gemini_key:
            self._providers["gemini"] = GeminiChatProvider(
                gemini_key,
                self.settings.gemini_base_url,
                self.settings.gemini_model,
                self.settings.ai_request_timeout_seconds,
            )
    def get(self, provider_key: AIProviderKey) -> AIProvider:
        return self._providers[provider_key]

    def default_model_for(self, provider_key: AIProviderKey) -> str:
        if provider_key == "grok":
            return self.settings.grok_model
        if provider_key == "gemini":
            return self.settings.gemini_model
        if provider_key == "disabled":
            return "disabled-local"
        return "default"


class AIGateway:
    def __init__(self, registry: AIProviderRegistry | None = None, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.registry = registry or AIProviderRegistry(self.settings)

    async def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        provider_key = self._resolve_provider(request.provider)
        routed_request = request.model_copy(update={"provider": provider_key, "model": self._resolve_model(request.model, provider_key)})
        try:
            provider = self.registry.get(provider_key)
            return await provider.complete(routed_request)
        except Exception as exc:
            fallback_key = self._resolve_fallback(provider_key)
            if fallback_key is None:
                raise
            fallback_request = request.model_copy(update={"provider": fallback_key, "model": self._resolve_model(request.model, fallback_key)})
            fallback_provider = self.registry.get(fallback_key)
            try:
                response = await fallback_provider.complete(fallback_request)
                response.raw = {
                    **response.raw,
                    "fallback_from": provider_key,
                    "fallback_error": _safe_error(exc),
                }
                return response
            except Exception as fallback_exc:
                disabled_response = await self.registry.get("disabled").complete(
                    request.model_copy(update={"provider": "disabled", "model": "disabled-local"})
                )
                disabled_response.raw = {
                    **disabled_response.raw,
                    "fallback_from": provider_key,
                    "fallback_provider": fallback_key,
                    "primary_error": _safe_error(exc),
                    "fallback_error": _safe_error(fallback_exc),
                    "degraded": True,
                }
                return disabled_response

    def _resolve_provider(self, requested: AIProviderKey) -> AIProviderKey:
        if requested == "disabled" and self.settings.ai_primary_provider != "disabled":
            return _provider_key(self.settings.ai_primary_provider)
        return requested

    def _resolve_fallback(self, failed_provider: AIProviderKey) -> AIProviderKey | None:
        fallback = _provider_key(self.settings.ai_fallback_provider)
        if fallback == "disabled" or fallback == failed_provider:
            return None
        return fallback

    def _resolve_model(self, requested_model: str, provider_key: AIProviderKey) -> str:
        if not requested_model or requested_model == "disabled-local":
            return self.registry.default_model_for(provider_key)
        return requested_model


def _provider_key(value: str) -> AIProviderKey:
    normalized = value.strip().lower()
    if normalized in {"disabled", "openai", "anthropic", "gemini", "grok"}:
        return normalized  # type: ignore[return-value]
    raise ValueError(f"Unsupported AI provider: {value}")


def _resolved_model(requested_model: str, default_model: str) -> str:
    return default_model if not requested_model or requested_model == "disabled-local" else requested_model


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout_seconds: float) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json", **headers},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")[:500]
        raise AIProviderError(f"Provider HTTP {exc.code}: {details}") from exc
    except URLError as exc:
        raise AIProviderError(f"Provider network error: {exc.reason}") from exc
    except TimeoutError as exc:
        raise AIProviderError("Provider request timed out") from exc


def _safe_error(exc: Exception) -> str:
    return str(exc).replace("Bearer ", "Bearer [redacted] ")[:500]




