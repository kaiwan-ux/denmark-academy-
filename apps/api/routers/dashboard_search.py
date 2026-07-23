from uuid import UUID

from fastapi import APIRouter

from denmark_academy.lms.repository import Phase2Repository
from denmark_academy.phase2_schemas import CountdownRequest, SearchRequest

router = APIRouter(prefix="/api/v1", tags=["dashboard-search"])
repo = Phase2Repository()


@router.get("/users/{user_id}/tracks/{track}/dashboard")
def dashboard(user_id: UUID, track: str) -> dict:
    with repo.connection() as conn:
        return repo.dashboard(conn, user_id, track)


@router.put("/users/{user_id}/tracks/{track}/exam-countdown")
def countdown(user_id: UUID, track: str, payload: CountdownRequest) -> dict:
    payload.user_id = user_id
    payload.track = track
    with repo.connection() as conn:
        row = repo.upsert_countdown(conn, payload)
        conn.commit()
        return dict(row)


@router.post("/search")
def search(payload: SearchRequest) -> dict:
    with repo.connection() as conn:
        return repo.search(conn, payload)
