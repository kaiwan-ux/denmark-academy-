from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from denmark_academy.adaptive.schemas import ConceptCreate
from denmark_academy.config import get_settings


class AdaptiveRepository:
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
        if not row:
            raise ValueError(f"Unknown exam track: {track}")
        return row["id"]

    def create_concept(self, conn, payload: ConceptCreate) -> dict:
        track_id = self.track_id(conn, payload.track)
        return conn.execute(
            """
            INSERT INTO learning_concepts (
              exam_track_id, course_id, chapter_id, topic_id, parent_concept_id,
              name, slug, description, sort_order, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                track_id,
                payload.course_id,
                payload.chapter_id,
                payload.topic_id,
                payload.parent_concept_id,
                payload.name,
                payload.slug,
                payload.description,
                payload.sort_order,
                Jsonb(payload.metadata),
            ),
        ).fetchone()

    def get_or_create_profile(self, conn, user_id: UUID, track: str) -> dict:
        track_id = self.track_id(conn, track)
        row = conn.execute(
            """
            INSERT INTO student_learning_profiles (user_id, exam_track_id)
            VALUES (%s, %s)
            ON CONFLICT (user_id, exam_track_id) DO UPDATE SET updated_at = now()
            RETURNING *
            """,
            (user_id, track_id),
        ).fetchone()
        return row

    def upsert_profile_metrics(self, conn, user_id: UUID, track: str, metrics: dict[str, Any]) -> dict:
        track_id = self.track_id(conn, track)
        row = conn.execute(
            """
            INSERT INTO student_learning_profiles (
              user_id, exam_track_id, reading_progress, overall_accuracy, average_mastery,
              confidence_score, study_frequency_days, preferred_difficulty, learning_velocity,
              time_spent_seconds, revision_accuracy, last_interaction_at, profile
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), %s)
            ON CONFLICT (user_id, exam_track_id)
            DO UPDATE SET reading_progress = EXCLUDED.reading_progress,
              overall_accuracy = EXCLUDED.overall_accuracy,
              average_mastery = EXCLUDED.average_mastery,
              confidence_score = EXCLUDED.confidence_score,
              study_frequency_days = EXCLUDED.study_frequency_days,
              preferred_difficulty = EXCLUDED.preferred_difficulty,
              learning_velocity = EXCLUDED.learning_velocity,
              time_spent_seconds = EXCLUDED.time_spent_seconds,
              revision_accuracy = EXCLUDED.revision_accuracy,
              last_interaction_at = now(),
              profile = EXCLUDED.profile,
              updated_at = now()
            RETURNING *
            """,
            (
                user_id,
                track_id,
                metrics["reading_progress"],
                metrics["overall_accuracy"],
                metrics["average_mastery"],
                metrics["confidence_score"],
                metrics["study_frequency_days"],
                metrics["preferred_difficulty"],
                metrics["learning_velocity"],
                metrics["time_spent_seconds"],
                metrics["revision_accuracy"],
                Jsonb(metrics.get("profile", {})),
            ),
        ).fetchone()
        return row

    def update_concept_mastery(self, conn, user_id: UUID, track: str, concept_id: UUID, delta: dict[str, Any]) -> dict:
        track_id = self.track_id(conn, track)
        row = conn.execute(
            """
            INSERT INTO student_concept_mastery (
              user_id, exam_track_id, concept_id, mastery_score, confidence_score,
              attempts, correct_attempts, incorrect_attempts, last_practiced_at, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now(), %s)
            ON CONFLICT (user_id, concept_id)
            DO UPDATE SET mastery_score = LEAST(100, GREATEST(0, student_concept_mastery.mastery_score + EXCLUDED.mastery_score)),
              confidence_score = LEAST(100, GREATEST(0, EXCLUDED.confidence_score)),
              attempts = student_concept_mastery.attempts + EXCLUDED.attempts,
              correct_attempts = student_concept_mastery.correct_attempts + EXCLUDED.correct_attempts,
              incorrect_attempts = student_concept_mastery.incorrect_attempts + EXCLUDED.incorrect_attempts,
              last_practiced_at = now(),
              metadata = student_concept_mastery.metadata || EXCLUDED.metadata,
              updated_at = now()
            RETURNING *
            """,
            (
                user_id,
                track_id,
                concept_id,
                delta["mastery_delta"],
                delta["confidence_score"],
                1,
                1 if delta["is_correct"] else 0,
                0 if delta["is_correct"] else 1,
                Jsonb(delta.get("metadata", {})),
            ),
        ).fetchone()
        return row

    def mastery_rows(self, conn, user_id: UUID, track: str) -> list[dict]:
        track_id = self.track_id(conn, track)
        return [dict(row) for row in conn.execute(
            """
            SELECT m.*, c.name AS concept_name, c.slug AS concept_slug
            FROM student_concept_mastery m
            JOIN learning_concepts c ON c.id = m.concept_id
            WHERE m.user_id = %s AND m.exam_track_id = %s
            ORDER BY m.mastery_score ASC
            """,
            (user_id, track_id),
        ).fetchall()]

    def schedule_spaced_item(self, conn, user_id: UUID, track: str, concept_id: UUID | None, official_question_id: UUID | None, ai_question_id: UUID | None, result: str) -> dict:
        track_id = self.track_id(conn, track)
        policy = conn.execute("SELECT * FROM spaced_repetition_policies WHERE is_active = true ORDER BY created_at DESC LIMIT 1").fetchone()
        row = conn.execute(
            """
            INSERT INTO spaced_repetition_items (
              user_id, exam_track_id, concept_id, official_question_id, ai_generated_question_id,
              policy_id, interval_index, due_at, last_result
            ) VALUES (%s, %s, %s, %s, %s, %s, 0, now() + interval '1 day', %s)
            RETURNING *
            """,
            (user_id, track_id, concept_id, official_question_id, ai_question_id, policy["id"] if policy else None, result),
        ).fetchone()
        return row

    def due_spaced_items(self, conn, user_id: UUID, track: str, limit: int = 50) -> list[dict]:
        track_id = self.track_id(conn, track)
        return [dict(row) for row in conn.execute(
            """
            SELECT s.*, c.name AS concept_name
            FROM spaced_repetition_items s
            LEFT JOIN learning_concepts c ON c.id = s.concept_id
            WHERE s.user_id = %s AND s.exam_track_id = %s AND s.status = 'due' AND s.due_at <= now()
            ORDER BY s.due_at ASC LIMIT %s
            """,
            (user_id, track_id, limit),
        ).fetchall()]

    def store_recommendation(self, conn, user_id: UUID, track: str, item: dict[str, Any]) -> dict:
        track_id = self.track_id(conn, track)
        return conn.execute(
            """
            INSERT INTO adaptive_recommendations (
              user_id, exam_track_id, recommendation_type, title, rationale, priority,
              target_entity_type, target_entity_id, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                user_id, track_id, item["type"], item["title"], item["rationale"], item["priority"],
                item.get("target_entity_type"), item.get("target_entity_id"), Jsonb(item.get("metadata", {}))
            ),
        ).fetchone()

    def store_prediction(self, conn, user_id: UUID, track: str, prediction: dict[str, Any]) -> dict:
        track_id = self.track_id(conn, track)
        return conn.execute(
            """
            INSERT INTO pass_predictions (user_id, exam_track_id, pass_probability, confidence, readiness_level, explainability)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (user_id, track_id, prediction["pass_probability"], prediction["confidence"], prediction["readiness_level"], Jsonb(prediction["explainability"])),
        ).fetchone()

    def store_readiness(self, conn, user_id: UUID, track: str, readiness: dict[str, Any]) -> dict:
        track_id = self.track_id(conn, track)
        return conn.execute(
            """
            INSERT INTO exam_readiness_snapshots (
              user_id, exam_track_id, readiness_score, coverage_score, mastery_score,
              mock_score, revision_score, consistency_score, blockers
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (user_id, track_id, readiness["readiness_score"], readiness["coverage_score"], readiness["mastery_score"], readiness["mock_score"], readiness["revision_score"], readiness["consistency_score"], Jsonb(readiness["blockers"])),
        ).fetchone()

    def profile_inputs(self, conn, user_id: UUID, track: str) -> dict[str, Any]:
        track_id = self.track_id(conn, track)
        reading = conn.execute("SELECT COALESCE(AVG(percent_complete),0) AS reading_progress, COALESCE(SUM(time_spent_seconds),0) AS reading_seconds FROM reading_progress WHERE user_id=%s AND exam_track_id=%s", (user_id, track_id)).fetchone()
        practice = conn.execute("SELECT COALESCE(AVG(score_percent),0) AS accuracy, COALESCE(SUM(duration_seconds),0) AS practice_seconds, COUNT(*) AS sessions FROM practice_sessions WHERE user_id=%s AND exam_track_id=%s AND status='submitted'", (user_id, track_id)).fetchone()
        mastery = conn.execute("SELECT COALESCE(AVG(mastery_score),0) AS average_mastery, COALESCE(AVG(confidence_score),50) AS confidence FROM student_concept_mastery WHERE user_id=%s AND exam_track_id=%s", (user_id, track_id)).fetchone()
        revision = conn.execute("SELECT COUNT(*) FILTER (WHERE status='completed') AS completed, COUNT(*) AS total FROM spaced_repetition_items WHERE user_id=%s AND exam_track_id=%s", (user_id, track_id)).fetchone()
        activity = conn.execute("SELECT COUNT(DISTINCT created_at::date) AS active_days FROM study_activity_events WHERE user_id=%s AND exam_track_id=%s AND created_at >= now() - interval '30 days'", (user_id, track_id)).fetchone()
        return {"reading": dict(reading), "practice": dict(practice), "mastery": dict(mastery), "revision": dict(revision), "activity": dict(activity)}
