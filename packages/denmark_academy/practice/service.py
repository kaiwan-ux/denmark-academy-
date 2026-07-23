from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from denmark_academy.lms.repository import Phase2Repository
from denmark_academy.phase2_schemas import PracticeAnswerRequest, PracticeSessionCreate, PracticeSubmitRequest


class PracticeService:
    def __init__(self, repository: Phase2Repository | None = None) -> None:
        self.repository = repository or Phase2Repository()

    def create_session(self, payload: PracticeSessionCreate) -> dict[str, Any]:
        with self.repository.connection() as conn:
            track_id = self.repository.track_id(conn, payload.track)
            questions = self._select_questions(conn, track_id, payload)
            if not questions:
                raise ValueError("No official questions match this practice request")
            session = conn.execute(
                """
                INSERT INTO practice_sessions (
                  user_id, exam_track_id, mode, source_type, source_id, official_exam_paper_id,
                  exam_blueprint_id, total_questions, unanswered_count, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    payload.user_id,
                    track_id,
                    payload.mode,
                    payload.source_type,
                    payload.source_id,
                    payload.source_id if payload.source_type == "past_paper" else None,
                    payload.source_id if payload.source_type == "blueprint" else None,
                    len(questions),
                    len(questions),
                    Jsonb({"requested_limit": payload.limit}),
                ),
            ).fetchone()
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO practice_session_questions (practice_session_id, official_question_id, question_order)
                    VALUES (%s, %s, %s)
                    """,
                    [(session["id"], question["id"], index + 1) for index, question in enumerate(questions)],
                )
            conn.commit()
            return {"session": dict(session), "questions": [dict(row) for row in questions]}

    def answer_question(
        self, session_id: UUID, session_question_id: UUID, payload: PracticeAnswerRequest
    ) -> dict:
        with self.repository.connection() as conn:
            row = conn.execute(
                """
                SELECT ps.user_id, ps.exam_track_id, psq.*, q.correct_choice
                FROM practice_session_questions psq
                JOIN practice_sessions ps ON ps.id = psq.practice_session_id
                JOIN official_questions q ON q.id = psq.official_question_id
                WHERE ps.id = %s AND psq.id = %s AND ps.status = 'in_progress'
                """,
                (session_id, session_question_id),
            ).fetchone()
            if not row:
                raise ValueError("Practice question not found or session is not in progress")
            is_correct = payload.selected_choice == row["correct_choice"]
            updated = conn.execute(
                """
                UPDATE practice_session_questions
                SET selected_choice = %s, is_correct = %s, answered_at = now(),
                  time_spent_seconds = time_spent_seconds + %s, marked_for_review = %s
                WHERE id = %s
                RETURNING *
                """,
                (
                    payload.selected_choice,
                    is_correct,
                    payload.time_spent_seconds,
                    payload.marked_for_review,
                    session_question_id,
                ),
            ).fetchone()
            if not is_correct:
                self._enqueue_revision(
                    conn,
                    user_id=row["user_id"],
                    exam_track_id=row["exam_track_id"],
                    official_question_id=row["official_question_id"],
                    reason="wrong_answer",
                )
            conn.commit()
            return dict(updated)

    def submit_session(self, session_id: UUID, payload: PracticeSubmitRequest) -> dict[str, Any]:
        with self.repository.connection() as conn:
            stats = conn.execute(
                """
                SELECT COUNT(*) AS total,
                  COUNT(*) FILTER (WHERE is_correct = true) AS correct,
                  COUNT(*) FILTER (WHERE is_correct = false) AS incorrect,
                  COUNT(*) FILTER (WHERE selected_choice IS NULL) AS unanswered
                FROM practice_session_questions WHERE practice_session_id = %s
                """,
                (session_id,),
            ).fetchone()
            total = stats["total"] or 0
            score = round((stats["correct"] / total) * 100, 2) if total else 0
            session = conn.execute(
                """
                UPDATE practice_sessions
                SET status = 'submitted', correct_count = %s, incorrect_count = %s,
                  unanswered_count = %s, score_percent = %s, duration_seconds = %s, submitted_at = now()
                WHERE id = %s
                RETURNING *
                """,
                (
                    stats["correct"],
                    stats["incorrect"],
                    stats["unanswered"],
                    score,
                    payload.duration_seconds,
                    session_id,
                ),
            ).fetchone()
            conn.commit()
            return {"session": dict(session), "stats": dict(stats)}

    def get_session(self, session_id: UUID) -> dict[str, Any]:
        with self.repository.connection() as conn:
            session = conn.execute("SELECT * FROM practice_sessions WHERE id = %s", (session_id,)).fetchone()
            if not session:
                raise ValueError("Practice session not found")
            questions = conn.execute(
                """
                SELECT psq.*, q.question_number, q.stem, q.choice_a, q.choice_b, q.choice_c,
                  q.correct_choice, p.paper_code
                FROM practice_session_questions psq
                JOIN official_questions q ON q.id = psq.official_question_id
                JOIN official_exam_papers p ON p.id = q.official_exam_paper_id
                WHERE psq.practice_session_id = %s
                ORDER BY psq.question_order
                """,
                (session_id,),
            ).fetchall()
            return {"session": dict(session), "questions": [dict(row) for row in questions]}

    def revision_queue(self, user_id: UUID, track: str, limit: int = 50) -> list[dict]:
        with self.repository.connection() as conn:
            track_id = self.repository.track_id(conn, track)
            rows = conn.execute(
                """
                SELECT r.*, q.stem, q.choice_a, q.choice_b, q.choice_c, q.correct_choice
                FROM revision_queue_items r
                JOIN official_questions q ON q.id = r.official_question_id
                WHERE r.user_id = %s AND r.exam_track_id = %s AND r.status = 'due' AND r.due_at <= now()
                ORDER BY r.due_at ASC LIMIT %s
                """,
                (user_id, track_id, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def _select_questions(self, conn, track_id: UUID, payload: PracticeSessionCreate) -> list[dict]:
        base_select = """
            SELECT q.id, q.question_number, q.stem, q.choice_a, q.choice_b, q.choice_c,
              q.correct_choice, p.paper_code, c.difficulty
            FROM official_questions q
            JOIN official_exam_papers p ON p.id = q.official_exam_paper_id
            LEFT JOIN official_question_classifications c ON c.official_question_id = q.id
        """
        if payload.source_type == "past_paper" and payload.source_id:
            return conn.execute(
                base_select + " WHERE q.exam_track_id = %s AND q.official_exam_paper_id = %s ORDER BY q.question_number",
                (track_id, payload.source_id),
            ).fetchall()
        if payload.source_type == "topic" and payload.source_id:
            return conn.execute(
                base_select + " WHERE q.exam_track_id = %s AND c.topic_id = %s ORDER BY random() LIMIT %s",
                (track_id, payload.source_id, payload.limit),
            ).fetchall()
        if payload.source_type == "chapter" and payload.source_id:
            return conn.execute(
                base_select + " WHERE q.exam_track_id = %s AND c.chapter_id = %s ORDER BY random() LIMIT %s",
                (track_id, payload.source_id, payload.limit),
            ).fetchall()
        if payload.source_type == "revision":
            return conn.execute(
                base_select
                + """
                  JOIN revision_queue_items r ON r.official_question_id = q.id
                  WHERE q.exam_track_id = %s AND r.user_id = %s AND r.status = 'due'
                  ORDER BY r.due_at ASC LIMIT %s
                """,
                (track_id, payload.user_id, payload.limit),
            ).fetchall()
        if payload.mode == "bookmarked_question_practice":
            return conn.execute(
                base_select
                + """
                  JOIN user_bookmarks b ON b.entity_id = q.id AND b.entity_type = 'official_question'
                  WHERE q.exam_track_id = %s AND b.user_id = %s
                  ORDER BY b.created_at DESC LIMIT %s
                """,
                (track_id, payload.user_id, payload.limit),
            ).fetchall()
        if payload.source_type == "blueprint" and payload.source_id:
            blueprint = conn.execute("SELECT * FROM exam_blueprints WHERE id = %s", (payload.source_id,)).fetchone()
            limit = blueprint["total_questions"] if blueprint else payload.limit
            return conn.execute(
                base_select + " WHERE q.exam_track_id = %s ORDER BY random() LIMIT %s",
                (track_id, limit),
            ).fetchall()
        return conn.execute(
            base_select + " WHERE q.exam_track_id = %s ORDER BY random() LIMIT %s",
            (track_id, payload.limit),
        ).fetchall()

    def _enqueue_revision(
        self,
        conn,
        *,
        user_id: UUID,
        exam_track_id: UUID,
        official_question_id: UUID,
        reason: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO revision_queue_items (user_id, exam_track_id, official_question_id, reason, attempts, last_seen_at)
            VALUES (%s, %s, %s, %s, 1, now())
            ON CONFLICT (user_id, official_question_id, reason)
            DO UPDATE SET status = 'due', due_at = now(), attempts = revision_queue_items.attempts + 1,
              last_seen_at = now()
            """,
            (user_id, exam_track_id, official_question_id, reason),
        )
