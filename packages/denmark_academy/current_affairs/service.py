from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row

from denmark_academy.config import get_settings
from denmark_academy.current_affairs.fetcher import RSSFetcher
from denmark_academy.current_affairs.models import (
    AIArticleAnalysis,
    AnswerResult,
    AnswerSubmission,
    Article,
    PracticeQuestion,
    PracticeRequest,
    Question,
)
from denmark_academy.current_affairs.processor import AIProcessor
from denmark_academy.current_affairs.quality import QuestionQualityValidator
from denmark_academy.current_affairs.vector_store import CurrentAffairsVectorStore

logger = logging.getLogger(__name__)
settings = get_settings()


class CurrentAffairsService:
    """Current Affairs ingestion, quality control, lifecycle, and practice sessions."""

    _refresh_lock = asyncio.Lock()
    _last_priority_refresh: datetime | None = None

    def __init__(self) -> None:
        self.fetcher = RSSFetcher()
        self.processor = AIProcessor()
        self.quality = QuestionQualityValidator(similarity_threshold=0.85)
        self.vectors = CurrentAffairsVectorStore(self.quality)

    async def fetch_and_process_articles(
        self,
        max_articles: int | None = None,
        regenerate_existing: bool = False,
    ) -> dict:
        """Fetch the latest articles and retain exactly five validated questions per relevant article."""
        articles = await self.fetcher.fetch_latest_articles()
        limit = max_articles if max_articles is not None else settings.current_affairs_max_articles_per_run
        selected_articles = articles[:limit]
        stats = {
            "fetched": len(articles), "new": 0, "processed": 0, "relevant": 0,
            "questions_generated": 0, "skipped": 0, "failed": 0,
        }
        existing_stems = self._question_stems_snapshot()
        semaphore = asyncio.Semaphore(3)

        async def process(article: dict) -> None:
            async with semaphore:
                article_id = self._article_id_for_url(article["url"])
                if article_id is not None and not regenerate_existing:
                    stats["skipped"] += 1
                    return
                try:
                    if article_id is None:
                        article_id = self._save_article(article, "pending")
                        stats["new"] += 1
                    analysis = await self._generate_article_question_set(
                        article["title"], article["content"], existing_stems
                    )
                    if analysis.is_relevant and analysis.questions:
                        self._update_article_processed(article_id, analysis)
                        saved_count = self._save_questions(article_id, analysis.questions)
                        stats["relevant"] += 1
                        stats["questions_generated"] += saved_count
                        existing_stems.extend(question.stem for question in analysis.questions)
                    elif not regenerate_existing:
                        self._mark_article_skipped(article_id)
                    stats["processed"] += 1
                except Exception as exc:
                    logger.exception("Failed to process Current Affairs article %s", article.get("url"))
                    if article_id is not None and not regenerate_existing:
                        self._mark_article_failed(article_id, str(exc))
                    stats["failed"] += 1

        await asyncio.gather(*(process(article) for article in selected_articles))
        logger.info("Current Affairs refresh completed: %s", stats)
        return stats

    async def _generate_article_question_set(
        self, title: str, content: str, existing_stems: list[str]
    ) -> AIArticleAnalysis:
        """Retry generation until five unique validated candidates are available."""
        base: AIArticleAnalysis | None = None
        candidates = []
        for attempt in range(3):
            analysis = await self.processor.analyze_article(
                title,
                content,
                variation_seed=f"{uuid4()}:{attempt}",
                existing_stems=[*existing_stems, *(item.stem for item in candidates)],
            )
            base = base or analysis
            if not analysis.is_relevant:
                return analysis
            candidates.extend(analysis.questions or [])
            selected = self.quality.select_unique(
                candidates,
                [(stem, "") for stem in existing_stems],
                limit=5,
            )
            if len(selected) == 5:
                return analysis.model_copy(update={"questions": selected})
        selected = self.quality.select_unique(
            candidates, [(stem, "") for stem in existing_stems], limit=5
        )
        if not base:
            raise RuntimeError("Current Affairs generation returned no analysis")
        return base.model_copy(update={"questions": selected or None})

    async def ensure_priority_pool(self, *, force: bool = False) -> dict:
        """Keep the latest-six-article priority pool warm without delaying login."""
        async with self._refresh_lock:
            await asyncio.to_thread(self.cleanup_expired)
            now = datetime.now(timezone.utc)
            if not force and self._last_priority_refresh:
                if (now - self._last_priority_refresh).total_seconds() < 900:
                    return {"status": "fresh"}
            stats = await self.fetch_and_process_articles(max_articles=6, regenerate_existing=False)
            self.__class__._last_priority_refresh = datetime.now(timezone.utc)
            return stats

    def get_articles(self, exam_type: str | None = None, limit: int = 20) -> list[Article]:
        query = "SELECT * FROM current_affairs_articles WHERE is_relevant = TRUE"
        params: list = []
        if exam_type and exam_type != "both":
            query += " AND (exam_type = %s OR exam_type = 'both')"
            params.append(exam_type)
        query += " ORDER BY published_date DESC NULLS LAST LIMIT %s"
        params.append(min(max(limit, 1), 100))
        with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
            rows = conn.execute(query, params).fetchall()
        return [Article(**dict(row)) for row in rows]

    def get_article(self, article_id: UUID) -> Article | None:
        with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
            row = conn.execute("SELECT * FROM current_affairs_articles WHERE id=%s", (article_id,)).fetchone()
        return Article(**dict(row)) if row else None

    def get_questions(
        self, exam_type: str | None = None, difficulty: str | None = None, limit: int = 50
    ) -> list[Question]:
        query = "SELECT * FROM current_affairs_questions WHERE expires_at > now()"
        params: list = []
        if exam_type and exam_type != "both":
            query += " AND (exam_type=%s OR exam_type='both')"
            params.append(exam_type)
        if difficulty:
            query += " AND difficulty=%s"
            params.append(difficulty)
        query += " ORDER BY quality_score DESC, created_at DESC LIMIT %s"
        params.append(min(max(limit, 1), 200))
        with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
            rows = conn.execute(query, params).fetchall()
        return [Question(**dict(row)) for row in rows]

    def available_question_count(
        self, difficulty: str | None = None, excluded_ids: list[UUID] | None = None
    ) -> int:
        query = "SELECT COUNT(*)::int FROM current_affairs_questions WHERE expires_at > now()"
        params: list = []
        if difficulty:
            query += " AND difficulty=%s"
            params.append(difficulty)
        if excluded_ids:
            query += " AND NOT (id = ANY(%s::uuid[]))"
            params.append(excluded_ids)
        with psycopg.connect(settings.database_url) as conn:
            return int(conn.execute(query, params).fetchone()[0])

    async def start_practice_session(self, request: PracticeRequest, user_id: UUID) -> dict:
        """Create an exact-sized, unique session and atomically record every served item."""
        if request.refresh_articles:
            await self.ensure_priority_pool(force=False)

        for attempt in range(3):
            result = await asyncio.to_thread(self._create_persistent_session, request, user_id)
            if result is not None:
                return result
            if attempt < 2:
                await self.ensure_priority_pool(force=True)

        # Exact size is the final contract. Reuse an objective only when generation
        # could not produce alternatives; exact and semantic duplicates remain blocked.
        fallback = await asyncio.to_thread(
            self._create_persistent_session, request, user_id, True
        )
        if fallback is not None:
            logger.warning(
                "Current Affairs session used objective fallback for user %s", user_id
            )
            return fallback

        raise ValueError(
            f"Could not prepare {request.count} unique validated questions. "
            "Please retry after the news pool refresh completes."
        )

    def _create_persistent_session(
        self, request: PracticeRequest, user_id: UUID, allow_objective_reuse: bool = False
    ) -> dict | None:
        """Select and persist a session while holding the user's cycle row lock."""
        with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
            conn.execute(
                """
                INSERT INTO current_affairs_user_progress(user_id)
                VALUES (%s) ON CONFLICT(user_id) DO NOTHING
                """,
                (user_id,),
            )
            progress = conn.execute(
                "SELECT cycle FROM current_affairs_user_progress WHERE user_id=%s FOR UPDATE",
                (user_id,),
            ).fetchone()
            cycle = int(progress["cycle"])
            rows, pool_total, unseen_total = self._session_candidates(conn, request, user_id, cycle)
            cycle_reset = False

            global_unseen_total = int(conn.execute(
                """
                SELECT COUNT(*)::int AS total
                FROM current_affairs_questions q
                WHERE q.expires_at > now()
                  AND NOT EXISTS (
                    SELECT 1 FROM current_affairs_served_questions served
                    WHERE served.user_id=%s AND served.cycle=%s AND served.question_id=q.id
                  )
                """,
                (user_id, cycle),
            ).fetchone()["total"])
            if unseen_total == 0 and pool_total > 0 and global_unseen_total == 0:
                cycle += 1
                cycle_reset = True
                conn.execute(
                    "UPDATE current_affairs_user_progress SET cycle=%s, updated_at=now() WHERE user_id=%s",
                    (cycle, user_id),
                )
                rows, pool_total, unseen_total = self._session_candidates(conn, request, user_id, cycle)

            selected = self.quality.select_session_rows(
                rows, request.count, enforce_objectives=not allow_objective_reuse
            )
            if len(selected) != request.count:
                conn.commit()
                return None

            session_id = uuid4()
            conn.execute(
                """
                INSERT INTO current_affairs_practice_sessions(
                  id, user_id, exam_type, difficulty, total_questions
                ) VALUES (%s, %s, 'both', %s, %s)
                """,
                (session_id, user_id, request.difficulty, request.count),
            )
            self._record_served_questions(
                conn,
                [
                    (
                        user_id,
                        row["id"],
                        self.quality.normalize(row["question_stem"]),
                        cycle,
                        session_id,
                    )
                    for row in selected
                ],
            )
            conn.commit()

        questions = [PracticeQuestion(**dict(row)) for row in selected]
        return {
            "session_id": str(session_id),
            "questions": [question.model_dump() for question in questions],
            "total": request.count,
            "pool_total": pool_total,
            "served_before": max(0, pool_total - unseen_total),
            "cycle_reset": cycle_reset,
        }

    @staticmethod
    def _record_served_questions(conn, records: list[tuple]) -> None:
        """Bulk insert through a Psycopg cursor; Connection has no executemany API."""
        if not records:
            return
        with conn.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO current_affairs_served_questions(
                  user_id, question_id, question_fingerprint, cycle, session_id
                ) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT(user_id, question_id, cycle) DO NOTHING
                """,
                records,
            )

    def _session_candidates(self, conn, request: PracticeRequest, user_id: UUID, cycle: int) -> tuple[list, int, int]:
        filters = "q.expires_at > now()"
        params: list = []
        if request.difficulty:
            filters += " AND q.difficulty=%s"
            params.append(request.difficulty)

        pool_total = int(conn.execute(
            f"SELECT COUNT(*)::int AS total FROM current_affairs_questions q WHERE {filters}",
            params,
        ).fetchone()["total"])
        unseen_filter = filters + """
            AND NOT EXISTS (
              SELECT 1 FROM current_affairs_served_questions served
              WHERE served.user_id=%s AND served.cycle=%s AND served.question_id=q.id
            )
        """
        unseen_params = [*params, user_id, cycle]
        unseen_total = int(conn.execute(
            f"SELECT COUNT(*)::int AS total FROM current_affairs_questions q WHERE {unseen_filter}",
            unseen_params,
        ).fetchone()["total"])
        candidate_limit = min(max(request.count * 30, 120), 1000)
        rows = conn.execute(
            f"""
            WITH latest_articles AS (
              SELECT id FROM current_affairs_articles
              WHERE is_relevant=TRUE
              ORDER BY published_date DESC NULLS LAST
              LIMIT 6
            )
            SELECT q.*, a.title AS article_title, a.url AS article_url
            FROM current_affairs_questions q
            JOIN current_affairs_articles a ON a.id=q.article_id
            WHERE {unseen_filter}
            ORDER BY CASE WHEN q.article_id IN (SELECT id FROM latest_articles) THEN 0 ELSE 1 END,
                     random()
            LIMIT %s
            """,
            [*unseen_params, candidate_limit],
        ).fetchall()
        return list(rows), pool_total, unseen_total

    def restart_progress(self, user_id: UUID) -> dict:
        """Start a new per-user cycle without deleting audit history."""
        with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
            row = conn.execute(
                """
                INSERT INTO current_affairs_user_progress(user_id, cycle)
                VALUES (%s, 2)
                ON CONFLICT(user_id) DO UPDATE
                  SET cycle=current_affairs_user_progress.cycle+1, updated_at=now()
                RETURNING cycle
                """,
                (user_id,),
            ).fetchone()
            conn.commit()
        return {"cycle": int(row["cycle"]), "message": "Current Affairs progress restarted"}

    def _select_questions(self, request: PracticeRequest, *, exclude_seen: bool) -> tuple[list, int]:
        """Compatibility helper for integrations; production sessions use persistent history."""
        base = """
            SELECT q.*, a.title AS article_title, a.url AS article_url
            FROM current_affairs_questions q
            JOIN current_affairs_articles a ON a.id=q.article_id
            WHERE q.expires_at > now()
        """
        params: list = []
        if request.difficulty:
            base += " AND q.difficulty=%s"
            params.append(request.difficulty)
        with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
            pool_total = conn.execute(
                "SELECT COUNT(*)::int total FROM (" + base + ") active", params
            ).fetchone()["total"]
            query, selection_params = base, list(params)
            if exclude_seen and request.exclude_question_ids:
                query += " AND NOT (q.id = ANY(%s::uuid[]))"
                selection_params.append(request.exclude_question_ids)
            query += " ORDER BY random() LIMIT %s"
            selection_params.append(max(request.count * 10, request.count))
            rows = conn.execute(query, selection_params).fetchall()
        return self.quality.select_session_rows(list(rows), request.count), int(pool_total)

    def submit_answer(self, session_id: UUID, answer: AnswerSubmission, user_id: UUID) -> AnswerResult:
        with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
            question = conn.execute(
                """
                SELECT q.*
                FROM current_affairs_questions q
                JOIN current_affairs_served_questions served
                  ON served.question_id=q.id AND served.session_id=%s
                JOIN current_affairs_practice_sessions session ON session.id=served.session_id
                WHERE q.id=%s AND q.expires_at > now() AND session.user_id=%s
                """,
                (session_id, answer.question_id, user_id),
            ).fetchone()
            if not question:
                raise ValueError("Question is not part of this user's active session")
            is_correct = answer.user_choice == question["correct_choice"]
            inserted = conn.execute(
                """
                INSERT INTO current_affairs_user_answers(session_id, question_id, user_choice, is_correct)
                VALUES (%s,%s,%s,%s)
                ON CONFLICT(session_id, question_id) DO NOTHING
                RETURNING id
                """,
                (session_id, answer.question_id, answer.user_choice, is_correct),
            ).fetchone()
            if inserted and is_correct:
                conn.execute(
                    """
                    UPDATE current_affairs_practice_sessions
                    SET correct_answers=correct_answers+1
                    WHERE id=%s AND user_id=%s
                    """,
                    (session_id, user_id),
                )
            conn.commit()
        return AnswerResult(
            is_correct=is_correct,
            correct_choice=question["correct_choice"],
            explanation=question["explanation"],
        )

    def complete_session(self, session_id: UUID, user_id: UUID) -> dict:
        with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
            session = conn.execute(
                """
                UPDATE current_affairs_practice_sessions
                SET completed=TRUE, completed_at=COALESCE(completed_at, now())
                WHERE id=%s AND user_id=%s RETURNING *
                """,
                (session_id, user_id),
            ).fetchone()
            conn.commit()
        if not session:
            raise ValueError("Session not found")
        return {
            "total_questions": session["total_questions"],
            "correct_answers": session["correct_answers"],
            "score_percentage": round(session["correct_answers"] / max(1, session["total_questions"]) * 100, 1),
        }

    def cleanup_expired(self) -> dict:
        """Delete questions older than 14 days from PostgreSQL and Qdrant."""
        with psycopg.connect(settings.database_url) as conn:
            rows = conn.execute(
                "DELETE FROM current_affairs_questions WHERE expires_at <= now() RETURNING id"
            ).fetchall()
            conn.execute(
                """
                DELETE FROM current_affairs_articles a
                WHERE a.created_at < now() - interval '14 days'
                  AND NOT EXISTS (SELECT 1 FROM current_affairs_questions q WHERE q.article_id=a.id)
                """
            )
            conn.commit()
        question_ids = [row[0] for row in rows]
        self.vectors.delete(question_ids)
        return {"expired_questions": len(question_ids)}

    def _question_stems_snapshot(self, limit: int = 1000) -> list[str]:
        with psycopg.connect(settings.database_url) as conn:
            rows = conn.execute(
                """
                SELECT question_stem FROM current_affairs_questions
                WHERE expires_at > now() ORDER BY created_at DESC LIMIT %s
                """,
                (limit,),
            ).fetchall()
        return [str(row[0]) for row in rows if row and row[0]]

    def _article_id_for_url(self, url: str) -> UUID | None:
        with psycopg.connect(settings.database_url) as conn:
            row = conn.execute("SELECT id FROM current_affairs_articles WHERE url=%s", (url,)).fetchone()
        return row[0] if row else None

    def _save_article(self, article: dict, status: str) -> UUID:
        article_id = uuid4()
        with psycopg.connect(settings.database_url) as conn:
            row = conn.execute(
                """
                INSERT INTO current_affairs_articles(id,title,url,source,published_date,processing_status)
                VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT(url) DO UPDATE SET
                  title=excluded.title, source=excluded.source,
                  published_date=excluded.published_date, updated_at=now()
                RETURNING id
                """,
                (article_id, article["title"], article["url"], article["source"], article["published_date"], status),
            ).fetchone()
            conn.commit()
        return row[0]

    def _update_article_processed(self, article_id: UUID, analysis: AIArticleAnalysis) -> None:
        with psycopg.connect(settings.database_url) as conn:
            conn.execute(
                """
                UPDATE current_affairs_articles SET processing_status='processed', is_relevant=TRUE,
                  exam_type=%s, topic=%s, summary=%s, error_message=NULL, updated_at=now()
                WHERE id=%s
                """,
                (analysis.exam_type, analysis.topic, analysis.summary, article_id),
            )
            conn.commit()

    def _mark_article_skipped(self, article_id: UUID) -> None:
        with psycopg.connect(settings.database_url) as conn:
            conn.execute(
                "UPDATE current_affairs_articles SET processing_status='skipped', updated_at=now() WHERE id=%s",
                (article_id,),
            )
            conn.commit()

    def _mark_article_failed(self, article_id: UUID, error: str) -> None:
        with psycopg.connect(settings.database_url) as conn:
            conn.execute(
                """
                UPDATE current_affairs_articles SET processing_status='failed', error_message=%s,
                  updated_at=now() WHERE id=%s
                """,
                (error[:2000], article_id),
            )
            conn.commit()

    def _save_questions(self, article_id: UUID, questions: list) -> int:
        saved_vectors: list[tuple[UUID, str, str, datetime]] = []
        with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
            rows = conn.execute(
                """
                SELECT question_stem, COALESCE(learning_objective,'') learning_objective
                FROM current_affairs_questions WHERE expires_at > now()
                ORDER BY created_at DESC LIMIT 1000
                """
            ).fetchall()
            # Global storage rejects duplicate facts, while objective diversity is
            # enforced per generated article and per delivered session.
            existing = [(row["question_stem"], "") for row in rows]
            for question in self.quality.select_unique(questions, existing, limit=5):
                stem = str(question.stem).strip()
                objective = self.quality.learning_objective(question)
                if self.quality.is_duplicate(stem, objective, existing):
                    continue
                row = conn.execute(
                    """
                    INSERT INTO current_affairs_questions(
                      article_id,question_stem,choice_a,choice_b,choice_c,correct_choice,
                      explanation,difficulty,exam_type,topic,learning_objective,quality_score,expires_at
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now()+interval '14 days')
                    ON CONFLICT DO NOTHING RETURNING id, expires_at
                    """,
                    (
                        article_id, stem, question.choice_a.strip(), question.choice_b.strip(),
                        question.choice_c.strip(), question.correct_choice, question.explanation.strip(),
                        question.difficulty, question.exam_type, question.topic.strip(), objective,
                        self.quality.quality_score(question),
                    ),
                ).fetchone()
                if row:
                    existing.append((stem, ""))
                    saved_vectors.append((row["id"], stem, objective, row["expires_at"]))
            conn.commit()
        for question_id, stem, objective, expires_at in saved_vectors:
            self.vectors.upsert(question_id, stem, objective, expires_at)
        return len(saved_vectors)

    # Compatibility helpers retained for existing tests and integrations.
    def _normalize_text(self, value: str) -> str:
        return self.quality.normalize(value)

    def _too_similar(self, left: str, right: str, threshold: float) -> bool:
        return self.quality.similarity(left, right) >= threshold

    def _is_duplicate_question(self, stem: str, existing_stems: list[str], threshold: float = 0.85) -> bool:
        return any(self._too_similar(stem, existing, threshold) for existing in existing_stems)
