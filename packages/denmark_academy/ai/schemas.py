from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

AIProviderKey = Literal["disabled", "openai", "anthropic", "gemini", "grok"]
AIPurpose = Literal[
    "tutor",
    "explanation",
    "similar_question",
    "mock_question",
    "recommendation",
    "revision",
    "flashcard",
    "notes",
    "quiz",
    "study_plan",
    "evaluation",
]
ArtifactType = Literal[
    "explanation",
    "similar_question",
    "mock_question",
    "recommendation",
    "revision_plan",
    "flashcard",
    "notes",
    "quiz",
    "study_plan",
    "tutor_response",
    "summary",
]


class StudentContext(BaseModel):
    user_id: UUID | None = None
    level: Literal["beginner", "intermediate", "advanced"] = "intermediate"
    weak_topics: list[str] = Field(default_factory=list)
    learning_objective: str | None = None


class RetrievalRequest(BaseModel):
    track: Literal["pr", "citizenship"]
    query: str
    purpose: AIPurpose
    limit: int = Field(default=8, ge=1, le=30)
    include_current_affairs: bool = False
    filters: dict[str, Any] = Field(default_factory=dict)


class RetrievedSource(BaseModel):
    source_type: str
    title: str | None = None
    text: str
    score: float = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class PromptBuildRequest(BaseModel):
    track: Literal["pr", "citizenship"]
    purpose: AIPurpose
    template_key: str
    retrieved_sources: list[RetrievedSource]
    student_context: StudentContext = Field(default_factory=StudentContext)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    metadata: dict[str, Any] = Field(default_factory=dict)


class PromptMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class AICompletionRequest(BaseModel):
    provider: AIProviderKey = "disabled"
    model: str = "disabled-local"
    purpose: AIPurpose
    messages: list[PromptMessage]
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int = Field(default=800, ge=64, le=8000)
    cache_key: str | None = None


class AICompletionResponse(BaseModel):
    provider: AIProviderKey
    model: str
    content: str
    raw: dict[str, Any] = Field(default_factory=dict)
    token_usage: dict[str, int] = Field(default_factory=dict)
    cache_hit: bool = False


class AIArtifactRequest(BaseModel):
    track: Literal["pr", "citizenship"]
    user_id: UUID | None = None
    source_entity_type: str | None = None
    source_entity_id: UUID | None = None
    query: str
    purpose: AIPurpose
    template_key: str
    provider: AIProviderKey = "disabled"
    model: str = "disabled-local"
    student_context: StudentContext = Field(default_factory=StudentContext)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    metadata: dict[str, Any] = Field(default_factory=dict)


class SimilarQuestionRequest(AIArtifactRequest):
    purpose: AIPurpose = "similar_question"
    template_key: str = "similar_question_v1"
    count: int = Field(default=3, ge=1, le=20)


class ExplanationRequest(AIArtifactRequest):
    purpose: AIPurpose = "explanation"
    template_key: str = "explanation_v1"
    official_question_id: UUID


class AIMockComposition(BaseModel):
    official_percent: int = Field(default=70, ge=0, le=100)
    ai_percent: int = Field(default=30, ge=0, le=100)

    def validate_total(self) -> None:
        if self.official_percent + self.ai_percent != 100:
            raise ValueError("official_percent and ai_percent must total 100")


class AIMockRequest(BaseModel):
    track: Literal["pr", "citizenship"]
    user_id: UUID
    blueprint_id: UUID
    composition: AIMockComposition = Field(default_factory=AIMockComposition)
    provider: AIProviderKey = "disabled"
    model: str = "disabled-local"
    difficulty: Literal["easy", "medium", "hard"] = "medium"


class EvaluationRequest(BaseModel):
    track: Literal["pr", "citizenship"]
    artifact_type: ArtifactType
    content: dict[str, Any]
    retrieved_sources: list[RetrievedSource]
    official_similarity_texts: list[str] = Field(default_factory=list)


class EvaluationResult(BaseModel):
    groundedness_score: float
    exam_alignment_score: float
    hallucination_risk: float
    duplication_score: float
    quality_score: float
    decision: Literal["approve", "needs_review", "reject"]
    findings: dict[str, Any] = Field(default_factory=dict)


class RecommendationRequest(BaseModel):
    track: Literal["pr", "citizenship"]
    user_id: UUID
    limit: int = Field(default=5, ge=1, le=20)


class StudyPlanRequest(BaseModel):
    track: Literal["pr", "citizenship"]
    user_id: UUID
    days_until_exam: int = Field(default=30, ge=1, le=365)
    minutes_per_day: int = Field(default=45, ge=10, le=240)
    provider: AIProviderKey = "disabled"
    model: str = "disabled-local"

