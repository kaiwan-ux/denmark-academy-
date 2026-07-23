from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

GraphScope = Literal['knowledge', 'student_learning', 'cross_graph']
NodeType = Literal[
    'Book', 'Chapter', 'Topic', 'Concept', 'OfficialQuestion', 'OfficialAnswer', 'AIQuestion',
    'AIExplanation', 'Flashcard', 'RevisionNote', 'CurrentAffairs', 'GovernmentDocument',
    'PastPaper', 'MockExam', 'Student', 'LearningProfile', 'Attempt', 'Progress', 'Revision'
]


class GraphNodeUpsert(BaseModel):
    graph_scope: GraphScope
    node_type: str
    stable_key: str
    label: str
    track: Literal['pr', 'citizenship'] | None = None
    user_id: UUID | None = None
    source_table: str | None = None
    source_id: UUID | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphRelationshipUpsert(BaseModel):
    graph_scope: GraphScope
    relationship_type: str
    from_stable_key: str
    to_stable_key: str
    weight: float = 1
    confidence: float = 100
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphExploreRequest(BaseModel):
    track: Literal['pr', 'citizenship'] | None = None
    user_id: UUID | None = None
    root_stable_key: str | None = None
    query: str | None = None
    node_types: list[str] = Field(default_factory=list)
    relationship_types: list[str] = Field(default_factory=list)
    depth: int = Field(default=2, ge=1, le=4)
    limit: int = Field(default=100, ge=1, le=500)
    overlays: list[Literal['current_affairs', 'weakness', 'mastery', 'difficulty']] = Field(default_factory=list)


class MentorRequest(BaseModel):
    user_id: UUID
    track: Literal['pr', 'citizenship']
    message: str
    available_minutes: int | None = Field(default=None, ge=5, le=480)
    goal: str | None = None


class LearningPathRequest(BaseModel):
    user_id: UUID | None = None
    track: Literal['pr', 'citizenship']
    from_concept_key: str
    to_concept_key: str
    include_student_state: bool = True


class ExamSimulationCreate(BaseModel):
    user_id: UUID
    track: Literal['pr', 'citizenship']
    name: str
    mode: Literal['official', 'ai', 'mixed', 'topic', 'weak_topic', 'current_affairs', 'custom', 'adaptive', 'official_replay']
    difficulty: Literal['easy', 'medium', 'official', 'hard', 'adaptive'] = 'official'
    blueprint_id: UUID | None = None
    timer_seconds: int | None = None
    official_percent: int = Field(default=100, ge=0, le=100)
    ai_percent: int = Field(default=0, ge=0, le=100)
    filters: dict[str, Any] = Field(default_factory=dict)

    def validate_ratio(self) -> None:
        if self.official_percent + self.ai_percent != 100:
            raise ValueError('official_percent and ai_percent must total 100')


class ExamAutoSaveRequest(BaseModel):
    state: dict[str, Any]


class NodeDetailResponse(BaseModel):
    node: dict[str, Any]
    relationships: list[dict[str, Any]]
    related_concepts: list[dict[str, Any]] = Field(default_factory=list)
    recommended_next_concept: dict[str, Any] | None = None
