from uuid import UUID

from fastapi import APIRouter, HTTPException

from denmark_academy.phase2_schemas import PracticeAnswerRequest, PracticeSessionCreate, PracticeSubmitRequest
from denmark_academy.practice.service import PracticeService

router = APIRouter(prefix="/api/v1", tags=["practice"])
service = PracticeService()


@router.post("/practice/sessions")
def create_session(payload: PracticeSessionCreate) -> dict:
    try:
        return service.create_session(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/practice/sessions/{session_id}")
def get_session(session_id: UUID) -> dict:
    try:
        return service.get_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/practice/sessions/{session_id}/questions/{session_question_id}/answer")
def answer_question(session_id: UUID, session_question_id: UUID, payload: PracticeAnswerRequest) -> dict:
    try:
        return service.answer_question(session_id, session_question_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/practice/sessions/{session_id}/submit")
def submit_session(session_id: UUID, payload: PracticeSubmitRequest) -> dict:
    return service.submit_session(session_id, payload)


@router.get("/users/{user_id}/tracks/{track}/revision")
def revision_queue(user_id: UUID, track: str, limit: int = 50) -> list[dict]:
    return service.revision_queue(user_id, track, limit)
