from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ExamTrackSlug(StrEnum):
    PR = "pr"
    CITIZENSHIP = "citizenship"


class SourceType(StrEnum):
    LEARNING_MATERIAL = "learning_material"
    QUESTION_PAPER = "question_paper"
    ANSWER_KEY = "answer_key"


class IngestionStatus(StrEnum):
    PENDING = "pending"
    EXTRACTING = "extracting"
    VALIDATED = "validated"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


class ChoiceLetter(StrEnum):
    A = "A"
    B = "B"
    C = "C"


class TrackDefinition(BaseModel):
    slug: ExamTrackSlug
    name: str
    official_name: str
    question_dir_names: list[str]
    answer_dir_name: str = "answers"
    learning_material_dir_name: str = "learning material"


TRACKS: dict[ExamTrackSlug, TrackDefinition] = {
    ExamTrackSlug.PR: TrackDefinition(
        slug=ExamTrackSlug.PR,
        name="Permanent Residence",
        official_name="Medborgerskabsproeven",
        question_dir_names=["question", "questions"],
    ),
    ExamTrackSlug.CITIZENSHIP: TrackDefinition(
        slug=ExamTrackSlug.CITIZENSHIP,
        name="Danish Citizenship",
        official_name="Indfoedsretsproeven",
        question_dir_names=["questions", "question"],
    ),
}


class SourceDocumentManifest(BaseModel):
    track: ExamTrackSlug
    source_type: SourceType
    source_path: str
    original_filename: str
    content_sha256: str
    file_size_bytes: int
    parser_version: str
    paired_source_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PaperPairManifest(BaseModel):
    track: ExamTrackSlug
    paper_code: str
    question_pdf: SourceDocumentManifest
    answer_pdf: SourceDocumentManifest | None
    validation_warnings: list[str] = Field(default_factory=list)


class IngestionManifest(BaseModel):
    root_path: str
    parser_version: str
    learning_materials: list[SourceDocumentManifest]
    paper_pairs: list[PaperPairManifest]
    warnings: list[str] = Field(default_factory=list)


class ParsedQuestion(BaseModel):
    question_number: int
    stem: str
    choices: dict[ChoiceLetter, str]
    source_page_start: int | None = None
    source_page_end: int | None = None


class ParsedAnswerKey(BaseModel):
    answers: dict[int, ChoiceLetter]


class ParsedOfficialQuestion(ParsedQuestion):
    correct_choice: ChoiceLetter
    content_sha256: str


class ValidationReport(BaseModel):
    status: str
    expected_question_count: int | None = None
    parsed_question_count: int
    parsed_answer_count: int
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RetrievalHit(BaseModel):
    collection: str
    score: float
    payload: dict[str, Any]


class BlueprintValidationResult(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SourceDocumentRecord(BaseModel):
    id: UUID
    exam_track_id: UUID
    source_type: SourceType
    original_filename: str
    source_path: str
    storage_uri: str
    content_sha256: str

