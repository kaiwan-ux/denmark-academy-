from __future__ import annotations

from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field, model_validator

from apps.api.routers.account import current_account, db


router = APIRouter(prefix="/api/v1/chapter-practice", tags=["chapter-practice"])
MODULE = "chapter_practice"


class SessionRequest(BaseModel):
    track: Literal["pr", "citizenship"]
    chapter_number: int = Field(ge=1, le=100)
    mode: Literal["sequential", "random"] = "sequential"
    start_number: int | None = Field(default=None, ge=1, le=500)
    end_number: int | None = Field(default=None, ge=1, le=500)
    count: int | None = Field(default=None, ge=1, le=500)

    @model_validator(mode="after")
    def validate_selection(self) -> "SessionRequest":
        if self.mode == "sequential":
            if self.start_number is None or self.end_number is None:
                raise ValueError("Sequential practice requires a start and end question")
            if self.start_number > self.end_number:
                raise ValueError("Start question cannot be after end question")
        elif self.count is None:
            raise ValueError("Random practice requires a question count")
        return self


class AnswerRequest(BaseModel):
    session_id: UUID
    question_id: UUID
    selected_choice: Literal["A", "B", "C"]


def _question_key(track: str, chapter_number: int, question_number: int) -> str:
    return f"chapter:{track}:{chapter_number}:{question_number}"


def _track_question_pattern(track: str) -> str:
    """Return a LIKE pattern as data, never as part of a Psycopg query string."""
    return f"chapter:{track}:%"


def _chapter_question_pattern(track: str, chapter_number: int) -> str:
    return f"chapter:{track}:{chapter_number}:%"


@router.get("/chapters")
def list_chapters(
    track: Literal["pr", "citizenship"],
    user: dict[str, Any] = Depends(current_account),
) -> dict[str, Any]:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT chapter.chapter_number, chapter.title, chapter.question_count, chapter.source_name,
                   COUNT(DISTINCT question.id) FILTER (WHERE attempt.id IS NOT NULL)::int AS completed_questions,
                   COUNT(attempt.id)::int AS total_attempts,
                   COUNT(attempt.id) FILTER (WHERE attempt.is_correct)::int AS correct_attempts
            FROM chapter_practice_chapters chapter
            JOIN chapter_practice_questions question ON question.chapter_id = chapter.id
            LEFT JOIN user_question_attempts attempt
              ON attempt.user_id = %s
             AND attempt.module = %s
             AND attempt.question_id = CONCAT(
                   'chapter:', chapter.track, ':', chapter.chapter_number, ':', question.question_number
                 )
            WHERE chapter.track = %s
            GROUP BY chapter.id
            ORDER BY chapter.chapter_number
            """,
            (user["id"], MODULE, track),
        ).fetchall()
    chapters = []
    for row in rows:
        attempts = int(row["total_attempts"] or 0)
        correct = int(row["correct_attempts"] or 0)
        chapters.append(
            {
                **dict(row),
                "accuracy": round(correct / attempts * 100, 1) if attempts else 0.0,
                "completion_percent": round(
                    int(row["completed_questions"] or 0) / int(row["question_count"]) * 100,
                    1,
                ),
            }
        )
    return {"track": track, "chapters": chapters}


@router.post("/sessions")
def create_session(
    payload: SessionRequest,
    user: dict[str, Any] = Depends(current_account),
) -> dict[str, Any]:
    del user
    with db() as conn:
        chapter = conn.execute(
            """
            SELECT id, track, chapter_number, title, question_count
            FROM chapter_practice_chapters
            WHERE track = %s AND chapter_number = %s
            """,
            (payload.track, payload.chapter_number),
        ).fetchone()
        if not chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")

        total = int(chapter["question_count"])
        if payload.mode == "sequential":
            start_number = int(payload.start_number or 1)
            end_number = int(payload.end_number or total)
            if end_number > total:
                raise HTTPException(status_code=400, detail=f"This chapter has {total} questions")
            rows = conn.execute(
                """
                SELECT id, question_number, stem, choice_a, choice_b, choice_c
                FROM chapter_practice_questions
                WHERE chapter_id = %s AND question_number BETWEEN %s AND %s
                ORDER BY question_number
                """,
                (chapter["id"], start_number, end_number),
            ).fetchall()
        else:
            count = int(payload.count or 1)
            if count > total:
                raise HTTPException(status_code=400, detail=f"This chapter has {total} questions")
            rows = conn.execute(
                """
                SELECT id, question_number, stem, choice_a, choice_b, choice_c
                FROM chapter_practice_questions
                WHERE chapter_id = %s
                ORDER BY random()
                LIMIT %s
                """,
                (chapter["id"], count),
            ).fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="No questions are available for this selection")
    return {
        "session_id": uuid4(),
        "track": payload.track,
        "chapter_number": payload.chapter_number,
        "chapter_title": chapter["title"],
        "mode": payload.mode,
        "questions": [dict(row) for row in rows],
        "count": len(rows),
    }


@router.post("/answers")
def answer_question(
    payload: AnswerRequest,
    user: dict[str, Any] = Depends(current_account),
) -> dict[str, Any]:
    with db() as conn:
        question = conn.execute(
            """
            SELECT question.id, question.question_number, question.stem,
                   question.choice_a, question.choice_b, question.choice_c,
                   question.correct_choice, chapter.track, chapter.chapter_number,
                   chapter.title AS chapter_title
            FROM chapter_practice_questions question
            JOIN chapter_practice_chapters chapter ON chapter.id = question.chapter_id
            WHERE question.id = %s
            """,
            (payload.question_id,),
        ).fetchone()
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")

        stable_key = _question_key(
            question["track"], int(question["chapter_number"]), int(question["question_number"])
        )
        client_attempt_id = f"chapter-practice:{payload.session_id}:{payload.question_id}"
        is_correct = payload.selected_choice == question["correct_choice"]
        existing = conn.execute(
            """
            SELECT selected_choice, correct_choice, is_correct
            FROM user_question_attempts
            WHERE user_id = %s AND client_attempt_id = %s
            """,
            (user["id"], client_attempt_id),
        ).fetchone()
        if existing:
            if existing["selected_choice"] != payload.selected_choice:
                raise HTTPException(
                    status_code=409, detail="This question was already answered in this session"
                )
            is_correct = bool(existing["is_correct"])
        else:
            conn.execute(
                """
                INSERT INTO user_question_attempts(
                  user_id, module, question_id, session_key, selected_choice, correct_choice,
                  is_correct, topic, track, metadata, client_attempt_id
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    user["id"],
                    MODULE,
                    stable_key,
                    str(payload.session_id),
                    payload.selected_choice,
                    question["correct_choice"],
                    is_correct,
                    question["chapter_title"],
                    question["track"],
                    Jsonb(
                        {
                            "source": "chapter_practice",
                            "chapter_number": int(question["chapter_number"]),
                            "question_number": int(question["question_number"]),
                        }
                    ),
                    client_attempt_id,
                ),
            )

        track_stats = conn.execute(
            """
            SELECT COUNT(DISTINCT attempt.question_id)::int AS completed_items,
                   COUNT(*)::int AS attempts,
                   COUNT(*) FILTER (WHERE attempt.is_correct)::int AS correct,
                   (SELECT COALESCE(SUM(question_count), 0)::int
                    FROM chapter_practice_chapters WHERE track = %s) AS total_items
            FROM user_question_attempts attempt
            WHERE attempt.user_id = %s AND attempt.module = %s AND attempt.track = %s
              AND attempt.question_id LIKE %s
            """,
            (
                question["track"],
                user["id"],
                MODULE,
                question["track"],
                _track_question_pattern(question["track"]),
            ),
        ).fetchone()
        chapter_stats = conn.execute(
            """
            SELECT COUNT(DISTINCT attempt.question_id)::int AS completed_items,
                   COUNT(*)::int AS attempts,
                   COUNT(*) FILTER (WHERE attempt.is_correct)::int AS correct
            FROM user_question_attempts attempt
            WHERE attempt.user_id = %s AND attempt.module = %s AND attempt.track = %s
              AND attempt.question_id LIKE %s
            """,
            (
                user["id"],
                MODULE,
                question["track"],
                _chapter_question_pattern(question["track"], int(question["chapter_number"])),
            ),
        ).fetchone()

        completed_items = int(track_stats["completed_items"] or 0)
        total_items = int(track_stats["total_items"] or 0)
        completion = round(completed_items / total_items * 100, 2) if total_items else 0
        route = f"/revision?track={question['track']}&chapter={question['chapter_number']}"
        title = (
            "Citizenship chapter practice"
            if question["track"] == "citizenship"
            else "Permanent Residence chapter practice"
        )
        conn.execute(
            """
            INSERT INTO user_learning_states(
              user_id, module, state_key, route, entity_id, title, completion_percent, state, completed_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT(user_id, module, state_key) DO UPDATE SET
              route=excluded.route, entity_id=excluded.entity_id, title=excluded.title,
              completion_percent=excluded.completion_percent, state=excluded.state,
              last_activity_at=now(), completed_at=excluded.completed_at
            """,
            (
                user["id"],
                MODULE,
                question["track"],
                route,
                stable_key,
                title,
                completion,
                Jsonb(
                    {
                        "completed_items": completed_items,
                        "total_items": total_items,
                        "last_chapter": int(question["chapter_number"]),
                        "last_question": int(question["question_number"]),
                    }
                ),
                None,
            ),
        )
        conn.commit()

    correct_choice = question["correct_choice"]
    correct_text = question[f"choice_{correct_choice.lower()}"]
    chapter_attempts = int(chapter_stats["attempts"] or 0)
    chapter_correct = int(chapter_stats["correct"] or 0)
    return {
        "is_correct": is_correct,
        "selected_choice": payload.selected_choice,
        "correct_choice": correct_choice,
        "correct_text": correct_text,
        "chapter_progress": {
            "completed_items": int(chapter_stats["completed_items"] or 0),
            "attempts": chapter_attempts,
            "correct": chapter_correct,
            "accuracy": round(chapter_correct / chapter_attempts * 100, 1)
            if chapter_attempts
            else 0.0,
        },
        "track_progress": dict(track_stats),
    }
