from fastapi import APIRouter, HTTPException
from denmark_academy.lms.seeding import CourseSeeder

from denmark_academy.lms.repository import Phase2Repository
from denmark_academy.phase2_schemas import (
    CategoryCreate,
    ChapterCreate,
    CourseCreate,
    LearningUnitCreate,
    QuestionClassificationRequest,
    TopicCreate,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin-phase2"])
repo = Phase2Repository()


@router.post("/courses")
def create_course(payload: CourseCreate) -> dict:
    with repo.connection() as conn:
        row = repo.create_course(conn, payload)
        conn.commit()
        return dict(row)


@router.post("/chapters")
def create_chapter(payload: ChapterCreate) -> dict:
    try:
        with repo.connection() as conn:
            row = repo.create_chapter(conn, payload)
            conn.commit()
            return dict(row)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/topics")
def create_topic(payload: TopicCreate) -> dict:
    try:
        with repo.connection() as conn:
            row = repo.create_topic(conn, payload)
            conn.commit()
            return dict(row)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/learning-units")
def create_learning_unit(payload: LearningUnitCreate) -> dict:
    try:
        with repo.connection() as conn:
            row = repo.create_learning_unit(conn, payload)
            conn.commit()
            return dict(row)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/question-categories")
def create_category(payload: CategoryCreate) -> dict:
    with repo.connection() as conn:
        row = repo.create_category(conn, payload)
        conn.commit()
        return dict(row)


@router.put("/tracks/{track}/question-classifications")
def classify_question(track: str, payload: QuestionClassificationRequest) -> dict:
    with repo.connection() as conn:
        row = repo.classify_question(conn, track, payload)
        conn.commit()
        return dict(row)


@router.post("/tracks/{track}/seed-course-from-chunks")
def seed_course_from_chunks(track: str, publish: bool = False) -> dict:
    return CourseSeeder(repo).seed_from_learning_chunks(track, publish)
