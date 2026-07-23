# Denmark Academy Phase 3 AI Intelligence Layer

Phase 3 adds an enterprise AI ecosystem. It does not add a chatbot as the product center. AI services enhance the LMS, official exam system, progress engine, and revision workflow.

## Modules Implemented

- AI Orchestrator
- AI Gateway
- Provider abstraction for disabled, Ollama, OpenAI, Anthropic, Gemini
- Hybrid RAG Engine
- AI Tutor endpoint
- AI Explanation Generator endpoint
- AI Similar Question Generator endpoint
- AI Mock Generator endpoint
- Recommendation Engine
- Weakness Analyzer
- AI Revision Assistant
- AI Flashcard Generator
- AI Notes Generator
- AI Quiz Generator
- AI Study Planner
- Prompt Builder
- Conversation Memory schema
- AI Analytics schema/service
- AI Evaluation Layer

## Retrieval Strategy

Hybrid RAG always filters by `exam_track_id` / track slug before retrieval.

Sources considered:

- Official PR learning material
- Official Citizenship learning material
- Official questions
- Official answers
- Approved AI explanations
- Government/current-affairs document source family when ingested

The first implementation combines SQL keyword retrieval with Qdrant vector retrieval. External web/current-affairs retrieval is intentionally not called from this layer; those documents should be ingested as governed source documents first.

## Evaluation Gate

Every AI artifact can be evaluated for:

- Groundedness
- Exam alignment
- Hallucination risk
- Duplication against official questions
- Quality score

Decisions:

- `approve`
- `needs_review`
- `reject`

Low quality outputs should stay out of student-facing surfaces until reviewed.

## Provider Strategy

The AI Gateway exposes a single completion interface. Provider-specific clients are hidden behind adapters so switching from Ollama to OpenAI, Anthropic, or Gemini does not change business logic.

The default `disabled` provider returns deterministic workflow text. This keeps the platform functional when AI services are disabled.

## API Highlights

```text
POST /api/v1/ai/rag/retrieve
POST /api/v1/ai/tutor
POST /api/v1/ai/explanations
POST /api/v1/ai/similar-questions
POST /api/v1/ai/mock-exams
POST /api/v1/ai/recommendations
GET  /api/v1/ai/users/{userId}/tracks/{track}/weaknesses
POST /api/v1/ai/revision-assistant
POST /api/v1/ai/flashcards
POST /api/v1/ai/notes
POST /api/v1/ai/quizzes
POST /api/v1/ai/study-plans
POST /api/v1/ai/evaluate
```

## Security And Cost Controls

- Prompt templates are data/version controlled, not hardcoded in business services.
- Track filters are applied before semantic retrieval.
- Provider abstraction centralizes model access.
- Cache keys are derived from prompt/model/purpose.
- Retrieval snapshots support auditability.
- Evaluation records support admin review and quality governance.
- Disabled provider allows local workflows without token spend.
