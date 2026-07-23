from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from denmark_academy.config import get_settings
from denmark_academy.domain import (
    ChoiceLetter,
    ExamTrackSlug,
    ParsedOfficialQuestion,
    SourceDocumentManifest,
    SourceType,
    ValidationReport,
)
from denmark_academy.ingestion.chunking import TextChunk
from denmark_academy.ingestion.pdf import ExtractedPage


class Phase1Repository:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.database_url = self.settings.database_url

    def connection(self):
        return psycopg.connect(
            self.database_url,
            row_factory=dict_row,
            connect_timeout=self.settings.database_connect_timeout_seconds,
        )

    def get_track_id(self, conn, track_slug: ExamTrackSlug) -> UUID:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM exam_tracks WHERE slug = %s", (track_slug.value,))
            row = cur.fetchone()
        if row is None:
            raise ValueError(f"Unknown exam track: {track_slug.value}")
        return row["id"]

    def upsert_source_document(
        self,
        conn,
        *,
        manifest: SourceDocumentManifest,
        storage_uri: str,
        page_count: int | None = None,
        metadata: dict[str, Any] | None = None,
        status: str = "validated",
    ) -> UUID:
        track_id = self.get_track_id(conn, manifest.track)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO source_documents (
                  exam_track_id, source_type, original_filename, source_path, storage_uri,
                  content_sha256, file_size_bytes, page_count, ingestion_status,
                  parser_version, metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (exam_track_id, source_type, content_sha256)
                DO UPDATE SET
                  storage_uri = EXCLUDED.storage_uri,
                  page_count = EXCLUDED.page_count,
                  ingestion_status = EXCLUDED.ingestion_status,
                  metadata = source_documents.metadata || EXCLUDED.metadata
                RETURNING id
                """,
                (
                    track_id,
                    manifest.source_type.value,
                    manifest.original_filename,
                    manifest.source_path,
                    storage_uri,
                    manifest.content_sha256,
                    manifest.file_size_bytes,
                    page_count,
                    status,
                    manifest.parser_version,
                    Jsonb(metadata or manifest.metadata),
                ),
            )
            return cur.fetchone()["id"]

    def replace_document_pages(
        self,
        conn,
        *,
        source_document_id: UUID,
        pages: list[ExtractedPage],
    ) -> None:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM document_pages WHERE source_document_id = %s", (source_document_id,))
            cur.executemany(
                """
                INSERT INTO document_pages (
                  source_document_id, page_number, extracted_text,
                  extraction_method, extraction_confidence
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                [
                    (
                        source_document_id,
                        page.page_number,
                        page.text,
                        page.extraction_method,
                        page.extraction_confidence,
                    )
                    for page in pages
                ],
            )

    def replace_document_chunks(
        self,
        conn,
        *,
        source_document_id: UUID,
        chunks: list[TextChunk],
        qdrant_point_ids: list[UUID] | None = None,
    ) -> None:
        qdrant_point_ids = qdrant_point_ids or []
        with conn.cursor() as cur:
            cur.execute("DELETE FROM document_chunks WHERE source_document_id = %s", (source_document_id,))
            cur.executemany(
                """
                INSERT INTO document_chunks (
                  source_document_id, page_start, page_end, section_title, chunk_index,
                  text, token_count, qdrant_point_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        source_document_id,
                        chunk.page_start,
                        chunk.page_end,
                        chunk.section_title,
                        chunk.chunk_index,
                        chunk.text,
                        chunk.token_count,
                        qdrant_point_ids[index] if index < len(qdrant_point_ids) else None,
                    )
                    for index, chunk in enumerate(chunks)
                ],
            )

    def upsert_official_paper(
        self,
        conn,
        *,
        track: ExamTrackSlug,
        paper_code: str,
        question_document_id: UUID,
        answer_document_id: UUID | None,
        title: str,
        expected_question_count: int | None,
        parser_version: str,
        validation_report: ValidationReport,
    ) -> UUID:
        track_id = self.get_track_id(conn, track)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO official_exam_papers (
                  exam_track_id, question_document_id, answer_document_id, paper_code, title,
                  expected_question_count, parser_version, validation_status, validation_report
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (exam_track_id, paper_code)
                DO UPDATE SET
                  question_document_id = EXCLUDED.question_document_id,
                  answer_document_id = EXCLUDED.answer_document_id,
                  validation_status = EXCLUDED.validation_status,
                  validation_report = EXCLUDED.validation_report
                RETURNING id
                """,
                (
                    track_id,
                    question_document_id,
                    answer_document_id,
                    paper_code,
                    title,
                    expected_question_count,
                    parser_version,
                    validation_report.status,
                    Jsonb(validation_report.model_dump(mode="json")),
                ),
            )
            return cur.fetchone()["id"]


    def existing_official_question_hashes(self, conn, hashes: list[str]) -> set[str]:
        if not hashes:
            return set()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT content_sha256 FROM official_questions WHERE content_sha256 = ANY(%s)",
                (hashes,),
            )
            return {row["content_sha256"] for row in cur.fetchall()}
    def insert_official_questions(
        self,
        conn,
        *,
        track: ExamTrackSlug,
        official_exam_paper_id: UUID,
        questions: list[ParsedOfficialQuestion],
        qdrant_point_ids_by_number: dict[int, UUID] | None = None,
    ) -> int:
        track_id = self.get_track_id(conn, track)
        qdrant_point_ids_by_number = qdrant_point_ids_by_number or {}
        inserted = 0
        with conn.cursor() as cur:
            for question in questions:
                choice_a = _choice(question, ChoiceLetter.A)
                choice_b = _choice(question, ChoiceLetter.B)
                choice_c = _choice(question, ChoiceLetter.C)
                cur.execute(
                    """
                    INSERT INTO official_questions (
                      exam_track_id, official_exam_paper_id, question_number, stem,
                      choice_a, choice_b, choice_c, correct_choice, source_page_start,
                      source_page_end, qdrant_point_id, content_sha256, metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (content_sha256) DO NOTHING
                    """,
                    (
                        track_id,
                        official_exam_paper_id,
                        question.question_number,
                        question.stem,
                        choice_a,
                        choice_b,
                        choice_c,
                        question.correct_choice.value,
                        question.source_page_start,
                        question.source_page_end,
                        qdrant_point_ids_by_number.get(question.question_number),
                        question.content_sha256,
                        Jsonb({"parser": "pdf-question-parser"}),
                    ),
                )
                inserted += cur.rowcount
        return inserted

    def create_ingestion_run(
        self,
        conn,
        *,
        root_path: Path,
        parser_version: str,
        manifest: dict[str, Any],
    ) -> UUID:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ingestion_runs (root_path, parser_version, manifest)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (str(root_path), parser_version, Jsonb(manifest)),
            )
            return cur.fetchone()["id"]

    def update_ingestion_run(self, conn, *, run_id: UUID, status: str, report: dict[str, Any]) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ingestion_runs
                SET status = %s,
                    report = %s,
                    completed_at = CASE WHEN %s IN ('completed', 'failed', 'needs_review') THEN now() ELSE completed_at END,
                    started_at = COALESCE(started_at, now())
                WHERE id = %s
                """,
                (status, Jsonb(report), status, run_id),
            )



def _choice(question: ParsedOfficialQuestion, letter: ChoiceLetter) -> str | None:
    return question.choices.get(letter) or question.choices.get(letter.value)


