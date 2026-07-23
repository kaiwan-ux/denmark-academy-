from uuid import UUID

from fastapi import APIRouter, HTTPException

from denmark_academy.graph.schemas import (
    ExamAutoSaveRequest,
    ExamSimulationCreate,
    GraphExploreRequest,
    GraphNodeUpsert,
    GraphRelationshipUpsert,
    LearningPathRequest,
    MentorRequest,
)
from denmark_academy.graph.repository import GraphRepository
from denmark_academy.graph.services import ExamSimulationService, GraphIntelligenceService, MentorService
from denmark_academy.graph.sync import GraphSyncService

router = APIRouter(prefix='/api/v1/graph', tags=['mentor-exam-graph'])
repo = GraphRepository()
graph_service = GraphIntelligenceService(repo)
sync_service = GraphSyncService(repo)
mentor_service = MentorService(graph_service)
exam_service = ExamSimulationService(repo)


@router.post('/nodes')
def upsert_node(payload: GraphNodeUpsert) -> dict:
    with repo.connection() as conn:
        row = repo.upsert_node(conn, payload)
        conn.commit()
        return row


@router.post('/relationships')
def upsert_relationship(payload: GraphRelationshipUpsert) -> dict:
    try:
        with repo.connection() as conn:
            row = repo.upsert_relationship(conn, payload)
            conn.commit()
            return row
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post('/sync/tracks/{track}')
def sync_track(track: str) -> dict:
    return sync_service.sync_track(track)


@router.post('/sync/users/{user_id}/tracks/{track}')
def sync_student(user_id: UUID, track: str) -> dict:
    return sync_service.sync_student(user_id, track)


@router.post('/explore')
def explore(payload: GraphExploreRequest) -> dict:
    return graph_service.explore(payload)


@router.get('/nodes/{stable_key}/detail')
def node_detail(stable_key: str, user_id: UUID | None = None) -> dict:
    try:
        return graph_service.node_detail(stable_key, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post('/learning-path')
def learning_path(payload: LearningPathRequest) -> dict:
    return graph_service.shortest_learning_path(payload)


@router.get('/tracks/{track}/metrics')
def metrics(track: str, user_id: UUID | None = None) -> dict:
    return graph_service.graph_metrics(track, user_id)


@router.post('/mentor/advise')
def mentor_advise(payload: MentorRequest) -> dict:
    return mentor_service.advise(payload)


@router.post('/exam-simulations/configs')
def create_exam_config(payload: ExamSimulationCreate) -> dict:
    try:
        return exam_service.create_config(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put('/exam-simulations/attempts/{attempt_id}/autosave')
def autosave(attempt_id: UUID, payload: ExamAutoSaveRequest) -> dict:
    return exam_service.autosave(attempt_id, payload)


@router.post('/exam-simulations/attempts/{attempt_id}/report')
def post_submit_report(attempt_id: UUID) -> dict:
    try:
        return exam_service.post_submit_report(attempt_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
