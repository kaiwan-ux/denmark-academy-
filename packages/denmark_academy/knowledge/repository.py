from hashlib import sha256
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from denmark_academy.config import get_settings
from denmark_academy.knowledge.schemas import ApprovalDecisionRequest, KnowledgeSourceCreate, NotificationCreate, QualityValidationResult, SchedulerJobCreate


class KnowledgeRepository:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.database_url = self.settings.database_url

    def connection(self):
        return psycopg.connect(
            self.database_url,
            row_factory=dict_row,
            connect_timeout=self.settings.database_connect_timeout_seconds,
        )

    def track_id(self, conn, track: str | None) -> UUID | None:
        if track is None:
            return None
        row = conn.execute('SELECT id FROM exam_tracks WHERE slug = %s', (track,)).fetchone()
        if not row:
            raise ValueError(f'Unknown exam track: {track}')
        return row['id']

    def create_source(self, conn, payload: KnowledgeSourceCreate) -> dict:
        row = conn.execute(
            """
            INSERT INTO knowledge_sources (
              exam_track_id, source_key, name, source_type, base_url, config,
              trust_level, collection_frequency_minutes, is_active
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_key) DO UPDATE SET name = EXCLUDED.name, base_url = EXCLUDED.base_url,
              config = EXCLUDED.config, trust_level = EXCLUDED.trust_level,
              collection_frequency_minutes = EXCLUDED.collection_frequency_minutes,
              is_active = EXCLUDED.is_active, updated_at = now()
            RETURNING *
            """,
            (self.track_id(conn, payload.track), payload.source_key, payload.name, payload.source_type, payload.base_url, Jsonb(payload.config), payload.trust_level, payload.collection_frequency_minutes, payload.is_active),
        ).fetchone()
        return dict(row)

    def list_sources(self, conn) -> list[dict]:
        return [dict(row) for row in conn.execute('SELECT * FROM knowledge_sources ORDER BY name').fetchall()]

    def create_collection_run(self, conn, source_id: UUID) -> dict:
        return dict(conn.execute(
            "INSERT INTO content_collection_runs (knowledge_source_id, status, started_at) VALUES (%s, 'running', now()) RETURNING *",
            (source_id,),
        ).fetchone())

    def complete_collection_run(self, conn, run_id: UUID, status: str, report: dict[str, Any]) -> dict:
        return dict(conn.execute(
            """
            UPDATE content_collection_runs
            SET status=%s, completed_at=now(), discovered_count=%s, stored_count=%s,
              skipped_count=%s, error_message=%s, report=%s
            WHERE id=%s RETURNING *
            """,
            (status, report.get('discovered_count', 0), report.get('stored_count', 0), report.get('skipped_count', 0), report.get('error_message'), Jsonb(report), run_id),
        ).fetchone())

    def upsert_document_version(self, conn, *, source_id: UUID, run_id: UUID | None, track: str | None, canonical_url: str | None, title: str, document_type: str, raw_text: str, language: str, metadata: dict[str, Any]) -> dict:
        track_id = self.track_id(conn, track)
        document = conn.execute(
            """
            INSERT INTO collected_documents (knowledge_source_id, exam_track_id, canonical_url, title, document_type, language, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (source_id, track_id, canonical_url, title, document_type, language, Jsonb(metadata)),
        ).fetchone()
        content_hash = sha256(raw_text.encode('utf-8')).hexdigest()
        version = conn.execute(
            """
            INSERT INTO document_versions_automation (
              collected_document_id, collection_run_id, version_number, content_sha256, extracted_text, trace
            ) VALUES (%s, %s, 1, %s, %s, %s)
            RETURNING *
            """,
            (document['id'], run_id, content_hash, raw_text, Jsonb({'source_id': str(source_id), 'canonical_url': canonical_url})),
        ).fetchone()
        conn.execute('UPDATE collected_documents SET latest_version_id = %s WHERE id = %s', (version['id'], document['id']))
        result = dict(version)
        result['document'] = dict(document)
        return result

    def create_processing_job(self, conn, version_id: UUID, job_type: str) -> dict:
        return dict(conn.execute(
            'INSERT INTO document_processing_jobs (document_version_id, job_type) VALUES (%s, %s) RETURNING *',
            (version_id, job_type),
        ).fetchone())

    def store_metadata(self, conn, version_id: UUID, track: str | None, metadata: dict[str, Any]) -> dict:
        return dict(conn.execute(
            """
            INSERT INTO content_metadata_intelligence (
              document_version_id, exam_track_id, detected_topics, detected_concepts,
              relevance_score, audience_level, difficulty, current_affairs_category
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (document_version_id)
            DO UPDATE SET detected_topics=EXCLUDED.detected_topics, detected_concepts=EXCLUDED.detected_concepts,
              relevance_score=EXCLUDED.relevance_score, audience_level=EXCLUDED.audience_level,
              difficulty=EXCLUDED.difficulty, current_affairs_category=EXCLUDED.current_affairs_category
            RETURNING *
            """,
            (version_id, self.track_id(conn, track), Jsonb(metadata['topics']), Jsonb(metadata['concepts']), metadata['relevance_score'], metadata.get('audience_level'), metadata.get('difficulty'), metadata.get('current_affairs_category')),
        ).fetchone())

    def store_quality_validation(self, conn, track: str | None, entity_type: str, entity_id: UUID, result: QualityValidationResult) -> dict:
        return dict(conn.execute(
            """
            INSERT INTO content_quality_validations (
              exam_track_id, entity_type, entity_id, extraction_quality, metadata_quality,
              relevance_score, duplication_risk, traceability_score, overall_score, decision, findings
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (self.track_id(conn, track), entity_type, entity_id, result.extraction_quality, result.metadata_quality, result.relevance_score, result.duplication_risk, result.traceability_score, result.overall_score, result.decision, Jsonb(result.findings)),
        ).fetchone())

    def create_current_affairs_item(self, conn, track: str, version_id: UUID, title: str, summary: str, relevance: float, category: str | None, trace: dict[str, Any]) -> dict:
        return dict(conn.execute(
            """
            INSERT INTO current_affairs_items (exam_track_id, document_version_id, title, summary, relevance_score, category, status, trace)
            VALUES (%s, %s, %s, %s, %s, %s, 'needs_review', %s) RETURNING *
            """,
            (self.track_id(conn, track), version_id, title, summary, relevance, category, Jsonb(trace)),
        ).fetchone())

    def create_generated_resource(self, conn, track: str, current_affairs_item_id: UUID | None, version_id: UUID | None, resource_type: str, title: str, content: dict[str, Any], trace: dict[str, Any]) -> dict:
        return dict(conn.execute(
            """
            INSERT INTO generated_content_resources (exam_track_id, current_affairs_item_id, document_version_id, resource_type, title, content, status, trace)
            VALUES (%s, %s, %s, %s, %s, %s, 'needs_review', %s) RETURNING *
            """,
            (self.track_id(conn, track), current_affairs_item_id, version_id, resource_type, title, Jsonb(content), Jsonb(trace)),
        ).fetchone())

    def submit_approval(self, conn, track: str | None, entity_type: str, entity_id: UUID, metadata: dict[str, Any] | None = None) -> dict:
        return dict(conn.execute(
            """
            INSERT INTO content_approval_workflows (exam_track_id, entity_type, entity_id, metadata)
            VALUES (%s, %s, %s, %s) RETURNING *
            """,
            (self.track_id(conn, track), entity_type, entity_id, Jsonb(metadata or {})),
        ).fetchone())

    def decide_approval(self, conn, payload: ApprovalDecisionRequest) -> dict:
        row = conn.execute(
            """
            UPDATE content_approval_workflows
            SET status=%s, reviewer_user_id=%s, review_note=%s, reviewed_at=now()
            WHERE entity_type=%s AND entity_id=%s AND status='pending'
            RETURNING *
            """,
            (payload.decision, payload.reviewer_user_id, payload.review_note, payload.entity_type, payload.entity_id),
        ).fetchone()
        if payload.entity_type == 'generated_resource':
            mapped = 'approved' if payload.decision == 'approved' else 'rejected'
            conn.execute('UPDATE generated_content_resources SET status=%s, reviewed_at=now(), reviewed_by_user_id=%s WHERE id=%s', (mapped, payload.reviewer_user_id, payload.entity_id))
        if payload.entity_type == 'current_affairs_item':
            mapped = 'approved' if payload.decision == 'approved' else 'rejected'
            conn.execute('UPDATE current_affairs_items SET status=%s WHERE id=%s', (mapped, payload.entity_id))
        return dict(row) if row else {}

    def create_notification(self, conn, payload: NotificationCreate) -> dict:
        return dict(conn.execute(
            """
            INSERT INTO content_notifications (recipient_user_id, channel, notification_type, title, body, entity_type, entity_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *
            """,
            (payload.recipient_user_id, payload.channel, payload.notification_type, payload.title, payload.body, payload.entity_type, payload.entity_id),
        ).fetchone())

    def create_scheduler_job(self, conn, payload: SchedulerJobCreate) -> dict:
        return dict(conn.execute(
            """
            INSERT INTO background_scheduler_jobs (job_key, job_type, schedule_cron, interval_minutes, payload, is_enabled)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (job_key) DO UPDATE SET job_type=EXCLUDED.job_type, schedule_cron=EXCLUDED.schedule_cron,
              interval_minutes=EXCLUDED.interval_minutes, payload=EXCLUDED.payload, is_enabled=EXCLUDED.is_enabled, updated_at=now()
            RETURNING *
            """,
            (payload.job_key, payload.job_type, payload.schedule_cron, payload.interval_minutes, Jsonb(payload.payload), payload.is_enabled),
        ).fetchone())

    def analytics(self, conn) -> dict:
        row = conn.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM knowledge_sources) AS source_count,
              (SELECT COUNT(*) FROM collected_documents) AS documents_collected,
              (SELECT COUNT(*) FROM document_versions_automation WHERE processing_status='processed') AS documents_processed,
              (SELECT COUNT(*) FROM duplicate_detection_items) AS duplicates_found,
              (SELECT COUNT(*) FROM content_approval_workflows WHERE status='pending') AS approvals_pending,
              (SELECT COUNT(*) FROM generated_content_resources) AS generated_resources,
              (SELECT COALESCE(AVG(overall_score),0) FROM content_quality_validations) AS average_quality_score
            """
        ).fetchone()
        return dict(row)
