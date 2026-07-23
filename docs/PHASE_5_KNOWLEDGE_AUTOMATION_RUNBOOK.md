# Denmark Academy Phase 5 Knowledge Automation & Content Intelligence

Phase 5 eliminates manual content maintenance by adding source management, automated collection, processing, versioning, quality validation, current-affairs generation, approvals, scheduler jobs, notifications, and analytics.

## Architecture

The platform uses a source-driven, append-only pipeline:

```text
Knowledge Source -> Collection Run -> Document Version -> Processing Jobs -> Metadata/Duplicate/Quality -> Approval -> Publication
```

Generated current-affairs resources use the same governance path:

```text
Collected Article -> Current Affairs Item -> AI Resources -> Quality Validation -> Admin Approval
```

## Why This Design

Append-only versions preserve official traceability and prevent accidental overwrites. Processing jobs are separated from collection runs so each step can scale independently in background workers. AI-generated educational resources are kept separate from official content and require approval.

## Alternatives Considered

- Directly overwriting source documents: rejected because official documents need version history.
- One monolithic content job: rejected because extraction, chunking, embeddings, quality, and approval need independent retries.
- Publishing AI current-affairs content automatically: rejected because education quality and hallucination risk require review.

## Database Changes

Migration: `005_phase_5_knowledge_automation.sql`

Key tables:

- `knowledge_sources`
- `content_collection_runs`
- `collected_documents`
- `document_versions_automation`
- `document_processing_jobs`
- `content_metadata_intelligence`
- `duplicate_detection_groups`
- `current_affairs_items`
- `generated_content_resources`
- `content_approval_workflows`
- `content_quality_validations`
- `content_notifications`
- `background_scheduler_jobs`
- `content_analytics_snapshots`

## API Contracts

```text
POST /api/v1/knowledge/sources
GET  /api/v1/knowledge/sources
POST /api/v1/knowledge/documents/manual
POST /api/v1/knowledge/documents/process
POST /api/v1/knowledge/current-affairs/generate
POST /api/v1/knowledge/approvals/decision
POST /api/v1/knowledge/scheduler/jobs
POST /api/v1/knowledge/notifications
GET  /api/v1/knowledge/analytics
```

## Scheduler Design

`background_scheduler_jobs` stores job type, cron/interval config, payload, enablement, and run state. Workers can claim due jobs and invoke the same service methods used by the API.

## AI Integration

Current-affairs generation creates summaries, revision notes, flashcards, practice questions, and official-style questions. The implementation is deterministic by default and can call Phase 3 AI services later. Every generated resource is quality validated and submitted to approval.

## Scalability

- Collection runs are separate from processing jobs.
- Processing jobs can be distributed across worker containers.
- Version hashes support idempotency and duplicate detection.
- Analytics snapshots avoid expensive dashboard scans.
- Future MCP connectors plug in as source adapters.

## Monitoring

Track:

- Collection run failures
- Processing job attempts/failures
- Average quality score
- Pending approvals
- Duplicate rate
- Generated resource volume
- Scheduler lag

## Security And Traceability

- Official documents are never overwritten.
- Every version stores source trace data.
- Generated resources store source links and approval status.
- Admin decisions are stored with reviewer and note.
- Student-facing publication must come after approval.
