import re
from difflib import SequenceMatcher
from typing import Any

from denmark_academy.ai.schemas import EvaluationRequest, EvaluationResult


class AIEvaluator:
    evaluator_version = "ai-evaluator-v1"

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        content_text = self._content_to_text(request.content)
        source_text = "\n".join(source.text for source in request.retrieved_sources)
        groundedness = self._groundedness(content_text, source_text)
        alignment = self._exam_alignment(request.artifact_type, request.content)
        hallucination = max(0, 100 - groundedness)
        duplication = self._duplication(content_text, request.official_similarity_texts)
        quality = round((groundedness * 0.35) + (alignment * 0.30) + ((100 - hallucination) * 0.20) + ((100 - duplication) * 0.15), 2)
        decision = "approve"
        if quality < 72 or hallucination > 35 or duplication > 85:
            decision = "needs_review"
        if quality < 45 or groundedness < 35:
            decision = "reject"
        return EvaluationResult(
            groundedness_score=groundedness,
            exam_alignment_score=alignment,
            hallucination_risk=hallucination,
            duplication_score=duplication,
            quality_score=quality,
            decision=decision,
            findings={
                "content_terms": len(set(_terms(content_text))),
                "source_terms": len(set(_terms(source_text))),
                "has_sources": bool(request.retrieved_sources),
            },
        )

    def _groundedness(self, content: str, sources: str) -> float:
        content_terms = set(_terms(content))
        source_terms = set(_terms(sources))
        if not content_terms or not source_terms:
            return 0
        overlap = len(content_terms & source_terms) / len(content_terms)
        return round(min(100, overlap * 140), 2)

    def _exam_alignment(self, artifact_type: str, content: dict[str, Any]) -> float:
        if artifact_type in {"similar_question", "mock_question"}:
            required = ["stem", "choices", "correct_choice"]
            present = sum(1 for key in required if key in content and content[key])
            choices = content.get("choices") or {}
            choice_score = 100 if {"A", "B"}.issubset(set(choices)) else 50
            return round(((present / len(required)) * 70) + (choice_score * 0.30), 2)
        if artifact_type in {"explanation", "notes", "summary"}:
            text = self._content_to_text(content)
            return 85 if len(text.split()) >= 25 else 55
        return 75

    def _duplication(self, content: str, official_texts: list[str]) -> float:
        if not official_texts:
            return 0
        return round(max(SequenceMatcher(None, content, official).ratio() for official in official_texts) * 100, 2)

    def _content_to_text(self, content: dict[str, Any]) -> str:
        return " ".join(str(value) for value in content.values())


def _terms(text: str) -> list[str]:
    return [term.lower() for term in re.findall(r"[A-Za-zÀ-ÿ0-9]{3,}", text)]
