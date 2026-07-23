from uuid import UUID

import pytest

from denmark_academy.adaptive.engines import (
    AdaptiveDifficultyEngine,
    AdaptiveMockPlanner,
    ExamReadinessEngine,
    KnowledgeMasteryEngine,
    PassPredictionEngine,
    SpacedRepetitionEngine,
)
from denmark_academy.adaptive.schemas import AdaptiveMockRequest, LearningInteractionEvent

USER = UUID("00000000-0000-0000-0000-000000000001")
BLUEPRINT = UUID("00000000-0000-0000-0000-000000000002")
CONCEPT = UUID("00000000-0000-0000-0000-000000000003")


def test_mastery_delta_rewards_hard_correct_answer():
    event = LearningInteractionEvent(
        user_id=USER,
        track="pr",
        event_type="practice_answer",
        concept_ids=[CONCEPT],
        is_correct=True,
        difficulty="hard",
        confidence=80,
    )
    delta = KnowledgeMasteryEngine().update_delta(event)
    assert delta["mastery_delta"] == 10
    assert delta["confidence_score"] == 80


def test_adaptive_difficulty_moves_to_easy_for_low_mastery():
    assert AdaptiveDifficultyEngine().choose(30, 80) == "easy"
    assert AdaptiveDifficultyEngine().choose(85, 80) == "hard"


def test_spaced_repetition_resets_on_incorrect():
    index, days = SpacedRepetitionEngine().next_interval(3, "incorrect")
    assert index == 0
    assert days == 1


def test_readiness_and_pass_prediction_are_explainable():
    profile = {"reading_progress": 80, "average_mastery": 75, "overall_accuracy": 78, "revision_accuracy": 70, "study_frequency_days": 12, "confidence_score": 72, "learning_velocity": 3, "time_spent_seconds": 36000}
    readiness = ExamReadinessEngine().calculate(profile, [])
    prediction = PassPredictionEngine().predict(readiness, profile)
    assert readiness["readiness_score"] > 70
    assert prediction["pass_probability"] > 60
    assert "readiness" in prediction["explainability"]


def test_adaptive_mock_ratio_must_total_100():
    request = AdaptiveMockRequest(user_id=USER, track="citizenship", blueprint_id=BLUEPRINT, official_percent=80, ai_percent=10)
    with pytest.raises(ValueError):
        AdaptiveMockPlanner().build(request, [])
