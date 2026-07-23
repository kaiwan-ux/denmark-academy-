from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

SourceType = Literal['government_site', 'immigration_site', 'citizenship_resource', 'official_pdf', 'rss_feed', 'news_api', 'mcp_connector', 'manual_upload']
DocumentType = Literal['html', 'pdf', 'rss_item', 'news_article', 'manual_upload', 'mcp_resource']
GeneratedResourceType = Literal['summary', 'revision_note', 'flashcard', 'practice_question', 'official_style_question']


class KnowledgeSourceCreate(BaseModel):
    track: Literal['pr', 'citizenship'] | None = None
    source_key: str
    name: str
    source_type: SourceType
    base_url: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    trust_level: Literal['official', 'trusted', 'news', 'manual', 'experimental'] = 'official'
    collection_frequency_minutes: int = Field(default=1440, ge=5)
    is_active: bool = True


class CollectionRunRequest(BaseModel):
    source_id: UUID
    dry_run: bool = False


class CollectedDocumentInput(BaseModel):
    source_id: UUID
    track: Literal['pr', 'citizenship'] | None = None
    canonical_url: str | None = None
    title: str
    document_type: DocumentType
    raw_text: str
    language: str = 'da'
    source_published_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProcessingRequest(BaseModel):
    document_version_id: UUID
    run_embeddings: bool = True


class CurrentAffairsGenerateRequest(BaseModel):
    track: Literal['pr', 'citizenship']
    document_version_id: UUID
    generate_resources: list[GeneratedResourceType] = Field(default_factory=lambda: ['summary', 'revision_note', 'flashcard', 'practice_question'])


class ApprovalDecisionRequest(BaseModel):
    entity_type: Literal['document_version', 'current_affairs_item', 'generated_resource']
    entity_id: UUID
    decision: Literal['approved', 'rejected', 'changes_requested']
    reviewer_user_id: UUID | None = None
    review_note: str | None = None


class SchedulerJobCreate(BaseModel):
    job_key: str
    job_type: Literal['collect_source', 'process_document', 'current_affairs', 'past_paper_scan', 'quality_validate', 'notify']
    schedule_cron: str | None = None
    interval_minutes: int | None = Field(default=None, ge=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    is_enabled: bool = True


class NotificationCreate(BaseModel):
    recipient_user_id: UUID | None = None
    channel: Literal['in_app', 'email', 'webhook'] = 'in_app'
    notification_type: str
    title: str
    body: str
    entity_type: str | None = None
    entity_id: UUID | None = None


class QualityValidationResult(BaseModel):
    extraction_quality: float
    metadata_quality: float
    relevance_score: float
    duplication_risk: float
    traceability_score: float
    overall_score: float
    decision: Literal['approve', 'needs_review', 'reject']
    findings: dict[str, Any] = Field(default_factory=dict)
