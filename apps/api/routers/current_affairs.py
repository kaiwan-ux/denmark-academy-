from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response

from denmark_academy.current_affairs.models import AnswerSubmission, PracticeRequest
from denmark_academy.current_affairs.service import CurrentAffairsService

from apps.api.routers.account import current_account

router = APIRouter(prefix="/api/v1/current-affairs", tags=["current-affairs"])
service = CurrentAffairsService()


@router.get("/articles")
async def get_articles(exam_type: str | None = None, limit: int = 20) -> list[dict]:
    """Get current affairs articles"""
    try:
        articles = service.get_articles(exam_type=exam_type, limit=limit)
        return [article.model_dump() for article in articles]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/articles/{article_id}")
async def get_article(article_id: UUID) -> dict:
    """Get single article"""
    article = service.get_article(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article.model_dump()


@router.get("/questions")
async def get_questions(
    exam_type: str | None = None,
    difficulty: str | None = None,
    limit: int = 50
) -> list[dict]:
    """Get current affairs questions"""
    try:
        questions = service.get_questions(
            exam_type=exam_type,
            difficulty=difficulty,
            limit=limit
        )
        return [q.model_dump() for q in questions]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/practice")
async def start_practice(
    request: PracticeRequest,
    response: Response,
    user: dict = Depends(current_account),
) -> dict:
    """Start a fresh authenticated Current Affairs practice session."""
    response.headers["Cache-Control"] = "no-store, private"
    try:
        return await service.start_practice_session(request, user["id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/practice/restart")
async def restart_practice(
    response: Response,
    user: dict = Depends(current_account),
) -> dict:
    """Explicitly begin a new question cycle while retaining audit history."""
    response.headers["Cache-Control"] = "no-store, private"
    return service.restart_progress(user["id"])


@router.post("/practice/{session_id}/answer")
async def submit_answer(
    session_id: UUID,
    answer: AnswerSubmission,
    response: Response,
    user: dict = Depends(current_account),
) -> dict:
    """Submit an answer belonging to the authenticated user's session."""
    response.headers["Cache-Control"] = "no-store, private"
    try:
        result = service.submit_answer(session_id, answer, user["id"])
        return result.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/practice/{session_id}/complete")
async def complete_session(
    session_id: UUID,
    response: Response,
    user: dict = Depends(current_account),
) -> dict:
    """Complete the authenticated user's practice session and get its summary."""
    response.headers["Cache-Control"] = "no-store, private"
    try:
        return service.complete_session(session_id, user["id"])
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# Admin endpoints
@router.post("/admin/fetch")
async def manual_fetch(max_articles: int | None = None) -> dict:
    """Manually trigger article fetch and processing"""
    try:
        stats = await service.fetch_and_process_articles(max_articles=max_articles)
        return stats
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
