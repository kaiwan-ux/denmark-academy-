from pathlib import Path
from uuid import UUID
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from denmark_academy.api_models import (
    BlueprintValidationRequest,
    ExplanationDraftRequest,
    ExplanationReviewRequest,
    HealthResponse,
    IngestionRunRequest,
    ManifestRequest,
    RetrievalSearchRequest,
)
from denmark_academy.blueprints import validate_blueprint_payload
from denmark_academy.config import get_settings
from denmark_academy.db.migrate import run_migrations
from denmark_academy.ingestion.manifest import build_ingestion_manifest
from denmark_academy.ingestion.pipeline import IngestionPipeline
from denmark_academy.retrieval.qdrant import QdrantRepository
from apps.api.routers import (
    account,
    admin_phase2,
    chapter_practice,
    current_affairs,
    lms,
    mock_ai_bank,
    practice,
)
# Removed routers (hidden from navigation):
# from apps.api.routers import adaptive_phase4, ai_phase3, dashboard_search, graph_phase6, knowledge_phase5


def verify_admin_key(x_admin_key: str = Header(None, alias="X-Admin-Key")) -> None:
    """Verify admin API key for protected endpoints."""
    settings = get_settings()
    if settings.admin_api_key is None:
        # If no admin key is configured, allow access (backward compatibility for local dev)
        return
    if not x_admin_key or x_admin_key != settings.admin_api_key.get_secret_value():
        raise HTTPException(
            status_code=403, detail="Invalid or missing admin API key. Set X-Admin-Key header."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start optional background services without slowing local API boot."""
    scheduler = None
    if settings.current_affairs_scheduler_enabled:
        from denmark_academy.current_affairs.scheduler import get_scheduler

        scheduler = get_scheduler()
        scheduler.start()

    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.stop()


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)

# CORS Configuration - Use environment variable for allowed origins
allowed_origins = [
    origin.strip() for origin in settings.allowed_origins.split(",") if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(account.router)
app.include_router(chapter_practice.router)
app.include_router(lms.router)
app.include_router(practice.router)
app.include_router(current_affairs.router)
app.include_router(mock_ai_bank.router)
app.include_router(admin_phase2.router)
# Removed routers (hidden from navigation):
# app.include_router(dashboard_search.router)
# app.include_router(ai_phase3.router)
# app.include_router(adaptive_phase4.router)
# app.include_router(knowledge_phase5.router)
# app.include_router(graph_phase6.router)


@app.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse(status="ok", app=settings.app_name)


@app.get("/readyz")
def readyz() -> dict[str, str]:
    try:
        with _db_connect() as conn:
            conn.execute("SELECT 1")
        return {"status": "ready"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/admin/db/migrate", dependencies=[Depends(verify_admin_key)])
def migrate() -> dict[str, str]:
    """Protected endpoint: Run database migrations. Requires X-Admin-Key header."""
    run_migrations()
    return {"status": "migrated"}


@app.get("/api/v1/exam-tracks")
def exam_tracks() -> list[dict]:
    with _db_connect(row_factory=dict_row) as conn:
        rows = conn.execute(
            "SELECT id, slug, name, official_name, locale, is_active FROM exam_tracks ORDER BY slug"
        ).fetchall()
    return list(rows)


@app.post("/api/v1/admin/ingestion/manifests")
def create_manifest(request: ManifestRequest) -> dict:
    root_path = _resolve_root(request.root_path)
    if request.dry_run:
        return IngestionPipeline().dry_run(root_path)
    manifest = build_ingestion_manifest(root_path, settings.parser_version)
    return manifest.model_dump(mode="json")


@app.post("/api/v1/admin/ingestion/runs")
def run_ingestion(request: IngestionRunRequest) -> dict:
    root_path = _resolve_root(request.root_path)
    try:
        return IngestionPipeline().run(root_path, upsert_qdrant=request.upsert_qdrant)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/v1/admin/ingestion/runs/{run_id}")
def get_ingestion_run(run_id: UUID) -> dict:
    with _db_connect(row_factory=dict_row) as conn:
        row = conn.execute("SELECT * FROM ingestion_runs WHERE id = %s", (run_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Ingestion run not found")
    return dict(row)


@app.get("/api/v1/admin/source-documents")
def source_documents(track: str | None = None, type: str | None = None) -> list[dict]:
    clauses = []
    params = []
    if track:
        clauses.append("et.slug = %s")
        params.append(track)
    if type:
        clauses.append("sd.source_type = %s")
        params.append(type)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"""
        SELECT sd.*, et.slug AS track
        FROM source_documents sd
        JOIN exam_tracks et ON et.id = sd.exam_track_id
        {where}
        ORDER BY sd.created_at DESC
    """
    with _db_connect(row_factory=dict_row) as conn:
        rows = conn.execute(query, params).fetchall()
    return list(rows)


@app.get("/api/v1/admin/official-questions")
def official_questions(
    track: str | None = None,
    paper_code: str | None = None,
    limit: int | None = None,
    random_order: bool = False,
) -> list[dict]:
    clauses = []
    params = []
    if track:
        clauses.append("et.slug = %s")
        params.append(track)
    if paper_code:
        clauses.append("p.paper_code = %s")
        params.append(paper_code)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    order_by = (
        "ORDER BY random()" if random_order else "ORDER BY et.slug, p.paper_code, q.question_number"
    )
    limit_clause = ""
    if limit is not None:
        bounded_limit = min(max(limit, 1), 500)
        params.append(bounded_limit)
        limit_clause = "LIMIT %s"
    with _db_connect(row_factory=dict_row) as conn:
        rows = conn.execute(
            f"""
            SELECT q.*, et.slug AS track, p.paper_code
            FROM official_questions q
            JOIN official_exam_papers p ON p.id = q.official_exam_paper_id
            JOIN exam_tracks et ON et.id = q.exam_track_id
            {where}
            {order_by}
            {limit_clause}
            """,
            params,
        ).fetchall()
    return list(rows)


@app.post("/api/v1/admin/retrieval/search")
def retrieval_search(request: RetrievalSearchRequest) -> list[dict]:
    try:
        hits = QdrantRepository().search(
            query=request.query,
            track_slug=request.track,
            collections=request.collections,
            limit=request.limit,
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Unknown collection alias: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return [hit.model_dump(mode="json") for hit in hits]


@app.post("/api/v1/admin/exam-blueprints/validate")
def validate_blueprint(request: BlueprintValidationRequest) -> dict:
    payload = request.model_dump(mode="json")
    return validate_blueprint_payload(payload).model_dump(mode="json")


@app.post("/api/v1/admin/official-questions/{question_id}/explanation-drafts")
def create_explanation_draft(question_id: UUID, request: ExplanationDraftRequest) -> dict:
    if str(question_id) != request.official_question_id:
        raise HTTPException(
            status_code=400, detail="Path question_id and body official_question_id differ"
        )
    with _db_connect(row_factory=dict_row) as conn:
        row = conn.execute(
            """
            INSERT INTO ai_explanation_drafts (
              official_question_id, generated_text, model_provider, model_name,
              prompt_version, retrieval_snapshot
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                question_id,
                request.generated_text,
                request.model_provider,
                request.model_name,
                request.prompt_version,
                Jsonb(request.retrieval_snapshot),
            ),
        ).fetchone()
        conn.commit()
    return dict(row)


@app.post("/api/v1/admin/explanation-drafts/{draft_id}/approve")
def approve_explanation_draft(draft_id: UUID, request: ExplanationReviewRequest) -> dict:
    if not request.approved_text:
        raise HTTPException(status_code=400, detail="approved_text is required")
    with _db_connect(row_factory=dict_row) as conn:
        draft = conn.execute(
            """
            UPDATE ai_explanation_drafts
            SET status = 'approved',
                approved_text = %s,
                review_note = %s,
                reviewed_at = now()
            WHERE id = %s
            RETURNING *
            """,
            (request.approved_text, request.review_note, draft_id),
        ).fetchone()
        if not draft:
            raise HTTPException(status_code=404, detail="Draft not found")
        explanation = conn.execute(
            """
            INSERT INTO approved_explanations (
              official_question_id, ai_explanation_draft_id, explanation_text
            )
            VALUES (%s, %s, %s)
            ON CONFLICT (official_question_id)
            DO UPDATE SET
              ai_explanation_draft_id = EXCLUDED.ai_explanation_draft_id,
              explanation_text = EXCLUDED.explanation_text
            RETURNING *
            """,
            (draft["official_question_id"], draft_id, request.approved_text),
        ).fetchone()
        conn.commit()
    return {"draft": dict(draft), "approved_explanation": dict(explanation)}


@app.post("/api/v1/admin/explanation-drafts/{draft_id}/reject")
def reject_explanation_draft(draft_id: UUID, request: ExplanationReviewRequest) -> dict:
    with _db_connect(row_factory=dict_row) as conn:
        row = conn.execute(
            """
            UPDATE ai_explanation_drafts
            SET status = 'rejected',
                review_note = %s,
                reviewed_at = now()
            WHERE id = %s
            RETURNING *
            """,
            (request.review_note, draft_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Draft not found")
        conn.commit()
    return dict(row)


def _db_connect(**kwargs):
    return psycopg.connect(
        settings.database_url,
        connect_timeout=settings.database_connect_timeout_seconds,
        **kwargs,
    )


def _resolve_root(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.exists():
        raise HTTPException(status_code=400, detail=f"Root path does not exist: {resolved}")
    return resolved


@app.get("/api/v1/admin/mock-ai-questions")
def list_mock_ai_questions(
    track: str, section: str | None = None, status: str = "approved", limit: int = 200
) -> list[dict]:
    return mock_ai_bank.list_mock_ai_questions(
        track=track, section=section, status=status, limit=limit
    )


@app.post("/api/v1/admin/mock-ai-questions/generate")
async def generate_mock_ai_questions(request: mock_ai_bank.GenerateMockBankRequest) -> dict:
    return await mock_ai_bank.generate_mock_ai_questions(request)


@app.patch("/api/v1/admin/mock-ai-questions/{question_id}/review")
def review_mock_ai_question(
    question_id: str, request: mock_ai_bank.ReviewMockQuestionRequest
) -> dict:
    return mock_ai_bank.review_mock_ai_question(question_id, request)
