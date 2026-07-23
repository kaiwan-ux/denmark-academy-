from __future__ import annotations

import math
import re
from collections import Counter
from difflib import SequenceMatcher
from hashlib import blake2b


class QuestionQualityValidator:
    """Deterministic validation and semantic clustering for generated MCQs.

    The feature-hashed embedding is deliberately local: validation remains fast and
    available when an external embedding provider is rate-limited.
    """

    def __init__(self, dimension: int = 384, similarity_threshold: float = 0.85) -> None:
        self.dimension = dimension
        self.similarity_threshold = similarity_threshold

    def normalize(self, value: str) -> str:
        cleaned = re.sub(r"[^\w]+", " ", str(value).lower(), flags=re.UNICODE)
        return re.sub(r"\s+", " ", cleaned).strip()

    def learning_objective(self, question) -> str:
        explicit = self.normalize(getattr(question, "learning_objective", "") or "")
        if explicit:
            return explicit
        topic = self.normalize(getattr(question, "topic", "") or "")
        stem_terms = [word for word in self.normalize(getattr(question, "stem", "")).split() if len(word) > 3]
        return " ".join(([topic] if topic else []) + stem_terms[:6]).strip()

    def semantic_normalize(self, value: str) -> str:
        """Canonicalize common Danish inflections before local embedding."""
        stop_words = {
            "af", "at", "den", "det", "der", "en", "et", "for", "fra", "har",
            "hvad", "hvem", "hvilken", "hvilket", "hvordan", "i", "med", "og",
            "på", "som", "til", "bliver", "blev", "er", "the", "a", "an", "is",
            "are", "how", "what", "which", "who", "of", "in", "to",
            "mellem", "fungerer", "følger", "sammenhæng",
        }
        aliases = {
            "lovforslag": "lov", "lovforslaget": "lov", "lovgivning": "lov",
            "vedtages": "vedtag", "vedtaget": "vedtag", "vedtage": "vedtag",
            "spørgsmål": "spørg", "spørgsmålet": "spørg",
            "folketinget": "folketing", "regeringen": "regering",
            "parlamentarismen": "parlamentarisme", "parlamentarismens": "parlamentarisme",
            "negative": "negativ", "negativt": "negativ",
        }
        tokens = []
        for token in self.normalize(value).split():
            token = aliases.get(token, token)
            if token not in stop_words:
                tokens.append(token)
        return " ".join(tokens)

    def embed(self, text: str) -> list[float]:
        normalized = self.normalize(text)
        features: Counter[str] = Counter()
        words = normalized.split()
        features.update("w:" + word for word in words)
        features.update("b:" + words[index] + "_" + words[index + 1] for index in range(len(words) - 1))
        compact = normalized.replace(" ", "_")
        features.update("c:" + compact[index:index + 4] for index in range(max(0, len(compact) - 3)))
        vector = [0.0] * self.dimension
        for feature, count in features.items():
            digest = blake2b(feature.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign * (1.0 + math.log(count))
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def cosine(self, left: list[float], right: list[float]) -> float:
        return sum(a * b for a, b in zip(left, right))

    def similarity(self, left: str, right: str) -> float:
        left_normalized, right_normalized = self.normalize(left), self.normalize(right)
        if not left_normalized or not right_normalized:
            return 0.0
        left_semantic = self.semantic_normalize(left_normalized)
        right_semantic = self.semantic_normalize(right_normalized)
        left_words, right_words = set(left_semantic.split()), set(right_semantic.split())
        jaccard = len(left_words & right_words) / max(1, len(left_words | right_words))
        sequence = SequenceMatcher(None, left_normalized, right_normalized).ratio()
        semantic = self.cosine(self.embed(left_semantic), self.embed(right_semantic))
        return max(jaccard, sequence, semantic)

    def valid_choices(self, question) -> bool:
        choices = [
            self.normalize(getattr(question, "choice_a", "")),
            self.normalize(getattr(question, "choice_b", "")),
            self.normalize(getattr(question, "choice_c", "")),
        ]
        if len(set(choices)) != 3 or any(len(choice) < 3 for choice in choices):
            return False
        lengths = [len(choice.split()) for choice in choices]
        return max(lengths) <= max(4, min(lengths) * 4)

    def is_duplicate(self, stem: str, objective: str, existing: list[tuple[str, str]]) -> bool:
        for prior_stem, prior_objective in existing:
            if self.similarity(stem, prior_stem) >= self.similarity_threshold:
                return True
            if objective and prior_objective and self.similarity(objective, prior_objective) >= 0.82:
                return True
        return False

    def quality_score(self, question) -> float:
        stem = self.normalize(getattr(question, "stem", ""))
        score = min(40.0, len(set(stem.split())) * 2.0)
        if any(word in stem for word in ("hvorfor", "hvordan", "betydning", "formål", "sammenhæng")):
            score += 25.0
        if self.valid_choices(question):
            score += 25.0
        if self.learning_objective(question):
            score += 10.0
        return min(100.0, score)

    def select_unique(self, questions: list, existing: list[tuple[str, str]], limit: int) -> list:
        selected: list = []
        seen = list(existing)
        # Prefer quality while maintaining an easy/medium/hard balance.
        ranked = sorted(questions, key=self.quality_score, reverse=True)
        for desired in ("easy", "medium", "hard"):
            candidate = next((item for item in ranked if getattr(item, "difficulty", None) == desired and item not in selected), None)
            if candidate and self._accept(candidate, seen):
                selected.append(candidate)
                seen.append((candidate.stem, self.learning_objective(candidate)))
                if len(selected) >= limit:
                    return selected
        for candidate in ranked:
            if candidate in selected or not self._accept(candidate, seen):
                continue
            selected.append(candidate)
            seen.append((candidate.stem, self.learning_objective(candidate)))
            if len(selected) >= limit:
                break
        return selected


    def select_session_rows(
        self, rows: list[dict], limit: int, *, enforce_objectives: bool = True
    ) -> list[dict]:
        """Apply exact/semantic filtering and optional objective diversity."""
        selected: list[dict] = []
        seen: list[tuple[str, str]] = []
        for row in rows:
            stem = self.normalize(row.get("question_stem", ""))
            objective = self.normalize(row.get("learning_objective", "") or "")
            stem_duplicate = any(
                self.similarity(stem, prior_stem) >= self.similarity_threshold
                for prior_stem, _ in seen
            )
            objective_duplicate = enforce_objectives and any(
                objective and prior_objective
                and self.similarity(objective, prior_objective) >= 0.82
                for _, prior_objective in seen
            )
            if not stem or stem_duplicate or objective_duplicate:
                continue
            selected.append(row)
            seen.append((stem, objective))
            if len(selected) >= limit:
                break
        return selected

    def _accept(self, question, seen: list[tuple[str, str]]) -> bool:
        stem = self.normalize(getattr(question, "stem", ""))
        objective = self.learning_objective(question)
        return bool(stem) and self.valid_choices(question) and not self.is_duplicate(stem, objective, seen)
