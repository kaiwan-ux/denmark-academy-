import pytest

from denmark_academy.ai.analytics import AIAnalyticsService
from denmark_academy.ai.evaluation import AIEvaluator
from denmark_academy.ai.prompt_builder import PromptBuilder
from denmark_academy.ai.providers import AIGateway, AIProvider, AIProviderError
from denmark_academy.ai.schemas import (
    AICompletionRequest,
    AICompletionResponse,
    AIMockComposition,
    EvaluationRequest,
    PromptBuildRequest,
    PromptMessage,
    RetrievedSource,
)
from denmark_academy.config import Settings


class FailingProvider(AIProvider):
    provider_key = "grok"

    async def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        raise AIProviderError("primary provider unavailable")


class EchoProvider(AIProvider):
    provider_key = "gemini"

    async def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        return AICompletionResponse(
            provider="gemini",
            model=request.model,
            content="fallback response",
            raw={},
            token_usage={"input_tokens": 1, "output_tokens": 2},
        )


class FakeRegistry:
    def __init__(self) -> None:
        self.providers = {"grok": FailingProvider(), "gemini": EchoProvider(), "disabled": EchoProvider()}

    def get(self, provider_key):
        return self.providers[provider_key]

    def default_model_for(self, provider_key):
        return {"grok": "primary-model", "gemini": "fallback-model", "disabled": "disabled-local"}[provider_key]


@pytest.mark.asyncio
async def test_disabled_provider_returns_deterministic_response():
    response = await AIGateway(settings=Settings(ai_primary_provider="disabled", ai_fallback_provider="disabled")).complete(
        AICompletionRequest(
            purpose="explanation",
            messages=[PromptMessage(role="user", content="Explain the constitution")],
        )
    )
    assert response.provider == "disabled"
    assert "Deterministic draft" in response.content


@pytest.mark.asyncio
async def test_gateway_uses_configured_fallback_provider():
    response = await AIGateway(
        registry=FakeRegistry(),
        settings=Settings(ai_primary_provider="grok", ai_fallback_provider="gemini", gemini_model="fallback-model"),
    ).complete(
        AICompletionRequest(
            purpose="explanation",
            messages=[PromptMessage(role="user", content="Explain the constitution")],
        )
    )
    assert response.provider == "gemini"
    assert response.model == "fallback-model"
    assert response.raw["fallback_from"] == "grok"


def test_prompt_builder_includes_track_context_and_sources():
    messages = PromptBuilder().build(
        PromptBuildRequest(
            track="pr",
            purpose="explanation",
            template_key="custom",
            retrieved_sources=[RetrievedSource(source_type="official_question", title="Paper 1", text="Grundlov context")],
        ),
        "System for $exam_type at $student_level",
        "Use $retrieved_context",
    )
    assert "pr" in messages[0].content
    assert "Grundlov context" in messages[1].content


def test_evaluator_routes_low_groundedness_to_review_or_reject():
    result = AIEvaluator().evaluate(
        EvaluationRequest(
            track="citizenship",
            artifact_type="explanation",
            content={"text": "Unsupported invented fact about a moon colony."},
            retrieved_sources=[RetrievedSource(source_type="learning_material", text="Danish constitution and citizenship")],
        )
    )
    assert result.decision in {"needs_review", "reject"}


def test_mock_composition_must_total_100():
    composition = AIMockComposition(official_percent=60, ai_percent=30)
    with pytest.raises(ValueError):
        composition.validate_total()


def test_ai_analytics_summarizes_token_usage():
    summary = AIAnalyticsService().summarize(
        [
            {"purpose": "explanation", "token_usage": {"input_tokens": 10, "output_tokens": 5}},
            {"purpose": "quiz", "token_usage": {"input_tokens": 20, "output_tokens": 10}},
        ]
    )
    assert summary["total_tokens"] == 45
    assert summary["by_purpose"]["explanation"] == 1