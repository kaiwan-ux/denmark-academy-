from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


PracticeMode = Literal[
    "chapter_practice",
    "topic_practice",
    "random_practice",
    "official_question_practice",
    "study_mode",
    "exam_mode",
    "review_mode",
    "wrong_question_practice",
    "bookmarked_question_practice",
    "past_paper",
    "mock_exam",
]


class CourseCreate(BaseModel):
    track: str
    title: str
    description: str | None = None
    estimated_minutes: int | None = None
    status: Literal["draft", "published", "archived"] = "draft"


class ChapterCreate(BaseModel):
    course_id: UUID
    title: str
    summary: str | None = None
    slug: str
    sort_order: int
    estimated_minutes: int | None = None
    status: Literal["draft", "published", "archived"] = "draft"


class TopicCreate(BaseModel):
    chapter_id: UUID
    title: str
    summary: str | None = None
    slug: str
    sort_order: int
    estimated_minutes: int | None = None
    status: Literal["draft", "published", "archived"] = "draft"


class LearningUnitCreate(BaseModel):
    course_id: UUID
    chapter_id: UUID | None = None
    topic_id: UUID | None = None
    subtopic_id: UUID | None = None
    source_document_id: UUID | None = None
    document_chunk_id: UUID | None = None
    title: str
    body: str
    estimated_minutes: int | None = None
    sort_order: int = 0
    status: Literal["draft", "published", "archived"] = "draft"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReadingProgressUpdate(BaseModel):
    percent_complete: float = Field(ge=0, le=100)
    last_position: dict[str, Any] = Field(default_factory=dict)
    time_spent_seconds: int = Field(default=0, ge=0)


class BookmarkRequest(BaseModel):
    entity_type: Literal["learning_unit", "official_question", "official_exam_paper", "chapter", "topic"]
    entity_id: UUID
    label: str | None = None


class NoteRequest(BaseModel):
    entity_type: Literal["learning_unit", "official_question", "official_exam_paper", "chapter", "topic"]
    entity_id: UUID
    body: str
    anchor: dict[str, Any] = Field(default_factory=dict)


class HighlightRequest(BaseModel):
    learning_unit_id: UUID
    selected_text: str
    color: str = "yellow"
    anchor: dict[str, Any] = Field(default_factory=dict)


class PracticeSessionCreate(BaseModel):
    track: str
    user_id: UUID
    mode: PracticeMode
    source_type: Literal["chapter", "topic", "question_set", "past_paper", "blueprint", "revision"]
    source_id: UUID | None = None
    limit: int = Field(default=20, ge=1, le=100)


class PracticeAnswerRequest(BaseModel):
    selected_choice: Literal["A", "B", "C"]
    time_spent_seconds: int = Field(default=0, ge=0)
    marked_for_review: bool = False


class PracticeSubmitRequest(BaseModel):
    duration_seconds: int = Field(default=0, ge=0)


class SearchRequest(BaseModel):
    track: str
    query: str = ""
    entity_types: list[str] = Field(default_factory=lambda: ["learning_unit", "official_question", "chapter", "topic", "past_paper"])
    difficulty: str | None = None
    year: int | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class CountdownRequest(BaseModel):
    user_id: UUID
    track: str
    target_exam_date: str
    label: str | None = None


class CategoryCreate(BaseModel):
    track: str
    name: str
    slug: str
    description: str | None = None


class QuestionClassificationRequest(BaseModel):
    official_question_id: UUID
    chapter_id: UUID | None = None
    topic_id: UUID | None = None
    subtopic_id: UUID | None = None
    category_id: UUID | None = None
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    metadata: dict[str, Any] = Field(default_factory=dict)
