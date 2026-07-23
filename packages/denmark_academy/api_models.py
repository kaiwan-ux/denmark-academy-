from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    app: str


class ManifestRequest(BaseModel):
    root_path: Path = Field(default=Path("."))
    dry_run: bool = True


class IngestionRunRequest(BaseModel):
    root_path: Path = Field(default=Path("."))
    upsert_qdrant: bool = True


class RetrievalSearchRequest(BaseModel):
    track: str
    query: str
    collections: list[str] = Field(
        default_factory=lambda: ["learning_chunks", "official_questions", "official_answers"]
    )
    limit: int = Field(default=10, ge=1, le=50)


class BlueprintValidationRequest(BaseModel):
    name: str
    version: int
    total_questions: int
    duration_minutes: int
    passing_score: int | None = None
    effective_from: str | None = None
    rules: dict[str, Any] = Field(default_factory=dict)
    sections: list[dict[str, Any]] = Field(default_factory=list)


class ExplanationDraftRequest(BaseModel):
    official_question_id: str
    generated_text: str
    model_provider: str
    model_name: str
    prompt_version: str
    retrieval_snapshot: dict[str, Any] = Field(default_factory=dict)


class ExplanationReviewRequest(BaseModel):
    approved_text: str | None = None
    review_note: str | None = None
