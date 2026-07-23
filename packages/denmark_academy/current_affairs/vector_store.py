from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.http import models

from denmark_academy.config import get_settings
from denmark_academy.current_affairs.quality import QuestionQualityValidator

logger = logging.getLogger(__name__)
COLLECTION = "da_current_affairs_questions"


class CurrentAffairsVectorStore:
    """Best-effort Qdrant index for duplicate detection and coordinated expiry."""

    def __init__(self, validator: QuestionQualityValidator) -> None:
        settings = get_settings()
        params = {"url": settings.qdrant_url}
        if settings.qdrant_api_key:
            params["api_key"] = settings.qdrant_api_key.get_secret_value()
        self.client = QdrantClient(**params)
        self.validator = validator
        self._ready = False

    def ensure_collection(self) -> None:
        if self._ready:
            return
        if not self.client.collection_exists(COLLECTION):
            self.client.create_collection(
                collection_name=COLLECTION,
                vectors_config=models.VectorParams(size=self.validator.dimension, distance=models.Distance.COSINE),
            )
            self.client.create_payload_index(COLLECTION, "expires_at", models.PayloadSchemaType.DATETIME)
        self._ready = True

    def find_duplicate(self, stem: str, threshold: float = 0.85) -> bool:
        try:
            self.ensure_collection()
            result = self.client.query_points(
                collection_name=COLLECTION,
                query=self.validator.embed(stem),
                limit=1,
                score_threshold=threshold,
            ).points
            return bool(result)
        except Exception as exc:
            logger.warning("Current Affairs vector duplicate lookup unavailable: %s", exc)
            return False

    def upsert(self, question_id: UUID, stem: str, objective: str, expires_at: datetime) -> None:
        try:
            self.ensure_collection()
            self.client.upsert(
                collection_name=COLLECTION,
                points=[models.PointStruct(
                    id=str(question_id),
                    vector=self.validator.embed(stem + " " + objective),
                    payload={
                        "question_id": str(question_id),
                        "question_stem": stem,
                        "learning_objective": objective,
                        "expires_at": expires_at.isoformat(),
                    },
                )],
                wait=False,
            )
        except Exception as exc:
            logger.warning("Current Affairs vector upsert unavailable: %s", exc)

    def delete(self, question_ids: list[UUID]) -> None:
        if not question_ids:
            return
        try:
            self.ensure_collection()
            self.client.delete(
                collection_name=COLLECTION,
                points_selector=models.PointIdsList(points=[str(item) for item in question_ids]),
                wait=False,
            )
        except Exception as exc:
            logger.warning("Current Affairs vector cleanup unavailable: %s", exc)
