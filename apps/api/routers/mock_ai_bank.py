from __future__ import annotations

import json
import re
from hashlib import sha256
from typing import Any, Literal

import psycopg
from fastapi import APIRouter, HTTPException
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from denmark_academy.ai.api_key_manager import get_api_key_manager
from denmark_academy.ai.providers import AIGateway
from denmark_academy.ai.schemas import AICompletionRequest, PromptMessage
from denmark_academy.config import get_settings
from denmark_academy.current_affairs.quality import QuestionQualityValidator
from denmark_academy.retrieval.qdrant import QdrantRepository

router = APIRouter(prefix="/api/v1/admin/mock-ai-questions", tags=["mock-ai-questions"])
settings = get_settings()
quality_validator = QuestionQualityValidator(similarity_threshold=0.85)

Track = Literal["pr", "citizenship"]
Section = Literal["knowledge", "current_affairs", "danish_values"]
Provider = Literal["gemini", "grok"]


class GenerateMockBankRequest(BaseModel):
    track: Track
    section: Section = "knowledge"
    count: int = Field(default=10, ge=1, le=40)
    difficulty: Literal["easy", "medium", "hard"] = "hard"
    auto_approve: bool = True


class ReviewMockQuestionRequest(BaseModel):
    status: Literal["approved", "rejected", "archived"]


@router.get("")
def list_mock_ai_questions(track: Track, section: Section | None = None, status: str = "approved", limit: int = 200) -> list[dict]:
    clauses = ["et.slug = %s", "q.status = %s"]
    params: list[Any] = [track, status]
    if section:
        clauses.append("q.section = %s")
        params.append(section)
    params.append(min(max(limit, 1), 500))
    query = f"""
        SELECT q.*, et.slug AS track
        FROM mock_ai_question_bank q
        JOIN exam_tracks et ON et.id = q.exam_track_id
        WHERE {' AND '.join(clauses)}
        ORDER BY q.created_at DESC
        LIMIT %s
    """
    with _db_connect(row_factory=dict_row) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


@router.get("/references")
def list_cross_bank_references(track: Track, limit: int = 1000) -> list[dict]:
    """Question banks that a newly assembled mock exam must not imitate."""
    bounded = min(max(limit, 1), 2000)
    references: list[dict] = []
    with _db_connect(row_factory=dict_row) as conn:
        if _table_exists(conn, "user_question_attempts"):
            ai_rows = conn.execute(
                """
                SELECT regexp_replace(question_id, '^[^:]+:[^:]+:', '') AS stem,
                       '' AS learning_objective, 'ai_practice' AS source
                FROM user_question_attempts
                WHERE module='ai_generated_mcqs' AND track=%s
                ORDER BY attempted_at DESC LIMIT %s
                """,
                (track, bounded),
            ).fetchall()
            references.extend(dict(row) for row in ai_rows if row.get("stem"))
        if track == "citizenship" and _table_exists(conn, "current_affairs_questions"):
            current_rows = conn.execute(
                """
                SELECT q.question_stem AS stem,
                       COALESCE(q.learning_objective,'') AS learning_objective,
                       'current_affairs' AS source
                FROM current_affairs_questions q
                WHERE q.expires_at>now()
                ORDER BY q.created_at DESC LIMIT %s
                """,
                (bounded,),
            ).fetchall()
            references.extend(dict(row) for row in current_rows)
    return references[:bounded]


@router.post("/generate")
async def generate_mock_ai_questions(payload: GenerateMockBankRequest) -> dict:
    """Generate a RAG-grounded, cross-bank unique, hard mock-question pool."""
    track_id = _track_id(payload.track)
    provider_plan = _provider_plan(payload.count)
    providers = [provider for provider, count in provider_plan if count > 0]
    rag_context, retrieval_backend = _retrieval_context(payload)
    if not rag_context:
        raise HTTPException(
            status_code=503,
            detail="No grounded official material is available for this track and section",
        )

    references = _existing_question_references(payload.track, payload.section)
    accepted: list[tuple[str, str]] = []
    accepted_contexts: set[str] = set()
    inserted: list[dict] = []
    errors: list[dict] = []
    avoid_examples = _existing_question_examples(payload.track, payload.section, limit=20)

    for attempt in range(6):
        remaining = payload.count - len(inserted)
        if remaining <= 0:
            break
        provider = providers[attempt % len(providers)]
        try:
            candidates = await _generate_with_provider(
                provider,
                payload,
                min(40, max(remaining * 2, remaining)),
                rag_context,
                avoid_examples + "\n" + "\n".join(f"- {stem}" for stem, _ in accepted),
            )
            with _db_connect(row_factory=dict_row) as conn:
                for candidate in candidates:
                    if len(inserted) >= payload.count:
                        break
                    normalized = _normalize_question(candidate)
                    stem = normalized["stem"]
                    objective = normalized.get("learning_objective", "")
                    score = _quality_score(normalized, payload.section)
                    if score < 0.82:
                        errors.append({"provider": provider, "stem": stem[:80], "error": "quality_score_too_low"})
                        continue
                    if _matches_reference(stem, objective, references + accepted):
                        errors.append({"provider": provider, "stem": stem[:80], "error": "semantic_duplicate"})
                        continue
                    if objective and any(
                        prior_objective
                        and quality_validator.similarity(objective, prior_objective) >= 0.82
                        for _, prior_objective in accepted
                    ):
                        errors.append({"provider": provider, "stem": stem[:80], "error": "repeated_learning_objective"})
                        continue
                    context_key = quality_validator.normalize(
                        f"{payload.section}:{normalized.get('grounding_source', '')}"
                    )
                    if context_key in accepted_contexts:
                        errors.append({"provider": provider, "stem": stem[:80], "error": "repeated_source_context"})
                        continue
                    row = conn.execute(
                        """
                        INSERT INTO mock_ai_question_bank (
                          exam_track_id, provider_key, section, stem, choice_a, choice_b, choice_c, choice_d,
                          correct_choice, explanation, difficulty, status, quality_score, content_sha256, metadata,
                          reviewed_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'hard', %s, %s, %s, %s,
                          CASE WHEN %s = 'approved' THEN now() ELSE NULL END)
                        ON CONFLICT (content_sha256) DO NOTHING
                        RETURNING *
                        """,
                        (
                            track_id, provider, payload.section, stem,
                            normalized["choice_a"], normalized["choice_b"], normalized["choice_c"],
                            normalized["choice_d"], normalized["correct_choice"], normalized["explanation"],
                            "approved" if payload.auto_approve else "needs_review", score,
                            _question_hash(payload.track, normalized),
                            Jsonb({
                                "generator": "mock_ai_bank_v2_rag",
                                "auto_approved": payload.auto_approve,
                                "rag_grounded": True,
                                "retrieval_backend": retrieval_backend,
                                "learning_objective": objective,
                                "grounding_source": normalized.get("grounding_source", ""),
                                "rag_context_sha256": sha256(rag_context.encode("utf-8")).hexdigest(),
                                "rag_collections": ["learning_chunks"],
                            }),
                            "approved" if payload.auto_approve else "needs_review",
                        ),
                    ).fetchone()
                    if row:
                        inserted.append(dict(row))
                        accepted.append((stem, objective))
                        references.append((stem, objective))
                conn.commit()
        except Exception as exc:
            errors.append({"provider": provider, "error": _safe_error(exc)})

    return {
        "track": payload.track,
        "section": payload.section,
        "requested": payload.count,
        "inserted": len(inserted),
        "complete": len(inserted) == payload.count,
        "rag_grounded": True,
        "retrieval_backend": retrieval_backend,
        "providers": dict(provider_plan),
        "errors": errors,
        "questions": inserted,
    }


@router.patch("/{question_id}/review")
def review_mock_ai_question(question_id: str, payload: ReviewMockQuestionRequest) -> dict:
    with _db_connect(row_factory=dict_row) as conn:
        row = conn.execute(
            """
            UPDATE mock_ai_question_bank
            SET status = %s, reviewed_at = now()
            WHERE id = %s
            RETURNING *
            """,
            (payload.status, question_id),
        ).fetchone()
        conn.commit()
    if not row:
        raise HTTPException(status_code=404, detail="AI mock question not found")
    return dict(row)


def _provider_plan(count: int) -> list[tuple[Provider, int]]:
    key_manager = get_api_key_manager()
    has_grok = bool(key_manager.get_grok_keys())
    has_gemini = bool(key_manager.get_gemini_keys())
    if has_grok and not has_gemini:
        return [("grok", count)]
    if has_gemini and not has_grok:
        return [("gemini", count)]
    if not has_grok and not has_gemini:
        return [("grok", count)]
    grok_count = count - (count // 2)
    gemini_count = count // 2
    return [("grok", grok_count), ("gemini", gemini_count)]


async def _generate_with_provider(
    provider: Provider,
    payload: GenerateMockBankRequest,
    count: int,
    rag_context: str,
    avoid_examples: str,
) -> list[dict[str, Any]]:
    request = AICompletionRequest(
        provider=provider,
        purpose="mock_question",
        messages=[
            PromptMessage(
                role="system",
                content="You generate high-quality Danish exam multiple-choice questions. Return strict JSON only.",
            ),
            PromptMessage(
                role="user", content=_prompt(payload, count, rag_context, avoid_examples)
            ),
        ],
        temperature=0.55,
        max_tokens=min(6000, 900 + count * 650),
    )
    manager = get_api_key_manager()
    configured_keys = manager.get_grok_keys() if provider == "grok" else manager.get_gemini_keys()
    last_error: Exception | None = None
    for _ in range(max(1, len(configured_keys))):
        try:
            # A new registry advances round-robin selection, so a failed first key
            # is followed immediately by the second configured key.
            response = await AIGateway().complete(request)
            if response.provider == "disabled":
                raise RuntimeError("Provider unavailable or key missing")
            return _parse_questions(response.content)
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"All configured {provider} API keys failed") from last_error


def _prompt(payload: GenerateMockBankRequest, count: int, rag_context: str = "", avoid_examples: str = "") -> str:
    exam = "Indfødsretsprøven" if payload.track == "citizenship" else "Medborgerskabsprøven"
    section = {
        "knowledge": "dansk historie, samfund, demokrati, rettigheder, pligter og hverdagsliv",
        "current_affairs": "nyere danske samfundsforhold, politik og demokrati",
        "danish_values": "demokrati, ligestilling, ytringsfrihed, religionsfrihed og retsstat",
    }[payload.section]
    return f"""
Udarbejd {count} SVÆRE multiple-choice-spørgsmål på dansk til {exam}.
Område: {section}.

AUTORITATIV RAG-KONTEKST FRA QDRANT:
{rag_context}

SPØRGSMÅL SOM SKAL UNDGÅS SEMANTISK OG KONCEPTUELT:
{avoid_examples or '- Ingen'}

UFRAVIGELIGE KRAV:
- Alle fakta og det korrekte svar skal kunne dokumenteres direkte i RAG-konteksten.
- Hvert spørgsmål skal teste ét forskelligt, præcist læringsmål og en forskellig kontekst.
- Spørgsmålene må ikke omskrive eller ligne spørgsmålene på undgå-listen.
- Niveauet skal være svært, men fair og i officiel dansk prøvestil; ingen trickformuleringer.
- Fire svar A-D, præcis ét korrekt svar.
- Alle tre distraktorer skal være faktuelt mulige, samme type, specificitet, længde og grammatiske form som det korrekte svar.
- Undgå åbenlyst absurde svar, "alle ovenstående" og længdesignaler.
- PR og Citizenship må aldrig blandes.
- Angiv en kort forklaring og den konkrete KILDE, som dokumenterer svaret.

Returnér kun gyldig JSON:
{{"questions":[{{
  "stem":"...", "choice_a":"...", "choice_b":"...", "choice_c":"...", "choice_d":"...",
  "correct_choice":"A", "explanation":"...", "learning_objective":"...", "grounding_source":"KILDE 1"
}}]}}
""".strip()


def _parse_questions(content: str) -> list[dict[str, Any]]:
    start = content.find("{")
    end = content.rfind("}") + 1
    if start < 0 or end <= 0:
        raise ValueError("Provider returned no JSON object")
    data = json.loads(content[start:end])
    questions = data.get("questions")
    if not isinstance(questions, list):
        raise ValueError("Provider JSON did not contain a questions array")
    return [question for question in questions if isinstance(question, dict)]


def _clean_display_text(value: Any, *, choice: bool = False) -> str:
    """Remove model-produced checkbox/bullet and duplicated choice-label artifacts."""
    cleaned = re.sub(r"[☐☑☒□▢◻◼]", "", str(value or ""))
    cleaned = re.sub(r"^\s*[.·•:;-]+\s*", "", cleaned)
    if choice:
        cleaned = re.sub(r"^\s*(?:[A-Da-d][.)]|\([A-Da-d]\))\s*", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _normalize_question(question: dict[str, Any]) -> dict[str, str]:
    normalized = {
        "stem": _clean_display_text(question.get("stem")),
        "choice_a": _clean_display_text(question.get("choice_a"), choice=True),
        "choice_b": _clean_display_text(question.get("choice_b"), choice=True),
        "choice_c": _clean_display_text(question.get("choice_c"), choice=True),
        "choice_d": _clean_display_text(question.get("choice_d"), choice=True),
        "correct_choice": str(question.get("correct_choice") or "A").strip().upper(),
        "explanation": _clean_display_text(question.get("explanation")),
        "learning_objective": str(question.get("learning_objective") or "").strip(),
        "grounding_source": str(question.get("grounding_source") or "").strip(),
    }
    if normalized["correct_choice"] not in {"A", "B", "C", "D"}:
        normalized["correct_choice"] = "A"
    return normalized


def _quality_score(question: dict[str, str], section: Section) -> float:
    required = [
        "stem", "choice_a", "choice_b", "choice_c", "choice_d", "correct_choice",
        "explanation", "learning_objective", "grounding_source",
    ]
    if any(not question.get(field) for field in required):
        return 0.0
    choices = [question["choice_a"], question["choice_b"], question["choice_c"], question["choice_d"]]
    normalized_choices = [_normalize_text(choice) for choice in choices]
    if len(set(normalized_choices)) != 4:
        return 0.0
    lengths = [max(1, len(choice.split())) for choice in choices]
    if max(lengths) > max(5, min(lengths) * 3):
        return 0.45
    forbidden = ("alle ovenstående", "ingen af ovenstående", "helt sikkert forkert")
    if any(marker in _normalize_text(choice) for choice in choices for marker in forbidden):
        return 0.45
    if question["correct_choice"] not in {"A", "B", "C", "D"}:
        return 0.0

    score = 0.72
    if len(question["stem"].split()) >= 8:
        score += 0.07
    if len(question["explanation"].split()) >= 7:
        score += 0.07
    if question["grounding_source"].lower().startswith("kilde"):
        score += 0.07
    if len(question["learning_objective"].split()) >= 2:
        score += 0.04
    if max(lengths) <= min(lengths) * 2 + 1:
        score += 0.03
    if section == "danish_values" and any(
        word in _normalize_text(question["stem"] + " " + question["explanation"])
        for word in ("demokrati", "frihed", "ligestilling", "rettighed", "pligt", "grundlov")
    ):
        score += 0.03
    return min(score, 0.99)


def _question_hash(track: Track, question: dict[str, str]) -> str:
    raw = "|".join([track, question["stem"], question["choice_a"], question["choice_b"], question["choice_c"], question.get("choice_d", "")]).lower()
    return sha256(raw.encode("utf-8")).hexdigest()


def _track_id(track: Track) -> str:
    with _db_connect(row_factory=dict_row) as conn:
        row = conn.execute("SELECT id FROM exam_tracks WHERE slug = %s", (track,)).fetchone()
    if not row:
        raise HTTPException(status_code=400, detail=f"Unknown exam track: {track}")
    return str(row["id"])


def _db_connect(**kwargs):
    return psycopg.connect(
        settings.database_url,
        connect_timeout=settings.database_connect_timeout_seconds,
        **kwargs,
    )


def _safe_error(exc: Exception) -> str:
    return str(exc).replace("Bearer ", "Bearer [redacted] ")[:500]

def _retrieval_context(payload: GenerateMockBankRequest) -> tuple[str, str]:
    """Use Qdrant first, with the canonical PostgreSQL chunks as an availability fallback."""
    queries = {
        "knowledge": "dansk samfund historie demokrati rettigheder pligter uddannelse arbejde velfaerd",
        "current_affairs": "aktuelle danske samfundsforhold politik demokrati lovgivning",
        "danish_values": "danske vaerdier demokrati ytringsfrihed ligestilling religionsfrihed retsstat pligter rettigheder",
    }
    snippets: list[str] = []
    retrieval_backend = "qdrant"
    try:
        hits = QdrantRepository().search(
            query=queries[payload.section],
            track_slug=payload.track,
            collections=["learning_chunks"],
            limit=8,
        )
        for index, hit in enumerate(hits, start=1):
            payload_data = hit.payload or {}
            source_text = payload_data.get("text") or payload_data.get("stem") or payload_data.get("correct_answer_text") or ""
            if source_text:
                title = payload_data.get("section_title") or payload_data.get("title") or payload_data.get("object_type") or "Qdrant"
                snippets.append(f"KILDE {index} — {title}:\n{str(source_text)[:900]}")
    except Exception:
        snippets = []

    if not snippets:
        retrieval_backend = "postgres_official_chunks"
        try:
            with _db_connect(row_factory=dict_row) as conn:
                chunks = conn.execute(
                    """
                    SELECT dc.text, COALESCE(dc.section_title, sd.original_filename) AS title,
                           dc.page_start
                    FROM document_chunks dc
                    JOIN source_documents sd ON sd.id=dc.source_document_id
                    JOIN exam_tracks et ON et.id=sd.exam_track_id
                    WHERE et.slug=%s AND sd.source_type='learning_material'
                      AND sd.ingestion_status IN ('validated','needs_review')
                    ORDER BY random() LIMIT 8
                    """,
                    (payload.track,),
                ).fetchall()
            for index, chunk in enumerate(chunks, start=1):
                snippets.append(
                    f"KILDE {index} — {chunk['title']}, side {chunk['page_start']}:\n{str(chunk['text'])[:900]}"
                )
        except Exception:
            snippets = []

    if payload.section == "current_affairs":
        try:
            with _db_connect(row_factory=dict_row) as conn:
                articles = conn.execute(
                    """
                    SELECT title, COALESCE(summary,'') AS summary
                    FROM current_affairs_articles
                    WHERE is_relevant=TRUE AND created_at>now()-interval '14 days'
                    ORDER BY published_date DESC NULLS LAST LIMIT 6
                    """
                ).fetchall()
            offset = len(snippets)
            for index, article in enumerate(articles, start=offset + 1):
                snippets.append(f"KILDE {index} — {article['title']}:\n{article['summary']}")
            if articles:
                retrieval_backend += "+current_affairs"
        except Exception:
            pass
    return "\n\n".join(snippets[:12]), retrieval_backend


def _existing_question_examples(track: Track, section: Section, limit: int = 12) -> str:
    stems: list[str] = []
    try:
        with _db_connect(row_factory=dict_row) as conn:
            rows = conn.execute(
                """
                SELECT q.stem
                FROM official_questions q
                JOIN exam_tracks et ON et.id = q.exam_track_id
                WHERE et.slug = %s
                ORDER BY random()
                LIMIT %s
                """,
                (track, limit // 2),
            ).fetchall()
            stems.extend(str(row["stem"]) for row in rows if row.get("stem"))
            rows = conn.execute(
                """
                SELECT q.stem
                FROM mock_ai_question_bank q
                JOIN exam_tracks et ON et.id = q.exam_track_id
                WHERE et.slug = %s AND q.section = %s AND q.status <> 'archived'
                ORDER BY q.created_at DESC
                LIMIT %s
                """,
                (track, section, limit),
            ).fetchall()
            stems.extend(str(row["stem"]) for row in rows if row.get("stem"))
    except Exception:
        pass
    return "\n".join(f"- {stem[:220]}" for stem in stems[:limit])


def _existing_question_references(track: Track, section: Section) -> list[tuple[str, str]]:
    """Load stems/objectives from every bank that a mock question must not imitate."""
    references: list[tuple[str, str]] = []
    with _db_connect(row_factory=dict_row) as conn:
        queries = [
            ("official_questions", """
                SELECT q.stem, '' AS objective
                FROM official_questions q
                JOIN exam_tracks et ON et.id=q.exam_track_id
                WHERE et.slug=%s ORDER BY q.created_at DESC LIMIT 500
            """, (track,)),
            ("user_question_attempts", """
                SELECT regexp_replace(question_id, '^[^:]+:[^:]+:', '') AS stem,
                       '' AS objective
                FROM user_question_attempts
                WHERE module='ai_generated_mcqs' AND track=%s
                ORDER BY attempted_at DESC LIMIT 500
            """, (track,)),
            ("current_affairs_questions", """
                SELECT q.question_stem AS stem, COALESCE(q.learning_objective,'') AS objective
                FROM current_affairs_questions q
                WHERE q.expires_at>now() AND q.exam_type IN (%s,'both')
                ORDER BY q.created_at DESC LIMIT 500
            """, (track,)),
            ("mock_ai_question_bank", """
                SELECT q.stem, COALESCE(q.metadata->>'learning_objective','') AS objective
                FROM mock_ai_question_bank q
                JOIN exam_tracks et ON et.id=q.exam_track_id
                WHERE et.slug=%s AND q.section=%s AND q.status<>'archived'
                ORDER BY q.created_at DESC LIMIT 500
            """, (track, section)),
        ]
        for table_name, statement, params in queries:
            if not _table_exists(conn, table_name):
                continue
            for row in conn.execute(statement, params).fetchall():
                stem = str(row.get("stem") or "").strip()
                if stem:
                    references.append((stem, str(row.get("objective") or "").strip()))
    return references


def _table_exists(conn, table_name: str) -> bool:
    """Check schema capabilities before optional cross-bank queries."""
    row = conn.execute("SELECT to_regclass(%s) AS relation", (f"public.{table_name}",)).fetchone()
    if not row:
        return False
    if isinstance(row, dict):
        return row.get("relation") is not None
    return row[0] is not None


def _matches_reference(stem: str, objective: str, references: list[tuple[str, str]]) -> bool:
    for prior_stem, prior_objective in references:
        if quality_validator.similarity(stem, prior_stem) >= 0.85:
            return True
        if objective and prior_objective and quality_validator.similarity(objective, prior_objective) >= 0.82:
            return True
    return False


def _is_duplicate_or_similar(conn, track: Track, section: Section, question: dict[str, str]) -> bool:
    signature = _question_hash(track, question)
    if conn.execute("SELECT 1 FROM mock_ai_question_bank WHERE content_sha256 = %s", (signature,)).fetchone():
        return True
    rows = conn.execute(
        """
        SELECT q.stem
        FROM mock_ai_question_bank q
        JOIN exam_tracks et ON et.id = q.exam_track_id
        WHERE et.slug = %s AND q.section = %s AND q.status <> 'archived'
        ORDER BY q.created_at DESC
        LIMIT 250
        """,
        (track, section),
    ).fetchall()
    rows += conn.execute(
        """
        SELECT q.stem
        FROM official_questions q
        JOIN exam_tracks et ON et.id = q.exam_track_id
        WHERE et.slug = %s
        ORDER BY q.created_at DESC
        LIMIT 250
        """,
        (track,),
    ).fetchall()
    return any(_too_similar(question.get("stem", ""), str(row["stem"])) for row in rows if row.get("stem"))


def _too_similar(left: str, right: str, threshold: float = 0.72) -> bool:
    left_tokens = set(_normalize_text(left).split())
    right_tokens = set(_normalize_text(right).split())
    if not left_tokens or not right_tokens:
        return False
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens) >= threshold


def _normalize_text(value: str) -> str:
    cleaned = re.sub(r"[^\wæøåÆØÅ]+", " ", value.lower(), flags=re.UNICODE)
    return re.sub(r"\s+", " ", cleaned).strip()
