from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

import psycopg
from psycopg.rows import dict_row
from qdrant_client.http import models

from denmark_academy.config import get_settings
from denmark_academy.retrieval.embeddings import DeterministicEmbeddingProvider
from denmark_academy.retrieval.qdrant import ANSWER_COLLECTION, QUESTION_COLLECTION, QdrantRepository


def sync_official_questions_and_answers() -> dict[str, int]:
    settings = get_settings()
    qdrant = QdrantRepository()
    qdrant.ensure_collections()
    embeddings = DeterministicEmbeddingProvider(settings.embedding_dimension)

    with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
        rows = conn.execute(
            """
            SELECT q.*, et.slug AS track_slug, p.paper_code
            FROM official_questions q
            JOIN exam_tracks et ON et.id = q.exam_track_id
            JOIN official_exam_papers p ON p.id = q.official_exam_paper_id
            ORDER BY et.slug, p.paper_code, q.question_number
            """
        ).fetchall()

    question_points: list[models.PointStruct] = []
    answer_points: list[models.PointStruct] = []
    for row in rows:
        choices = {
            "A": row.get("choice_a") or "",
            "B": row.get("choice_b") or "",
            "C": row.get("choice_c") or "",
        }
        if row.get("choice_d"):
            choices["D"] = row["choice_d"]
        correct_choice = str(row.get("correct_choice") or "A").upper()
        correct_answer_text = choices.get(correct_choice, "")
        question_text = (
            f"{row['stem']}\n"
            + "\n".join(f"{key}: {value}" for key, value in choices.items())
            + f"\nCorrect: {correct_choice}: {correct_answer_text}"
        )
        question_id = row.get("qdrant_point_id") or str(row["id"])
        answer_id = uuid5(NAMESPACE_URL, f"answer:{row['id']}:{correct_choice}:{correct_answer_text}")
        base_payload = {
            "exam_track_slug": row["track_slug"],
            "official_question_id": str(row["id"]),
            "official_exam_paper_id": str(row["official_exam_paper_id"]),
            "paper_code": row.get("paper_code"),
            "question_number": row.get("question_number"),
            "language": "da",
        }
        question_points.append(
            models.PointStruct(
                id=str(question_id),
                vector=embeddings.embed(question_text),
                payload={
                    **base_payload,
                    "object_type": "official_question",
                    "stem": row.get("stem") or "",
                    "choices": choices,
                    "correct_choice": correct_choice,
                    "correct_answer_text": correct_answer_text,
                    "source_page_start": row.get("source_page_start"),
                    "source_page_end": row.get("source_page_end"),
                    "immutable_version": row.get("immutable_version") or 1,
                    "content_sha256": row.get("content_sha256"),
                },
            )
        )
        answer_points.append(
            models.PointStruct(
                id=str(answer_id),
                vector=embeddings.embed(f"{row['stem']}\nAnswer: {correct_choice}: {correct_answer_text}"),
                payload={
                    **base_payload,
                    "object_type": "official_answer",
                    "correct_choice": correct_choice,
                    "correct_answer_text": correct_answer_text,
                },
            )
        )

    if question_points:
        qdrant.client.upsert(collection_name=QUESTION_COLLECTION, points=question_points)
    if answer_points:
        qdrant.client.upsert(collection_name=ANSWER_COLLECTION, points=answer_points)
    return {"official_questions": len(question_points), "official_answers": len(answer_points)}


if __name__ == "__main__":
    print(sync_official_questions_and_answers())
