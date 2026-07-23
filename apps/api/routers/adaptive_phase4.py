from uuid import UUID

from fastapi import APIRouter, HTTPException

from denmark_academy.adaptive.schemas import AdaptiveMockRequest, ConceptCreate, LearningInteractionEvent, StudyPlannerRequest
from denmark_academy.adaptive.service import AdaptiveLearningService

router = APIRouter(prefix="/api/v1/adaptive", tags=["adaptive-learning"])
service = AdaptiveLearningService()


@router.post("/concepts")
def create_concept(payload: ConceptCreate) -> dict:
    return service.create_concept(payload)


@router.post("/interactions")
def record_interaction(payload: LearningInteractionEvent) -> dict:
    return service.record_interaction(payload)


@router.post("/users/{user_id}/tracks/{track}/refresh-profile")
def refresh_profile(user_id: UUID, track: str) -> dict:
    return service.refresh_profile(user_id, track)


@router.get("/users/{user_id}/tracks/{track}/dashboard")
def adaptive_dashboard(user_id: UUID, track: str) -> dict:
    return service.dashboard(user_id, track)


@router.get("/users/{user_id}/tracks/{track}/readiness")
def readiness(user_id: UUID, track: str) -> dict:
    return service.readiness(user_id, track)


@router.get("/users/{user_id}/tracks/{track}/pass-prediction")
def pass_prediction(user_id: UUID, track: str) -> dict:
    return service.pass_prediction(user_id, track)


@router.post("/study-plan")
def study_plan(payload: StudyPlannerRequest) -> dict:
    return service.study_plan(payload)


@router.post("/adaptive-mock-plan")
def adaptive_mock_plan(payload: AdaptiveMockRequest) -> dict:
    try:
        return service.adaptive_mock_plan(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
