import asyncio
import json
import logging
import re

import httpx

from denmark_academy.ai.api_key_manager import get_api_key_manager
from denmark_academy.config import get_settings
from denmark_academy.current_affairs.models import AIArticleAnalysis, AIGeneratedQuestion
from denmark_academy.current_affairs.quality import QuestionQualityValidator

logger = logging.getLogger(__name__)
settings = get_settings()


class AIProcessor:
    """Analyze current-affairs articles and generate Danish exam-style questions."""

    ANALYSIS_PROMPT = """You are an expert in Danish Citizenship and Permanent Residence exam preparation.

Analyze this Danish news article:

Title: {title}
Content: {content}

Your job is not to test whether students remember the news story. Your job is to identify the underlying civic, legal, democratic, social, or institutional concept that the article illustrates.

Decide whether the concept is relevant for:
- citizenship
- pr
- both
- neither

If relevant, generate exactly {question_count} different Danish multiple-choice questions. Each question must:
- be written in Danish
- test the underlying exam concept, not trivia from the news article
- look like a serious official-style exam question
- use 3 plausible options: choice_a, choice_b, choice_c
- have one correct answer: a, b, or c
- include a useful explanation in Danish
- use difficulty: easy, medium, or hard
- avoid copying existing official wording
- contribute distinct candidates to a combined pool of 10 questions from this article
- ensure every candidate tests a different fact or civic concept
- never ask multiple questions about the same idea or learning objective
- state one precise learning_objective for every candidate
- balance the final candidates across easy, medium, and hard difficulty
- keep distractors similar in specificity and length so the answer is not obvious
- reject candidates with similar wording
- prefer understanding and application over simple memorization
- make every distractor plausible, distinct, and factually coherent
- avoid generating two questions that test the same idea
- return candidates in descending quality order

Use this JSON format only:
{{
  "is_relevant": true,
  "exam_type": "citizenship" | "pr" | "both",
  "topic": "short topic name",
  "summary": "2-3 Danish sentences explaining the exam concept",
  "questions": [
    {{
      "stem": "Danish question text",
      "choice_a": "plausible option a",
      "choice_b": "plausible option b",
      "choice_c": "plausible option c",
      "correct_choice": "a" | "b" | "c",
      "explanation": "Danish explanation",
      "difficulty": "easy" | "medium" | "hard",
      "exam_type": "citizenship" | "pr" | "both",
      \
    }}
  ]
}}

If not relevant, return:
{{
  "is_relevant": false,
  "exam_type": null,
  "topic": null,
  "summary": null,
  "questions": null
}}

Return valid JSON only."""

    def __init__(self):
        self.api_key_manager = get_api_key_manager()
        self.timeout = settings.ai_request_timeout_seconds
        self.validator = QuestionQualityValidator(similarity_threshold=0.85)

    async def analyze_article(
        self,
        title: str,
        content: str,
        variation_seed: str | None = None,
        existing_stems: list[str] | None = None,
    ) -> AIArticleAnalysis:
        """Generate with every configured key available as a same-provider fallback."""
        has_grok = bool(self.api_key_manager.get_grok_keys())
        has_gemini = bool(self.api_key_manager.get_gemini_keys())

        if has_grok and has_gemini:

            async def generate(provider: str) -> AIArticleAnalysis | Exception:
                try:
                    prompt = self._build_prompt(title, content, 5, variation_seed, existing_stems)
                    return await self._call_provider_with_key_fallback(provider, prompt)
                except Exception as exc:
                    logger.warning("Current-affairs provider %s failed: %s", provider, exc)
                    return exc

            results = await asyncio.gather(generate("grok"), generate("gemini"))
            split_results = [result for result in results if isinstance(result, AIArticleAnalysis)]
            if split_results:
                return self._merge_analyses(split_results, existing_stems)

        provider, api_key = self.api_key_manager.get_key_for_task("current_affairs")
        prompt = self._build_prompt(title, content, 10, variation_seed, existing_stems)
        if api_key:
            try:
                analysis = await self._call_provider_with_key_fallback(provider, prompt)
                return self._finalize_analysis(analysis, existing_stems)
            except Exception as exc:
                logger.warning("Selected current-affairs provider failed: %s", exc)

        fallback_provider = "gemini" if provider == "grok" else "grok"
        fallback_keys = (
            self.api_key_manager.get_gemini_keys()
            if fallback_provider == "gemini"
            else self.api_key_manager.get_grok_keys()
        )
        if fallback_keys:
            analysis = await self._call_provider_with_key_fallback(fallback_provider, prompt)
            return self._finalize_analysis(analysis, existing_stems)
        raise ValueError("No working Gemini/Groq API key configured for current affairs")

    def _build_prompt(self, title: str, content: str, question_count: int, variation_seed: str | None = None, existing_stems: list[str] | None = None) -> str:
        clean_content = re.sub(r"\s+", " ", content).strip()[:5000]
        prompt = self.ANALYSIS_PROMPT.format(title=title, content=clean_content, question_count=question_count)
        avoid = "\\n".join("- " + stem[:180] for stem in (existing_stems or [])[-80:])
        duplicate_rule = ("\\n\\nExisting database questions to avoid (regenerate any candidate with semantic similarity above 0.85):\\n" + avoid) if avoid else ""
        return prompt + duplicate_rule + "\\n\\nVariation seed: " + (variation_seed or "scheduled") + ". Generate substantively new angles while remaining fully grounded in this article. Return 10 candidates; the application will retain only the best 5 unique questions."

    async def _call_provider_with_key_fallback(
        self, provider: str, prompt: str
    ) -> AIArticleAnalysis:
        """Try each configured key once, preserving provider choice and hiding secrets."""
        keys = (
            self.api_key_manager.get_grok_keys()
            if provider == "grok"
            else self.api_key_manager.get_gemini_keys()
        )
        if not keys:
            raise ValueError(f"No {provider} API key configured for current affairs")

        last_error: Exception | None = None
        for _ in range(len(keys)):
            key = (
                self.api_key_manager.get_next_grok_key()
                if provider == "grok"
                else self.api_key_manager.get_next_gemini_key()
            )
            try:
                if provider == "grok":
                    return await self._call_grok(prompt, key)
                return await self._call_gemini(prompt, key)
            except Exception as exc:
                last_error = exc
                logger.warning("Current-affairs %s key failed; trying fallback key", provider)
        raise RuntimeError(f"All configured {provider} API keys failed") from last_error

    async def _call_grok(self, prompt: str, api_key) -> AIArticleAnalysis:
        if not api_key:
            raise ValueError("Grok API key not provided")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{settings.grok_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key.get_secret_value()}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.grok_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.45,
                    "max_tokens": 4800,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return self._parse_ai_response(content)

    async def _call_gemini(self, prompt: str, api_key) -> AIArticleAnalysis:
        if not api_key:
            raise ValueError("Gemini API key not provided")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{settings.gemini_base_url}/models/{settings.gemini_model}:generateContent",
                headers={"Content-Type": "application/json"},
                params={"key": api_key.get_secret_value()},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.45,
                        "maxOutputTokens": 4800,
                        "responseMimeType": "application/json",
                    },
                },
            )
            response.raise_for_status()
        content = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        return self._parse_ai_response(content)

    def _parse_ai_response(self, content: str) -> AIArticleAnalysis:
        try:
            data = json.loads(content)
            questions = None
            if data.get("questions"):
                questions = [AIGeneratedQuestion(**question) for question in data["questions"]]
            return AIArticleAnalysis(
                is_relevant=bool(data["is_relevant"]),
                exam_type=data.get("exam_type"),
                topic=data.get("topic"),
                summary=data.get("summary"),
                questions=questions,
            )
        except Exception as exc:
            logger.error("Failed to parse current-affairs AI response: %s", exc)
            raise ValueError(f"Invalid AI response format: {exc}") from exc

    def _merge_analyses(self, analyses: list[AIArticleAnalysis], existing_stems: list[str] | None = None) -> AIArticleAnalysis:
        relevant = [analysis for analysis in analyses if analysis.is_relevant]
        if not relevant:
            return analyses[0]

        merged_questions: list[AIGeneratedQuestion] = []
        seen_stems: list[str] = []
        for analysis in relevant:
            for question in analysis.questions or []:
                normalized = self._normalize_stem(question.stem)
                if not normalized:
                    continue
                if any(existing == normalized or self._stem_similarity(existing, normalized) > 0.85 for existing in seen_stems):
                    continue
                seen_stems.append(normalized)
                merged_questions.append(question)

        base = relevant[0]
        merged = AIArticleAnalysis(
            is_relevant=True,
            exam_type=base.exam_type or next((item.exam_type for item in relevant if item.exam_type), None),
            topic=base.topic or next((item.topic for item in relevant if item.topic), None),
            summary=base.summary or next((item.summary for item in relevant if item.summary), None),
            questions=merged_questions or None,
        )
        return self._finalize_analysis(merged, existing_stems)


    def _finalize_analysis(self, analysis: AIArticleAnalysis, existing_stems: list[str] | None = None) -> AIArticleAnalysis:
        """Validate, semantically cluster, difficulty-balance, and retain five candidates."""
        if not analysis.is_relevant or not analysis.questions:
            return analysis
        existing = [(stem, "") for stem in (existing_stems or []) if stem]
        accepted = self.validator.select_unique(analysis.questions, existing, limit=5)
        return analysis.model_copy(update={"questions": accepted or None})
    def _valid_choices(self, question: AIGeneratedQuestion) -> bool:
        choices = {
            self._normalize_stem(question.choice_a),
            self._normalize_stem(question.choice_b),
            self._normalize_stem(question.choice_c),
        }
        return len(choices) == 3 and all(len(choice) >= 3 for choice in choices)

    def _understanding_score(self, question: AIGeneratedQuestion) -> int:
        stem = self._normalize_stem(question.stem)
        score = len(set(stem.split()))
        if any(word in stem for word in ("hvorfor", "hvordan", "betydning", "formål", "sammenhæng")):
            score += 20
        if stem.startswith(("hvem ", "hvornår ", "hvor mange ", "hvad hedder ")):
            score -= 12
        return score
    def _normalize_stem(self, value: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^\wæøåÆØÅ]+", " ", value.lower())).strip()

    def _stem_similarity(self, first: str, second: str) -> float:
        first_words = {word for word in first.split() if len(word) > 2}
        second_words = {word for word in second.split() if len(word) > 2}
        if not first_words or not second_words:
            return 0.0
        return len(first_words & second_words) / max(len(first_words), len(second_words))
