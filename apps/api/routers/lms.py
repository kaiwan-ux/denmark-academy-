from uuid import UUID

from fastapi import APIRouter, HTTPException

from denmark_academy.lms.repository import Phase2Repository
from denmark_academy.phase2_schemas import (
    BookmarkRequest,
    HighlightRequest,
    NoteRequest,
    ReadingProgressUpdate,
)

router = APIRouter(prefix="/api/v1", tags=["lms"])
repo = Phase2Repository()


@router.get("/tracks/{track}/course")
def course_outline(track: str) -> dict:
    with repo.connection() as conn:
        return repo.course_outline(conn, track)


@router.get("/learning-units/{unit_id}")
def learning_unit(unit_id: UUID, user_id: UUID | None = None) -> dict:
    try:
        with repo.connection() as conn:
            return repo.learning_unit(conn, unit_id, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/users/{user_id}/reading-progress/{learning_unit_id}")
def update_reading_progress(user_id: UUID, learning_unit_id: UUID, payload: ReadingProgressUpdate) -> dict:
    try:
        with repo.connection() as conn:
            row = repo.update_reading_progress(conn, user_id, learning_unit_id, payload)
            conn.commit()
            return dict(row)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/users/{user_id}/tracks/{track}/bookmarks")
def bookmark(user_id: UUID, track: str, payload: BookmarkRequest) -> dict:
    with repo.connection() as conn:
        row = repo.upsert_bookmark(conn, user_id, track, payload)
        conn.commit()
        return dict(row)


@router.post("/users/{user_id}/tracks/{track}/notes")
def note(user_id: UUID, track: str, payload: NoteRequest) -> dict:
    with repo.connection() as conn:
        row = repo.create_note(conn, user_id, track, payload)
        conn.commit()
        return dict(row)


@router.post("/users/{user_id}/tracks/{track}/highlights")
def highlight(user_id: UUID, track: str, payload: HighlightRequest) -> dict:
    with repo.connection() as conn:
        row = repo.create_highlight(conn, user_id, track, payload)
        conn.commit()
        return dict(row)
