from collections.abc import Iterable
from uuid import UUID, uuid5, NAMESPACE_URL

from qdrant_client import QdrantClient
from qdrant_client.http import models

from denmark_academy.config import get_settings
from denmark_academy.domain import ParsedOfficialQuestion, RetrievalHit
from denmark_academy.ingestion.chunking import TextChunk
from denmark_academy.retrieval.embeddings import DeterministicEmbeddingProvider

LEARNING_COLLECTION = "da_learning_chunks"
QUESTION_COLLECTION = "da_official_questions"
ANSWER_COLLECTION = "da_official_answers"
EXPLANATION_COLLECTION = "da_explanations"


class QdrantRepository:
    def __init__(self) -> None:
        settings = get_settings()
        # Initialize QdrantClient with API key for cloud clusters
        client_params = {"url": settings.qdrant_url}
        if settings.qdrant_api_key:
            client_params["api_key"] = settings.qdrant_api_key.get_secret_value()
        self.client = QdrantClient(**client_params)
        self.embeddings = DeterministicEmbeddingProvider(settings.embedding_dimension)
        self.dimension = settings.embedding_dimension

    def ensure_collections(self) -> None:
        for collection in [
            LEARNING_COLLECTION,
            QUESTION_COLLECTION,
            ANSWER_COLLECTION,
            EXPLANATION_COLLECTION,
        ]:
            if not self.client.collection_exists(collection):
                self.client.create_collection(
                    collection_name=collection,
                    vectors_config=models.VectorParams(
                        size=self.dimension,
                        distance=models.Distance.COSINE,
                    ),
                )
                self.client.create_payload_index(
                    collection_name=collection,
                    field_name="exam_track_slug",
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
                self.client.create_payload_index(
                    collection_name=collection,
                    field_name="object_type",
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )

    def upsert_learning_chunks(
        self,
        *,
        track_slug: str,
        source_document_id: UUID,
        source_document_sha256: str,
        title: str,
        chunks: Iterable[TextChunk],
        parser_version: str,
    ) -> list[UUID]:
        point_ids: list[UUID] = []
        points: list[models.PointStruct] = []
        for chunk in chunks:
            point_id = uuid5(
                NAMESPACE_URL, f"learning:{source_document_id}:{chunk.chunk_index}:{source_document_sha256}"
            )
            point_ids.append(point_id)
            payload = {
                "object_type": "learning_chunk",
                "exam_track_slug": track_slug,
                "source_document_id": str(source_document_id),
                "source_document_sha256": source_document_sha256,
                "source_type": "learning_material",
                "title": title,
                "section_title": chunk.section_title,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "chunk_index": chunk.chunk_index,
                "language": "da",
                "text": chunk.text,
                "token_count": chunk.token_count,
                "parser_version": parser_version,
            }
            points.append(
                models.PointStruct(
                    id=str(point_id),
                    vector=self.embeddings.embed(chunk.text),
                    payload=payload,
                )
            )
        if points:
            self.client.upsert(collection_name=LEARNING_COLLECTION, points=points)
        return point_ids

    def upsert_official_questions(
        self,
        *,
        track_slug: str,
        official_exam_paper_id: UUID,
        questions: Iterable[ParsedOfficialQuestion],
    ) -> dict[int, UUID]:
        point_ids: dict[int, UUID] = {}
        question_points: list[models.PointStruct] = []
        answer_points: list[models.PointStruct] = []
        for question in questions:
            question_id = uuid5(
                NAMESPACE_URL,
                f"question:{official_exam_paper_id}:{question.question_number}:{question.content_sha256}",
            )
            answer_id = uuid5(
                NAMESPACE_URL,
                f"answer:{official_exam_paper_id}:{question.question_number}:{question.correct_choice}",
            )
            point_ids[question.question_number] = question_id
            correct_answer_text = question.choices[question.correct_choice]
            choices = {letter.value: value for letter, value in question.choices.items()}
            question_text = (
                f"{question.stem}\n"
                + "\n".join(f"{key}: {value}" for key, value in choices.items())
                + f"\nCorrect: {question.correct_choice.value}: {correct_answer_text}"
            )
            question_points.append(
                models.PointStruct(
                    id=str(question_id),
                    vector=self.embeddings.embed(question_text),
                    payload={
                        "object_type": "official_question",
                        "exam_track_slug": track_slug,
                        "official_exam_paper_id": str(official_exam_paper_id),
                        "question_number": question.question_number,
                        "stem": question.stem,
                        "choices": choices,
                        "correct_choice": question.correct_choice.value,
                        "correct_answer_text": correct_answer_text,
                        "source_page_start": question.source_page_start,
                        "source_page_end": question.source_page_end,
                        "immutable_version": 1,
                        "content_sha256": question.content_sha256,
                        "language": "da",
                    },
                )
            )
            answer_text = f"Question {question.question_number}: {correct_answer_text}"
            answer_points.append(
                models.PointStruct(
                    id=str(answer_id),
                    vector=self.embeddings.embed(answer_text),
                    payload={
                        "object_type": "official_answer",
                        "exam_track_slug": track_slug,
                        "official_exam_paper_id": str(official_exam_paper_id),
                        "question_number": question.question_number,
                        "correct_choice": question.correct_choice.value,
                        "correct_answer_text": correct_answer_text,
                        "language": "da",
                    },
                )
            )
        if question_points:
            self.client.upsert(collection_name=QUESTION_COLLECTION, points=question_points)
        if answer_points:
            self.client.upsert(collection_name=ANSWER_COLLECTION, points=answer_points)
        return point_ids

    def search(self, *, query: str, track_slug: str, collections: list[str], limit: int) -> list[RetrievalHit]:
        vector = self.embeddings.embed(query)
        hits: list[RetrievalHit] = []
        collection_map = {
            "learning_chunks": LEARNING_COLLECTION,
            "official_questions": QUESTION_COLLECTION,
            "official_answers": ANSWER_COLLECTION,
            "explanations": EXPLANATION_COLLECTION,
        }
        query_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="exam_track_slug",
                    match=models.MatchValue(value=track_slug),
                )
            ]
        )
        for alias in collections:
            collection = collection_map[alias]
            try:
                # Try the newer query method first
                if hasattr(self.client, 'query_points'):
                    results = self.client.query_points(
                        collection_name=collection,
                        query=vector,
                        query_filter=query_filter,
                        limit=limit,
                    ).points
                else:
                    # Fallback to older search method
                    results = self.client.search(
                        collection_name=collection,
                        query_vector=vector,
                        query_filter=query_filter,
                        limit=limit,
                    )
                
                hits.extend(
                    RetrievalHit(collection=alias, score=result.score, payload=result.payload or {})
                    for result in results
                )
            except Exception as e:
                print(f"Error searching collection {collection}: {e}")
                continue
        
        return sorted(hits, key=lambda hit: hit.score, reverse=True)[:limit]

