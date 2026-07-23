from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

Difficulty = Literal["easy", "medium", "hard"]
ReadinessLevel = Literal["not_ready", "developing", "near_ready", "ready"]


class LearningInteractionEvent(BaseModel):
    user_id: UUID
    track: Literal["pr", "citizenship"]
    event_type: Literal["reading", "practice_answer", "mock_submitted", "revision", "note", "bookmark"]
    entity_type: str | None = None
    entity_id: UUID | None = None
    concept_ids: list[UUID] = Field(default_factory=list)
    is_correct: bool | None = None
    confidence: float | None = Field(default=None, ge=0, le=100)
    difficulty: Difficulty | None = None
    time_spent_seconds: int = Field(default=0, ge=0)
    score_percent: float | None = Field(default=None, ge=0, le=100)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConceptCreate(BaseModel):
    track: Literal["pr", "citizenship"]
    course_id: UUID | None = None
    chapter_id: UUID | None = None
    topic_id: UUID | None = None
    parent_concept_id: UUID | None = None
    name: str
    slug: str
    description: str | None = None
    sort_order: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class AdaptiveMockRequest(BaseModel):
    user_id: UUID
    track: Literal["pr", "citizenship"]
    blueprint_id: UUID
    official_percent: int = Field(default=70, ge=0, le=100)
    ai_percent: int = Field(default=30, ge=0, le=100)
    weak_concept_weight: float = Field(default=1.5, ge=1, le=5)

    def validate_ratio(self) -> None:
        if self.official_percent + self.ai_percent != 100:
            raise ValueError("official_percent and ai_percent must total 100")


class StudyPlannerRequest(BaseModel):
    user_id: UUID
    track: Literal["pr", "citizenship"]
    days_until_exam: int = Field(default=30, ge=1, le=365)
    minutes_per_day: int = Field(default=45, ge=10, le=240)


class SpacedReviewResult(BaseModel):
    item_id: UUID
    result: Literal["correct", "incorrect", "low_confidence"]


class AdaptiveDashboardRequest(BaseModel):
    user_id: UUID
    track: Literal["pr", "citizenship"]
