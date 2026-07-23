import argparse
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from denmark_academy.config import get_settings
from denmark_academy.retrieval.qdrant import QdrantRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate AI explanation drafts requiring admin approval.")
    parser.add_argument("official_question_id", type=UUID)
    parser.add_argument("--model-provider", default="placeholder")
    parser.add_argument("--model-name", default="phase1-template")
    parser.add_argument("--prompt-version", default="explanation-v1")
    args = parser.parse_args()

    draft = create_placeholder_draft(
        args.official_question_id,
        model_provider=args.model_provider,
        model_name=args.model_name,
        prompt_version=args.prompt_version,
    )
    print(draft)


def create_placeholder_draft(
    official_question_id: UUID,
    *,
    model_provider: str,
    model_name: str,
    prompt_version: str,
) -> dict:
    settings = get_settings()
    with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
        question = conn.execute(
            """
            SELECT q.*, et.slug AS track
            FROM official_questions q
            JOIN exam_tracks et ON et.id = q.exam_track_id
            WHERE q.id = %s
            """,
            (official_question_id,),
        ).fetchone()
        if question is None:
            raise ValueError(f"Official question not found: {official_question_id}")

        retrieval_hits = QdrantRepository().search(
            query=question["stem"],
            track_slug=question["track"],
            collections=["learning_chunks", "official_questions"],
            limit=5,
        )
        correct_text = question[f"choice_{question['correct_choice'].lower()}"]
        generated_text = (
            "Draft explanation pending human review. "
            f"The official correct answer is {question['correct_choice']}: {correct_text}. "
            "Use the attached retrieval snapshot to write a source-grounded explanation."
        )
        draft = conn.execute(
            """
            INSERT INTO ai_explanation_drafts (
              official_question_id, generated_text, model_provider, model_name,
              prompt_version, retrieval_snapshot
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                official_question_id,
                generated_text,
                model_provider,
                model_name,
                prompt_version,
                Jsonb({"hits": [hit.model_dump(mode="json") for hit in retrieval_hits]}),
            ),
        ).fetchone()
        conn.commit()
    return dict(draft)


if __name__ == "__main__":
    main()

