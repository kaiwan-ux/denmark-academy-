from pathlib import Path
from typing import Any

from denmark_academy.config import get_settings
from denmark_academy.domain import ParsedAnswerKey, SourceType
from denmark_academy.ingestion.chunking import chunk_pages
from denmark_academy.ingestion.manifest import build_ingestion_manifest
from denmark_academy.ingestion.parsers import (
    combine_questions_and_answers,
    parse_answer_key_pdf,
    parse_question_pdf,
)
from denmark_academy.ingestion.pdf import extract_pdf_pages
from denmark_academy.ingestion.validation import validate_question_answer_pair
from denmark_academy.storage.local import LocalObjectStorage


class IngestionPipeline:
    def __init__(
        self,
        *,
        repository: Any | None = None,
        qdrant: Any | None = None,
        storage: LocalObjectStorage | None = None,
    ) -> None:
        self.settings = get_settings()
        self.repository = repository
        self.qdrant = qdrant
        self.storage = storage or LocalObjectStorage()

    def dry_run(self, root_path: Path) -> dict[str, Any]:
        manifest = build_ingestion_manifest(root_path, self.settings.parser_version)
        reports = []
        for pair in manifest.paper_pairs:
            question_path = root_path / pair.question_pdf.source_path
            answer_count = 0
            validation = None
            if pair.answer_pdf:
                answer_key = parse_answer_key_pdf(root_path / pair.answer_pdf.source_path)
                questions = parse_question_pdf(question_path, expected_numbers=sorted(answer_key.answers))
                answer_count = len(answer_key.answers)
                validation = validate_question_answer_pair(questions, answer_key)
            else:
                questions = parse_question_pdf(question_path)
            reports.append(
                {
                    "track": pair.track.value,
                    "paper_code": pair.paper_code,
                    "question_count": len(questions),
                    "answer_count": answer_count,
                    "validation": validation.model_dump(mode="json") if validation else None,
                    "warnings": pair.validation_warnings,
                }
            )
        return {
            "manifest": manifest.model_dump(mode="json"),
            "paper_reports": reports,
        }

    def run(self, root_path: Path, *, upsert_qdrant: bool = True) -> dict[str, Any]:
        from denmark_academy.db.repository import Phase1Repository
        from denmark_academy.retrieval.qdrant import QdrantRepository

        manifest = build_ingestion_manifest(root_path, self.settings.parser_version)
        self.repository = self.repository or Phase1Repository()
        qdrant = self.qdrant or QdrantRepository()
        if upsert_qdrant:
            qdrant.ensure_collections()

        report: dict[str, Any] = {
            "learning_materials": [],
            "papers": [],
            "warnings": manifest.warnings,
        }

        with self.repository.connection() as conn:
            run_id = self.repository.create_ingestion_run(
                conn,
                root_path=root_path,
                parser_version=self.settings.parser_version,
                manifest=manifest.model_dump(mode="json"),
            )
            try:
                for source in manifest.learning_materials:
                    source_path = root_path / source.source_path
                    pages = extract_pdf_pages(source_path)
                    storage_uri = self.storage.put_file(
                        source_path,
                        f"{source.track.value}/{SourceType.LEARNING_MATERIAL.value}/{source.content_sha256}.pdf",
                    )
                    source_document_id = self.repository.upsert_source_document(
                        conn,
                        manifest=source,
                        storage_uri=storage_uri,
                        page_count=len(pages),
                    )
                    self.repository.replace_document_pages(
                        conn,
                        source_document_id=source_document_id,
                        pages=pages,
                    )
                    chunks = chunk_pages(pages)
                    point_ids = (
                        qdrant.upsert_learning_chunks(
                            track_slug=source.track.value,
                            source_document_id=source_document_id,
                            source_document_sha256=source.content_sha256,
                            title=source.original_filename,
                            chunks=chunks,
                            parser_version=source.parser_version,
                        )
                        if upsert_qdrant
                        else []
                    )
                    self.repository.replace_document_chunks(
                        conn,
                        source_document_id=source_document_id,
                        chunks=chunks,
                        qdrant_point_ids=point_ids,
                    )
                    report["learning_materials"].append(
                        {
                            "track": source.track.value,
                            "source_path": source.source_path,
                            "pages": len(pages),
                            "chunks": len(chunks),
                        }
                    )

                for pair in manifest.paper_pairs:
                    question_path = root_path / pair.question_pdf.source_path
                    answer_path = root_path / pair.answer_pdf.source_path if pair.answer_pdf else None
                    question_pages = extract_pdf_pages(question_path)
                    question_storage_uri = self.storage.put_file(
                        question_path,
                        f"{pair.track.value}/question_paper/{pair.question_pdf.content_sha256}.pdf",
                    )
                    question_document_id = self.repository.upsert_source_document(
                        conn,
                        manifest=pair.question_pdf,
                        storage_uri=question_storage_uri,
                        page_count=len(question_pages),
                    )
                    self.repository.replace_document_pages(
                        conn,
                        source_document_id=question_document_id,
                        pages=question_pages,
                    )

                    answer_document_id = None
                    if pair.answer_pdf and answer_path:
                        answer_pages = extract_pdf_pages(answer_path)
                        answer_storage_uri = self.storage.put_file(
                            answer_path,
                            f"{pair.track.value}/answer_key/{pair.answer_pdf.content_sha256}.pdf",
                        )
                        answer_document_id = self.repository.upsert_source_document(
                            conn,
                            manifest=pair.answer_pdf,
                            storage_uri=answer_storage_uri,
                            page_count=len(answer_pages),
                        )
                        self.repository.replace_document_pages(
                            conn,
                            source_document_id=answer_document_id,
                            pages=answer_pages,
                        )

                    answer_key = parse_answer_key_pdf(answer_path) if answer_path else None
                    questions = parse_question_pdf(
                        question_path, expected_numbers=sorted(answer_key.answers) if answer_key else None
                    )
                    if answer_key:
                        validation = validate_question_answer_pair(questions, answer_key)
                        official_questions = (
                            combine_questions_and_answers(questions, answer_key)
                            if validation.status == "valid"
                            else []
                        )
                        existing_hashes = self.repository.existing_official_question_hashes(
                            conn, [question.content_sha256 for question in official_questions]
                        )
                        official_questions = [
                            question for question in official_questions if question.content_sha256 not in existing_hashes
                        ]
                    else:
                        validation = validate_question_answer_pair(questions, ParsedAnswerKey(answers={}))
                        official_questions = []

                    paper_id = self.repository.upsert_official_paper(
                        conn,
                        track=pair.track,
                        paper_code=pair.paper_code,
                        question_document_id=question_document_id,
                        answer_document_id=answer_document_id,
                        title=f"{pair.track.value} paper {pair.paper_code}",
                        expected_question_count=None,
                        parser_version=self.settings.parser_version,
                        validation_report=validation,
                    )
                    point_ids_by_number = (
                        qdrant.upsert_official_questions(
                            track_slug=pair.track.value,
                            official_exam_paper_id=paper_id,
                            questions=official_questions,
                        )
                        if upsert_qdrant and official_questions
                        else {}
                    )
                    inserted = self.repository.insert_official_questions(
                        conn,
                        track=pair.track,
                        official_exam_paper_id=paper_id,
                        questions=official_questions,
                        qdrant_point_ids_by_number=point_ids_by_number,
                    )
                    report["papers"].append(
                        {
                            "track": pair.track.value,
                            "paper_code": pair.paper_code,
                            "questions": len(questions),
                            "official_questions_inserted": inserted,
                            "immutable_write_skipped": validation.status != "valid",
                            "validation": validation.model_dump(mode="json"),
                        }
                    )

                status = "completed"
                if any(item["validation"]["status"] != "valid" for item in report["papers"]):
                    status = "needs_review"
                self.repository.update_ingestion_run(conn, run_id=run_id, status=status, report=report)
                conn.commit()
            except Exception as exc:
                conn.rollback()
                with self.repository.connection() as failed_conn:
                    self.repository.update_ingestion_run(
                        failed_conn,
                        run_id=run_id,
                        status="failed",
                        report={"error": str(exc), **report},
                    )
                    failed_conn.commit()
                raise

        return {"run_id": str(run_id), "status": status, "report": report}





