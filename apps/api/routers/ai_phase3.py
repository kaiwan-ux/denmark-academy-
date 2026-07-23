from uuid import UUID

from fastapi import APIRouter, HTTPException

from denmark_academy.ai.evaluation import AIEvaluator
from denmark_academy.ai.rag import HybridRAGEngine
from denmark_academy.ai.schemas import (
    AIArtifactRequest,
    AIMockRequest,
    EvaluationRequest,
    RecommendationRequest,
    RetrievalRequest,
    StudyPlanRequest,
)
from denmark_academy.ai.services import AIIntelligenceService

router = APIRouter(prefix="/api/v1/ai", tags=["ai-intelligence"])
service = AIIntelligenceService()
rag = HybridRAGEngine()
evaluator = AIEvaluator()


@router.post("/rag/retrieve")
def retrieve(payload: RetrievalRequest) -> dict:
    sources, snapshot = rag.retrieve(payload)
    return {"snapshot": snapshot, "sources": [source.model_dump(mode="json") for source in sources]}


@router.post("/tutor")
async def tutor(payload: AIArtifactRequest) -> dict:
    return await service.tutor(payload)


@router.post("/explanations")
async def explanation(payload: AIArtifactRequest) -> dict:
    return await service.explanation(payload)


@router.post("/similar-questions")
async def similar_questions(payload: AIArtifactRequest) -> dict:
    return await service.similar_questions(payload)


@router.post("/flashcards")
async def flashcards(payload: AIArtifactRequest) -> dict:
    return await service.flashcards(payload)


@router.post("/notes")
async def notes(payload: AIArtifactRequest) -> dict:
    return await service.notes(payload)


@router.post("/quizzes")
async def quiz(payload: AIArtifactRequest) -> dict:
    return await service.quiz(payload)


@router.post("/revision-assistant")
async def revision_assistant(payload: AIArtifactRequest) -> dict:
    return await service.revision_assistant(payload)


@router.post("/study-plans")
async def study_plan(payload: StudyPlanRequest) -> dict:
    return await service.study_plan(payload)


@router.post("/mock-exams")
def ai_mock(payload: AIMockRequest) -> dict:
    try:
        return service.create_ai_mock(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/recommendations")
def recommendations(payload: RecommendationRequest) -> dict:
    return service.recommendations(payload)


@router.get("/users/{user_id}/tracks/{track}/weaknesses")
def weakness_analysis(user_id: UUID, track: str) -> dict:
    return service.weakness_analysis(user_id, track)


@router.post("/evaluate")
def evaluate(payload: EvaluationRequest) -> dict:
    return evaluator.evaluate(payload).model_dump(mode="json")
