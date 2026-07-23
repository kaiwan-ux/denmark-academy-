from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from denmark_academy.config import get_settings
from denmark_academy.phase2_schemas import (
    BookmarkRequest,
    CategoryCreate,
    ChapterCreate,
    CountdownRequest,
    CourseCreate,
    HighlightRequest,
    LearningUnitCreate,
    NoteRequest,
    QuestionClassificationRequest,
    ReadingProgressUpdate,
    SearchRequest,
    TopicCreate,
)


class Phase2Repository:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.database_url = self.settings.database_url

    def connection(self):
        return psycopg.connect(
            self.database_url,
            row_factory=dict_row,
            connect_timeout=self.settings.database_connect_timeout_seconds,
        )

    def track_id(self, conn, track: str) -> UUID:
        row = conn.execute("SELECT id FROM exam_tracks WHERE slug = %s", (track,)).fetchone()
        if row is None:
            raise ValueError(f"Unknown exam track: {track}")
        return row["id"]

    def create_course(self, conn, payload: CourseCreate) -> dict:
        track_id = self.track_id(conn, payload.track)
        return conn.execute(
            """
            INSERT INTO courses (exam_track_id, title, description, status, estimated_minutes)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (exam_track_id)
            DO UPDATE SET title = EXCLUDED.title, description = EXCLUDED.description,
              status = EXCLUDED.status, estimated_minutes = EXCLUDED.estimated_minutes, updated_at = now()
            RETURNING *
            """,
            (track_id, payload.title, payload.description, payload.status, payload.estimated_minutes),
        ).fetchone()

    def create_chapter(self, conn, payload: ChapterCreate) -> dict:
        course = self.get_course(conn, payload.course_id)
        return conn.execute(
            """
            INSERT INTO course_chapters (
              course_id, exam_track_id, title, summary, slug, sort_order, estimated_minutes, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                payload.course_id,
                course["exam_track_id"],
                payload.title,
                payload.summary,
                payload.slug,
                payload.sort_order,
                payload.estimated_minutes,
                payload.status,
            ),
        ).fetchone()

    def create_topic(self, conn, payload: TopicCreate) -> dict:
        chapter = conn.execute("SELECT * FROM course_chapters WHERE id = %s", (payload.chapter_id,)).fetchone()
        if not chapter:
            raise ValueError("Chapter not found")
        return conn.execute(
            """
            INSERT INTO course_topics (
              chapter_id, course_id, exam_track_id, title, summary, slug, sort_order, estimated_minutes, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                payload.chapter_id,
                chapter["course_id"],
                chapter["exam_track_id"],
                payload.title,
                payload.summary,
                payload.slug,
                payload.sort_order,
                payload.estimated_minutes,
                payload.status,
            ),
        ).fetchone()

    def create_learning_unit(self, conn, payload: LearningUnitCreate) -> dict:
        course = self.get_course(conn, payload.course_id)
        return conn.execute(
            """
            INSERT INTO learning_units (
              exam_track_id, course_id, chapter_id, topic_id, subtopic_id, source_document_id,
              document_chunk_id, title, body, estimated_minutes, sort_order, status, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                course["exam_track_id"],
                payload.course_id,
                payload.chapter_id,
                payload.topic_id,
                payload.subtopic_id,
                payload.source_document_id,
                payload.document_chunk_id,
                payload.title,
                payload.body,
                payload.estimated_minutes,
                payload.sort_order,
                payload.status,
                Jsonb(payload.metadata),
            ),
        ).fetchone()

    def get_course(self, conn, course_id: UUID) -> dict:
        row = conn.execute("SELECT * FROM courses WHERE id = %s", (course_id,)).fetchone()
        if not row:
            raise ValueError("Course not found")
        return row

    def course_outline(self, conn, track: str) -> dict:
        track_id = self.track_id(conn, track)
        course = conn.execute("SELECT * FROM courses WHERE exam_track_id = %s", (track_id,)).fetchone()
        if not course:
            return {"track": track, "course": None, "chapters": []}
        chapters = conn.execute(
            "SELECT * FROM course_chapters WHERE course_id = %s ORDER BY sort_order", (course["id"],)
        ).fetchall()
        topics = conn.execute(
            "SELECT * FROM course_topics WHERE course_id = %s ORDER BY sort_order", (course["id"],)
        ).fetchall()
        units = conn.execute(
            "SELECT id, chapter_id, topic_id, title, estimated_minutes, sort_order, status FROM learning_units WHERE course_id = %s ORDER BY sort_order",
            (course["id"],),
        ).fetchall()
        topics_by_chapter: dict[UUID, list[dict]] = {}
        for topic in topics:
            topic = dict(topic)
            topic["learning_units"] = [dict(unit) for unit in units if unit["topic_id"] == topic["id"]]
            topics_by_chapter.setdefault(topic["chapter_id"], []).append(topic)
        return {
            "track": track,
            "course": dict(course),
            "chapters": [
                {**dict(chapter), "topics": topics_by_chapter.get(chapter["id"], [])}
                for chapter in chapters
            ],
        }

    def learning_unit(self, conn, unit_id: UUID, user_id: UUID | None = None) -> dict:
        unit = conn.execute("SELECT * FROM learning_units WHERE id = %s", (unit_id,)).fetchone()
        if not unit:
            raise ValueError("Learning unit not found")
        result = dict(unit)
        if user_id:
            progress = conn.execute(
                "SELECT * FROM reading_progress WHERE user_id = %s AND learning_unit_id = %s",
                (user_id, unit_id),
            ).fetchone()
            result["progress"] = dict(progress) if progress else None
        return result

    def update_reading_progress(
        self, conn, user_id: UUID, learning_unit_id: UUID, payload: ReadingProgressUpdate
    ) -> dict:
        unit = conn.execute("SELECT exam_track_id FROM learning_units WHERE id = %s", (learning_unit_id,)).fetchone()
        if not unit:
            raise ValueError("Learning unit not found")
        completed_at = "now()" if payload.percent_complete >= 100 else "NULL"
        return conn.execute(
            f"""
            INSERT INTO reading_progress (
              user_id, exam_track_id, learning_unit_id, percent_complete, last_position,
              time_spent_seconds, completed_at
            ) VALUES (%s, %s, %s, %s, %s, %s, {completed_at})
            ON CONFLICT (user_id, learning_unit_id)
            DO UPDATE SET percent_complete = EXCLUDED.percent_complete,
              last_position = EXCLUDED.last_position,
              time_spent_seconds = reading_progress.time_spent_seconds + EXCLUDED.time_spent_seconds,
              completed_at = CASE WHEN EXCLUDED.percent_complete >= 100 THEN now() ELSE reading_progress.completed_at END,
              updated_at = now()
            RETURNING *
            """,
            (
                user_id,
                unit["exam_track_id"],
                learning_unit_id,
                payload.percent_complete,
                Jsonb(payload.last_position),
                payload.time_spent_seconds,
            ),
        ).fetchone()

    def upsert_bookmark(self, conn, user_id: UUID, track: str, payload: BookmarkRequest) -> dict:
        track_id = self.track_id(conn, track)
        return conn.execute(
            """
            INSERT INTO user_bookmarks (user_id, exam_track_id, entity_type, entity_id, label)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_id, entity_type, entity_id)
            DO UPDATE SET label = EXCLUDED.label
            RETURNING *
            """,
            (user_id, track_id, payload.entity_type, payload.entity_id, payload.label),
        ).fetchone()

    def create_note(self, conn, user_id: UUID, track: str, payload: NoteRequest) -> dict:
        track_id = self.track_id(conn, track)
        return conn.execute(
            """
            INSERT INTO user_notes (user_id, exam_track_id, entity_type, entity_id, body, anchor)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (user_id, track_id, payload.entity_type, payload.entity_id, payload.body, Jsonb(payload.anchor)),
        ).fetchone()

    def create_highlight(self, conn, user_id: UUID, track: str, payload: HighlightRequest) -> dict:
        track_id = self.track_id(conn, track)
        return conn.execute(
            """
            INSERT INTO user_highlights (user_id, exam_track_id, learning_unit_id, selected_text, color, anchor)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (user_id, track_id, payload.learning_unit_id, payload.selected_text, payload.color, Jsonb(payload.anchor)),
        ).fetchone()

    def create_category(self, conn, payload: CategoryCreate) -> dict:
        track_id = self.track_id(conn, payload.track)
        return conn.execute(
            """
            INSERT INTO question_categories (exam_track_id, name, slug, description)
            VALUES (%s, %s, %s, %s)
            RETURNING *
            """,
            (track_id, payload.name, payload.slug, payload.description),
        ).fetchone()

    def classify_question(self, conn, track: str, payload: QuestionClassificationRequest) -> dict:
        track_id = self.track_id(conn, track)
        return conn.execute(
            """
            INSERT INTO official_question_classifications (
              official_question_id, exam_track_id, chapter_id, topic_id, subtopic_id, category_id, difficulty, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (official_question_id)
            DO UPDATE SET chapter_id = EXCLUDED.chapter_id, topic_id = EXCLUDED.topic_id,
              subtopic_id = EXCLUDED.subtopic_id, category_id = EXCLUDED.category_id,
              difficulty = EXCLUDED.difficulty, metadata = EXCLUDED.metadata
            RETURNING *
            """,
            (
                payload.official_question_id,
                track_id,
                payload.chapter_id,
                payload.topic_id,
                payload.subtopic_id,
                payload.category_id,
                payload.difficulty,
                Jsonb(payload.metadata),
            ),
        ).fetchone()

    def search(self, conn, payload: SearchRequest) -> dict[str, list[dict]]:
        track_id = self.track_id(conn, payload.track)
        like = f"%{payload.query}%"
        results: dict[str, list[dict]] = {}
        if "learning_unit" in payload.entity_types:
            results["learning_units"] = conn.execute(
                """
                SELECT id, title, body, estimated_minutes, status
                FROM learning_units
                WHERE exam_track_id = %s AND (%s = '' OR title ILIKE %s OR body ILIKE %s)
                ORDER BY sort_order LIMIT %s OFFSET %s
                """,
                (track_id, payload.query, like, like, payload.limit, payload.offset),
            ).fetchall()
        if "chapter" in payload.entity_types:
            results["chapters"] = conn.execute(
                """
                SELECT id, title, summary, slug, estimated_minutes, status
                FROM course_chapters
                WHERE exam_track_id = %s AND (%s = '' OR title ILIKE %s OR summary ILIKE %s)
                ORDER BY sort_order LIMIT %s OFFSET %s
                """,
                (track_id, payload.query, like, like, payload.limit, payload.offset),
            ).fetchall()
        if "topic" in payload.entity_types:
            results["topics"] = conn.execute(
                """
                SELECT id, title, summary, slug, estimated_minutes, status
                FROM course_topics
                WHERE exam_track_id = %s AND (%s = '' OR title ILIKE %s OR summary ILIKE %s)
                ORDER BY sort_order LIMIT %s OFFSET %s
                """,
                (track_id, payload.query, like, like, payload.limit, payload.offset),
            ).fetchall()
        if "official_question" in payload.entity_types:
            results["official_questions"] = conn.execute(
                """
                SELECT q.id, q.question_number, q.stem, q.choice_a, q.choice_b, q.choice_c,
                  q.correct_choice, p.paper_code, c.difficulty
                FROM official_questions q
                JOIN official_exam_papers p ON p.id = q.official_exam_paper_id
                LEFT JOIN official_question_classifications c ON c.official_question_id = q.id
                WHERE q.exam_track_id = %s
                  AND (%s = '' OR q.stem ILIKE %s OR q.choice_a ILIKE %s OR q.choice_b ILIKE %s OR q.choice_c ILIKE %s)
                  AND (%s IS NULL OR c.difficulty = %s)
                ORDER BY p.paper_code, q.question_number LIMIT %s OFFSET %s
                """,
                (
                    track_id,
                    payload.query,
                    like,
                    like,
                    like,
                    like,
                    payload.difficulty,
                    payload.difficulty,
                    payload.limit,
                    payload.offset,
                ),
            ).fetchall()
        if "past_paper" in payload.entity_types:
            results["past_papers"] = conn.execute(
                """
                SELECT id, paper_code, title, duration_minutes, expected_question_count, validation_status
                FROM official_exam_papers
                WHERE exam_track_id = %s AND (%s = '' OR title ILIKE %s OR paper_code ILIKE %s)
                ORDER BY paper_code LIMIT %s OFFSET %s
                """,
                (track_id, payload.query, like, like, payload.limit, payload.offset),
            ).fetchall()
        return {key: [dict(row) for row in rows] for key, rows in results.items()}

    def dashboard(self, conn, user_id: UUID, track: str) -> dict[str, Any]:
        track_id = self.track_id(conn, track)
        course = conn.execute("SELECT * FROM courses WHERE exam_track_id = %s", (track_id,)).fetchone()
        reading = conn.execute(
            """
            SELECT COUNT(*) AS units_started,
              COALESCE(AVG(percent_complete), 0) AS average_completion,
              COALESCE(SUM(time_spent_seconds), 0) AS reading_seconds
            FROM reading_progress WHERE user_id = %s AND exam_track_id = %s
            """,
            (user_id, track_id),
        ).fetchone()
        practice = conn.execute(
            """
            SELECT COUNT(*) AS sessions, COALESCE(AVG(score_percent), 0) AS average_score,
              COALESCE(SUM(duration_seconds), 0) AS practice_seconds
            FROM practice_sessions WHERE user_id = %s AND exam_track_id = %s AND status = 'submitted'
            """,
            (user_id, track_id),
        ).fetchone()
        revision_due = conn.execute(
            """
            SELECT COUNT(*) AS due_count FROM revision_queue_items
            WHERE user_id = %s AND exam_track_id = %s AND status = 'due' AND due_at <= now()
            """,
            (user_id, track_id),
        ).fetchone()
        bookmarks = conn.execute(
            "SELECT COUNT(*) AS bookmark_count FROM user_bookmarks WHERE user_id = %s AND exam_track_id = %s",
            (user_id, track_id),
        ).fetchone()
        streak = conn.execute(
            "SELECT * FROM user_streaks WHERE user_id = %s AND exam_track_id = %s",
            (user_id, track_id),
        ).fetchone()
        countdown = conn.execute(
            "SELECT * FROM exam_countdowns WHERE user_id = %s AND exam_track_id = %s",
            (user_id, track_id),
        ).fetchone()
        recent_sessions = conn.execute(
            """
            SELECT id, mode, status, total_questions, correct_count, score_percent, submitted_at, started_at
            FROM practice_sessions WHERE user_id = %s AND exam_track_id = %s
            ORDER BY started_at DESC LIMIT 5
            """,
            (user_id, track_id),
        ).fetchall()
        return {
            "track": track,
            "course": dict(course) if course else None,
            "reading": dict(reading),
            "practice": dict(practice),
            "revision": dict(revision_due),
            "bookmarks": dict(bookmarks),
            "streak": dict(streak) if streak else None,
            "exam_countdown": dict(countdown) if countdown else None,
            "recent_sessions": [dict(row) for row in recent_sessions],
        }

    def upsert_countdown(self, conn, payload: CountdownRequest) -> dict:
        track_id = self.track_id(conn, payload.track)
        return conn.execute(
            """
            INSERT INTO exam_countdowns (user_id, exam_track_id, target_exam_date, label)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id, exam_track_id)
            DO UPDATE SET target_exam_date = EXCLUDED.target_exam_date, label = EXCLUDED.label, updated_at = now()
            RETURNING *
            """,
            (payload.user_id, track_id, payload.target_exam_date, payload.label),
        ).fetchone()
