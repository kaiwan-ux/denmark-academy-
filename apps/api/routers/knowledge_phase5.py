from uuid import UUID

from fastapi import APIRouter, HTTPException

from denmark_academy.knowledge.schemas import (
    ApprovalDecisionRequest,
    CollectedDocumentInput,
    CurrentAffairsGenerateRequest,
    KnowledgeSourceCreate,
    NotificationCreate,
    ProcessingRequest,
    SchedulerJobCreate,
)
from denmark_academy.knowledge.service import KnowledgeAutomationService

router = APIRouter(prefix='/api/v1/knowledge', tags=['knowledge-automation'])
service = KnowledgeAutomationService()


@router.post('/sources')
def create_source(payload: KnowledgeSourceCreate) -> dict:
    return service.create_source(payload)


@router.get('/sources')
def list_sources() -> list[dict]:
    return service.list_sources()


@router.post('/documents/manual')
def ingest_manual_document(payload: CollectedDocumentInput) -> dict:
    return service.ingest_manual_document(payload)


@router.post('/documents/process')
def process_document(payload: ProcessingRequest) -> dict:
    try:
        return service.process_document(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post('/current-affairs/generate')
def generate_current_affairs(payload: CurrentAffairsGenerateRequest) -> dict:
    try:
        return service.generate_current_affairs(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post('/approvals/decision')
def decide_approval(payload: ApprovalDecisionRequest) -> dict:
    return service.decide_approval(payload)


@router.post('/scheduler/jobs')
def create_scheduler_job(payload: SchedulerJobCreate) -> dict:
    return service.create_scheduler_job(payload)


@router.post('/notifications')
def create_notification(payload: NotificationCreate) -> dict:
    return service.create_notification(payload)


@router.get('/analytics')
def analytics() -> dict:
    return service.analytics()
