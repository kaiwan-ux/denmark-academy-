from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from denmark_academy.ai.schemas import EvaluationResult, RetrievedSource
from denmark_academy.config import get_settings


class AIRepository:
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

    def active_template(self, conn, template_key: str) -> dict | None:
        return conn.execute(
            "SELECT * FROM ai_prompt_templates WHERE template_key = %s AND status = 'active' ORDER BY version DESC LIMIT 1",
            (template_key,),
        ).fetchone()

    def create_retrieval_snapshot(self, conn, track: str, query: str, filters: dict[str, Any], sources: list[RetrievedSource]) -> UUID:
        track_id = self.track_id(conn, track)
        row = conn.execute(
            """
            INSERT INTO ai_retrieval_snapshots (exam_track_id, query, filters, sources)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (track_id, query, Jsonb(filters), Jsonb([source.model_dump(mode="json") for source in sources])),
        ).fetchone()
        return row["id"]

    def create_prompt_run(
        self,
        conn,
        *,
        track: str,
        user_id: UUID | None,
        template_id: UUID | None,
        retrieval_snapshot_id: UUID | None,
        provider_key: str,
        model: str,
        purpose: str,
        messages: list[dict[str, Any]],
        response_payload: dict[str, Any],
        token_usage: dict[str, Any],
        cache_hit: bool,
    ) -> UUID:
        track_id = self.track_id(conn, track)
        row = conn.execute(
            """
            INSERT INTO ai_prompt_runs (
              exam_track_id, user_id, prompt_template_id, retrieval_snapshot_id, provider_key, model,
              purpose, prompt_messages, response_payload, token_usage, cache_hit
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                track_id,
                user_id,
                template_id,
                retrieval_snapshot_id,
                provider_key,
                model,
                purpose,
                Jsonb(messages),
                Jsonb(response_payload),
                Jsonb(token_usage),
                cache_hit,
            ),
        ).fetchone()
        return row["id"]

    def create_artifact(
        self,
        conn,
        *,
        track: str,
        user_id: UUID | None,
        artifact_type: str,
        source_entity_type: str | None,
        source_entity_id: UUID | None,
        prompt_run_id: UUID | None,
        title: str | None,
        content: dict[str, Any],
        status: str,
        quality_score: float | None,
        metadata: dict[str, Any],
    ) -> UUID:
        track_id = self.track_id(conn, track)
        row = conn.execute(
            """
            INSERT INTO ai_content_artifacts (
              exam_track_id, user_id, artifact_type, source_entity_type, source_entity_id,
              prompt_run_id, title, content, status, quality_score, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                track_id,
                user_id,
                artifact_type,
                source_entity_type,
                source_entity_id,
                prompt_run_id,
                title,
                Jsonb(content),
                status,
                quality_score,
                Jsonb(metadata),
            ),
        ).fetchone()
        return row["id"]

    def create_evaluation(
        self,
        conn,
        *,
        track: str,
        artifact_id: UUID | None,
        ai_generated_question_id: UUID | None,
        result: EvaluationResult,
        evaluator_version: str,
    ) -> UUID:
        track_id = self.track_id(conn, track)
        row = conn.execute(
            """
            INSERT INTO ai_evaluations (
              exam_track_id, artifact_id, ai_generated_question_id, evaluator_version,
              groundedness_score, exam_alignment_score, hallucination_risk,
              duplication_score, quality_score, decision, findings
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                track_id,
                artifact_id,
                ai_generated_question_id,
                evaluator_version,
                result.groundedness_score,
                result.exam_alignment_score,
                result.hallucination_risk,
                result.duplication_score,
                result.quality_score,
                result.decision,
                Jsonb(result.findings),
            ),
        ).fetchone()
        return row["id"]

    def official_similarity_texts(self, conn, track: str, limit: int = 100) -> list[str]:
        track_id = self.track_id(conn, track)
        rows = conn.execute(
            "SELECT stem FROM official_questions WHERE exam_track_id = %s ORDER BY created_at DESC LIMIT %s",
            (track_id, limit),
        ).fetchall()
        return [row["stem"] for row in rows]
