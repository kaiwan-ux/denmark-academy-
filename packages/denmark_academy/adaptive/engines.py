from datetime import date, timedelta
from statistics import mean
from typing import Any
from uuid import UUID

from denmark_academy.adaptive.schemas import AdaptiveMockRequest, LearningInteractionEvent, StudyPlannerRequest


def clamp(value: float, low: float = 0, high: float = 100) -> float:
    return round(max(low, min(high, value)), 2)


class KnowledgeMasteryEngine:
    def update_delta(self, event: LearningInteractionEvent) -> dict[str, Any]:
        if event.event_type == "reading":
            return {"mastery_delta": 1.5, "confidence_score": event.confidence or 55, "is_correct": True, "metadata": {"event": event.event_type}}
        correct = bool(event.is_correct)
        difficulty_bonus = {"easy": 4, "medium": 7, "hard": 10}.get(event.difficulty or "medium", 7)
        delta = difficulty_bonus if correct else -8
        confidence = event.confidence if event.confidence is not None else (70 if correct else 35)
        return {"mastery_delta": delta, "confidence_score": confidence, "is_correct": correct, "metadata": {"event": event.event_type}}


class AdaptiveDifficultyEngine:
    def choose(self, mastery_score: float, recent_accuracy: float) -> str:
        if mastery_score >= 78 and recent_accuracy >= 75:
            return "hard"
        if mastery_score < 45 or recent_accuracy < 55:
            return "easy"
        return "medium"


class LearningProfileEngine:
    def __init__(self, repository=None) -> None:
        if repository is None:
            from denmark_academy.adaptive.repository import AdaptiveRepository

            repository = AdaptiveRepository()
        self.repository = repository
        self.mastery_engine = KnowledgeMasteryEngine()

    def update_after_event(self, event: LearningInteractionEvent) -> dict[str, Any]:
        with self.repository.connection() as conn:
            self.repository.get_or_create_profile(conn, event.user_id, event.track)
            for concept_id in event.concept_ids:
                delta = self.mastery_engine.update_delta(event)
                self.repository.update_concept_mastery(conn, event.user_id, event.track, concept_id, delta)
                if event.is_correct is False or (event.confidence is not None and event.confidence < 45):
                    self.repository.schedule_spaced_item(conn, event.user_id, event.track, concept_id, event.entity_id if event.entity_type == "official_question" else None, None, "incorrect" if event.is_correct is False else "low_confidence")
            metrics = self.compute_profile_metrics(conn, event.user_id, event.track)
            profile = self.repository.upsert_profile_metrics(conn, event.user_id, event.track, metrics)
            conn.commit()
            return dict(profile)

    def compute_profile_metrics(self, conn, user_id: UUID, track: str) -> dict[str, Any]:
        inputs = self.repository.profile_inputs(conn, user_id, track)
        reading = float(inputs["reading"]["reading_progress"] or 0)
        accuracy = float(inputs["practice"]["accuracy"] or 0)
        mastery = float(inputs["mastery"]["average_mastery"] or 0)
        confidence = float(inputs["mastery"]["confidence"] or 50)
        active_days = float(inputs["activity"]["active_days"] or 0)
        total_seconds = int(inputs["reading"]["reading_seconds"] or 0) + int(inputs["practice"]["practice_seconds"] or 0)
        revision_total = int(inputs["revision"]["total"] or 0)
        revision_completed = int(inputs["revision"]["completed"] or 0)
        revision_accuracy = (revision_completed / revision_total * 100) if revision_total else 0
        preferred = AdaptiveDifficultyEngine().choose(mastery, accuracy)
        velocity = mastery / max(1, active_days)
        return {
            "reading_progress": clamp(reading),
            "overall_accuracy": clamp(accuracy),
            "average_mastery": clamp(mastery),
            "confidence_score": clamp(confidence),
            "study_frequency_days": active_days,
            "preferred_difficulty": preferred,
            "learning_velocity": round(velocity, 2),
            "time_spent_seconds": total_seconds,
            "revision_accuracy": clamp(revision_accuracy),
            "profile": {"inputs": inputs},
        }


class SpacedRepetitionEngine:
    intervals = [1, 3, 7, 14, 30]

    def next_interval(self, interval_index: int, result: str) -> tuple[int, int]:
        if result in {"incorrect", "low_confidence"}:
            return 0, 1
        next_index = min(interval_index + 1, len(self.intervals) - 1)
        return next_index, self.intervals[next_index]


class ExamReadinessEngine:
    def calculate(self, profile: dict[str, Any], mastery_rows: list[dict[str, Any]]) -> dict[str, Any]:
        coverage = float(profile.get("reading_progress", 0))
        mastery = float(profile.get("average_mastery", 0))
        mock = float(profile.get("overall_accuracy", 0))
        revision = float(profile.get("revision_accuracy", 0))
        consistency = min(100, float(profile.get("study_frequency_days", 0)) / 20 * 100)
        readiness = clamp((coverage * 0.18) + (mastery * 0.32) + (mock * 0.25) + (revision * 0.15) + (consistency * 0.10))
        blockers = []
        if mastery < 55:
            blockers.append("Concept mastery is below target.")
        if mock < 65:
            blockers.append("Mock/practice score is below pass comfort range.")
        weak = [row for row in mastery_rows if float(row["mastery_score"]) < 45]
        if weak:
            blockers.append(f"{len(weak)} weak concepts need review.")
        return {"readiness_score": readiness, "coverage_score": clamp(coverage), "mastery_score": clamp(mastery), "mock_score": clamp(mock), "revision_score": clamp(revision), "consistency_score": clamp(consistency), "blockers": blockers}


class PassPredictionEngine:
    def predict(self, readiness: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
        probability = clamp((readiness["readiness_score"] * 0.72) + (float(profile.get("confidence_score", 50)) * 0.18) + (float(profile.get("learning_velocity", 0)) * 2))
        confidence = clamp(45 + min(35, float(profile.get("study_frequency_days", 0)) * 1.2) + min(20, float(profile.get("time_spent_seconds", 0)) / 3600))
        if probability >= 78:
            level = "ready"
        elif probability >= 62:
            level = "near_ready"
        elif probability >= 42:
            level = "developing"
        else:
            level = "not_ready"
        return {"pass_probability": probability, "confidence": confidence, "readiness_level": level, "explainability": {"readiness": readiness, "profile_factors": profile}}


class RecommendationEngineV2:
    def build(self, profile: dict[str, Any], mastery_rows: list[dict[str, Any]], due_reviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        if due_reviews:
            items.append({"type": "revise", "title": "Complete due revision", "rationale": f"{len(due_reviews)} review items are due now.", "priority": 95})
        for row in mastery_rows[:5]:
            if float(row["mastery_score"]) < 55:
                items.append({"type": "practice", "title": f"Practice {row['concept_name']}", "rationale": "Concept mastery is below the readiness target.", "priority": 85, "target_entity_type": "concept", "target_entity_id": row["concept_id"]})
        if float(profile.get("reading_progress", 0)) < 70:
            items.append({"type": "read", "title": "Continue official reading", "rationale": "Reading coverage improves exam readiness and RAG grounding.", "priority": 65})
        if float(profile.get("overall_accuracy", 0)) >= 75:
            items.append({"type": "mock", "title": "Take an adaptive mock", "rationale": "Accuracy suggests you are ready for timed exam practice.", "priority": 70})
        return sorted(items, key=lambda item: item["priority"], reverse=True)[:8]


class MotivationEngine:
    def achievements(self, profile: dict[str, Any]) -> list[dict[str, Any]]:
        awards = []
        if float(profile.get("study_frequency_days", 0)) >= 7:
            awards.append({"event_key": "seven_day_consistency", "points": 100, "badge_key": "consistent_learner", "title": "Consistent learner", "description": "Studied on at least seven days recently."})
        if float(profile.get("average_mastery", 0)) >= 80:
            awards.append({"event_key": "high_mastery", "points": 150, "badge_key": "mastery_builder", "title": "Mastery builder", "description": "Average concept mastery reached 80%."})
        return awards


class LearningAnalyticsEngine:
    def trend_payload(self, profile: dict[str, Any], mastery_rows: list[dict[str, Any]]) -> dict[str, Any]:
        scores = [float(row["mastery_score"]) for row in mastery_rows]
        return {"average_mastery": round(mean(scores), 2) if scores else 0, "weak_concepts": [row["concept_name"] for row in mastery_rows if float(row["mastery_score"]) < 50], "profile": profile}


class PersonalizedStudyPlanner:
    def build_plan(self, request: StudyPlannerRequest, recommendations: list[dict[str, Any]]) -> dict[str, Any]:
        today = date.today()
        days = []
        for offset in range(request.days_until_exam):
            rec = recommendations[offset % len(recommendations)] if recommendations else {"title": "Review official material", "type": "read"}
            days.append({"date": (today + timedelta(days=offset)).isoformat(), "minutes": request.minutes_per_day, "focus": rec["title"], "type": rec["type"]})
        return {"track": request.track, "user_id": str(request.user_id), "days": days}


class AdaptiveMockPlanner:
    def build(self, request: AdaptiveMockRequest, mastery_rows: list[dict[str, Any]]) -> dict[str, Any]:
        request.validate_ratio()
        weak = [row for row in mastery_rows if float(row["mastery_score"]) < 60]
        return {"blueprint_id": str(request.blueprint_id), "official_percent": request.official_percent, "ai_percent": request.ai_percent, "weak_concepts": [str(row["concept_id"]) for row in weak[:10]], "weak_concept_weight": request.weak_concept_weight, "difficulty_progression": ["easy", "medium", "hard"]}


