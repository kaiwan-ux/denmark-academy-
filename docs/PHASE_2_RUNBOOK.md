# Denmark Academy Phase 2 Runbook

Phase 2 adds the Learning Management System and Official Exam System on top of Phase 1.

## Backend Modules

- LMS repository: `packages/denmark_academy/lms/repository.py`
- Course seeding from imported chunks: `packages/denmark_academy/lms/seeding.py`
- Practice engine: `packages/denmark_academy/practice/service.py`
- API schemas: `packages/denmark_academy/phase2_schemas.py`
- API routers: `apps/api/routers/`
- Database migration: `packages/denmark_academy/db/migrations/002_phase_2_lms_exam.sql`

## Frontend

Next.js App Router scaffold lives in `frontend/`.

Screens:

- `/dashboard`
- `/reader/[unitId]`
- `/practice`
- `/papers`
- `/revision`
- `/search`
- `/admin`

## Phase 2 API Highlights

```text
GET  /api/v1/tracks/{track}/course
GET  /api/v1/learning-units/{unitId}
PUT  /api/v1/users/{userId}/reading-progress/{learningUnitId}
POST /api/v1/users/{userId}/tracks/{track}/bookmarks
POST /api/v1/users/{userId}/tracks/{track}/notes
POST /api/v1/practice/sessions
POST /api/v1/practice/sessions/{sessionId}/questions/{sessionQuestionId}/answer
POST /api/v1/practice/sessions/{sessionId}/submit
GET  /api/v1/users/{userId}/tracks/{track}/revision
GET  /api/v1/users/{userId}/tracks/{track}/dashboard
POST /api/v1/search
POST /api/v1/admin/courses
POST /api/v1/admin/chapters
POST /api/v1/admin/topics
POST /api/v1/admin/learning-units
POST /api/v1/admin/tracks/{track}/seed-course-from-chunks
```

## Course Seeding

After Phase 1 ingestion has stored `document_chunks`, seed an editable course outline:

```powershell
Invoke-RestMethod -Method Post "http://localhost:8000/api/v1/admin/tracks/pr/seed-course-from-chunks?publish=false"
Invoke-RestMethod -Method Post "http://localhost:8000/api/v1/admin/tracks/citizenship/seed-course-from-chunks?publish=false"
```

## AI Boundaries

No AI is required in Phase 2.

Future AI can integrate through:

- `study_activity_events` for recommendations.
- `revision_queue_items` for weak-topic prediction.
- `official_question_classifications` for topic-aware retrieval.
- Existing Qdrant collections for semantic expansion of `/api/v1/search`.
- Existing explanation draft approval flow from Phase 1.

## Risk Notes

- Official questions remain immutable.
- Practice sessions read from official questions only.
- Mock exams use blueprint IDs and official question selection, never AI-generated questions.
- Every Phase 2 table that is track-sensitive includes `exam_track_id`.
