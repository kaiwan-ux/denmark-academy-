from typing import Any

from denmark_academy.ai.schemas import RetrievalRequest, RetrievedSource
from denmark_academy.lms.repository import Phase2Repository
from denmark_academy.retrieval.qdrant import QdrantRepository


class HybridRAGEngine:
    def __init__(
        self,
        repository: Phase2Repository | None = None,
        qdrant: QdrantRepository | None = None,
    ) -> None:
        self.repository = repository or Phase2Repository()
        self.qdrant = qdrant

    def retrieve(self, request: RetrievalRequest) -> tuple[list[RetrievedSource], dict[str, Any]]:
        keyword_sources = self._keyword_retrieve(request)
        vector_sources = self._vector_retrieve(request)
        merged = self._merge(keyword_sources + vector_sources, request.limit)
        snapshot = {
            "strategy": "hybrid_rag",
            "track": request.track,
            "purpose": request.purpose,
            "filters": request.filters,
            "source_count": len(merged),
        }
        return merged, snapshot

    def _keyword_retrieve(self, request: RetrievalRequest) -> list[RetrievedSource]:
        sources: list[RetrievedSource] = []
        with self.repository.connection() as conn:
            track_id = self.repository.track_id(conn, request.track)
            like = f"%{request.query}%"
            learning = conn.execute(
                """
                SELECT lu.id, lu.title, lu.body, lu.metadata
                FROM learning_units lu
                WHERE lu.exam_track_id = %s AND (lu.title ILIKE %s OR lu.body ILIKE %s)
                ORDER BY lu.sort_order LIMIT %s
                """,
                (track_id, like, like, request.limit),
            ).fetchall()
            for row in learning:
                sources.append(
                    RetrievedSource(
                        source_type="learning_material",
                        title=row["title"],
                        text=row["body"][:2000],
                        score=0.65,
                        metadata={"learning_unit_id": str(row["id"]), **(row["metadata"] or {})},
                    )
                )
            questions = conn.execute(
                """
                SELECT q.id, q.stem, q.choice_a, q.choice_b, q.choice_c, q.correct_choice, p.paper_code
                FROM official_questions q
                JOIN official_exam_papers p ON p.id = q.official_exam_paper_id
                WHERE q.exam_track_id = %s AND (
                  q.stem ILIKE %s OR q.choice_a ILIKE %s OR q.choice_b ILIKE %s OR q.choice_c ILIKE %s
                )
                ORDER BY p.paper_code, q.question_number LIMIT %s
                """,
                (track_id, like, like, like, like, request.limit),
            ).fetchall()
            for row in questions:
                answer_text = row[f"choice_{row['correct_choice'].lower()}"]
                sources.append(
                    RetrievedSource(
                        source_type="official_question",
                        title=f"Paper {row['paper_code']}",
                        text=f"{row['stem']}\nA: {row['choice_a']}\nB: {row['choice_b']}\nC: {row['choice_c'] or ''}\nOfficial answer: {row['correct_choice']} {answer_text}",
                        score=0.75,
                        metadata={"official_question_id": str(row["id"]), "paper_code": row["paper_code"]},
                    )
                )
            explanations = conn.execute(
                """
                SELECT ae.id, ae.explanation_text, q.id AS official_question_id
                FROM approved_explanations ae
                JOIN official_questions q ON q.id = ae.official_question_id
                WHERE q.exam_track_id = %s AND ae.explanation_text ILIKE %s
                LIMIT %s
                """,
                (track_id, like, request.limit),
            ).fetchall()
            for row in explanations:
                sources.append(
                    RetrievedSource(
                        source_type="ai_explanation",
                        title="Approved explanation",
                        text=row["explanation_text"],
                        score=0.55,
                        metadata={"approved_explanation_id": str(row["id"]), "official_question_id": str(row["official_question_id"])},
                    )
                )
            government_docs = conn.execute(
                """
                SELECT id, original_filename, metadata
                FROM source_documents
                WHERE exam_track_id = %s AND source_type = 'learning_material'
                  AND metadata->>'source_family' IN ('government_document', 'current_affairs')
                LIMIT %s
                """,
                (track_id, request.limit if request.include_current_affairs else 0),
            ).fetchall()
            for row in government_docs:
                sources.append(
                    RetrievedSource(
                        source_type=row["metadata"].get("source_family", "government_document"),
                        title=row["original_filename"],
                        text="Government/current-affairs document metadata is available; chunk ingestion supplies full text.",
                        score=0.4,
                        metadata={"source_document_id": str(row["id"]), **(row["metadata"] or {})},
                    )
                )
        return sources

    def _vector_retrieve(self, request: RetrievalRequest) -> list[RetrievedSource]:
        if self.qdrant is None:
            try:
                self.qdrant = QdrantRepository()
            except Exception:
                return []
        try:
            hits = self.qdrant.search(
                query=request.query,
                track_slug=request.track,
                collections=["learning_chunks", "official_questions", "official_answers", "explanations"],
                limit=request.limit,
            )
        except Exception:
            return []
        return [
            RetrievedSource(
                source_type=hit.payload.get("object_type", hit.collection),
                title=hit.payload.get("title") or hit.payload.get("paper_code"),
                text=hit.payload.get("text") or hit.payload.get("stem") or hit.payload.get("correct_answer_text") or "",
                score=hit.score,
                metadata=hit.payload,
            )
            for hit in hits
            if hit.payload.get("exam_track_slug") == request.track
        ]

    def _merge(self, sources: list[RetrievedSource], limit: int) -> list[RetrievedSource]:
        seen: set[str] = set()
        merged: list[RetrievedSource] = []
        for source in sorted(sources, key=lambda item: item.score, reverse=True):
            fingerprint = f"{source.source_type}:{source.title}:{source.text[:120]}"
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            merged.append(source)
            if len(merged) >= limit:
                break
        return merged

