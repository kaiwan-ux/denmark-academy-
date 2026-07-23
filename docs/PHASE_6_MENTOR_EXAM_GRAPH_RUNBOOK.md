# Denmark Academy Phase 6: AI Mentor, Exam Simulation, Knowledge Graph

Phase 6 adds three integrated enterprise systems:

1. AI Personal Mentor
2. AI Exam Simulation Engine
3. AI Knowledge Graph and Concept Explorer

It also implements the dual graph requested by product strategy:

```text
Knowledge Graph
Books -> Chapters -> Topics -> Concepts -> Questions -> Explanations -> Current Affairs

Student Learning Graph
Student -> Weak Concepts -> Attempts -> Progress -> Revision -> Readiness
```

The two graphs are connected through concept and question nodes.

## Architecture

PostgreSQL remains the source of truth. Neo4j is the graph query engine. Qdrant remains semantic retrieval. The graph mirror tables in PostgreSQL provide traceability, testability, and fallback when Neo4j is unavailable.

```text
PostgreSQL source tables
  -> graph sync events
  -> graph_nodes / graph_relationships mirror
  -> Neo4j upsert
  -> graph algorithms
  -> AI Mentor / Exam Simulator / RAG enrichment
```

## Why This Design

A pure Neo4j-only graph would be fast for traversal but weak for auditability and local tests. A pure PostgreSQL graph would be operationally simpler but weaker for deep graph traversal and explorer tooling. The chosen dual-write/mirror model gives production graph power while preserving relational governance.

## Neo4j Graph Schema

Node labels:

- Book, Chapter, Topic, Concept
- OfficialQuestion, OfficialAnswer, AIQuestion, AIExplanation
- Flashcard, RevisionNote, CurrentAffairs, GovernmentDocument
- PastPaper, MockExam
- Student, LearningProfile, Attempt, Progress, Revision

Relationship types:

- BOOK_CONTAINS_CHAPTER
- CHAPTER_CONTAINS_TOPIC
- TOPIC_CONTAINS_CONCEPT
- CONCEPT_RELATED_TO_CONCEPT
- CONCEPT_TESTED_BY_QUESTION
- QUESTION_APPEARS_IN_PAPER
- QUESTION_HAS_EXPLANATION
- QUESTION_GENERATED_AI_VERSION
- CONCEPT_REFERENCED_IN_BOOK
- CONCEPT_APPEARS_IN_CURRENT_AFFAIRS
- STUDENT_MASTERED_CONCEPT
- STUDENT_WEAK_AT_CONCEPT
- QUESTION_RECOMMENDS_CONCEPT
- MOCK_CONTAINS_QUESTION
- FLASHCARD_CREATED_FROM_CONCEPT

## API Contracts

```text
POST /api/v1/graph/nodes
POST /api/v1/graph/relationships
POST /api/v1/graph/sync/tracks/{track}
POST /api/v1/graph/sync/users/{userId}/tracks/{track}
POST /api/v1/graph/explore
GET  /api/v1/graph/nodes/{stableKey}/detail
POST /api/v1/graph/learning-path
GET  /api/v1/graph/tracks/{track}/metrics
POST /api/v1/graph/mentor/advise
POST /api/v1/graph/exam-simulations/configs
PUT  /api/v1/graph/exam-simulations/attempts/{attemptId}/autosave
POST /api/v1/graph/exam-simulations/attempts/{attemptId}/report
```

## Synchronization

- PostgreSQL writes produce graph sync events.
- Sync services upsert graph mirror rows and can upsert Neo4j via the optional adapter.
- Qdrant retrieval can be enriched with graph context by fetching related concepts/questions before prompt assembly.

## Caching

- Graph explorer requests should be cached by track, root node, filters, depth, and overlay.
- Mentor context can cache centrality/community metrics per user/track for short TTLs.
- Exam reports are persisted after submission and reused for dashboards.

## Security

- Student graph edges are user-scoped.
- Knowledge graph nodes are track-scoped.
- Cross-graph relationships never expose another student's profile.
- Neo4j credentials are provided through environment configuration.

## Testing

- Graph algorithms are tested without Neo4j.
- Repository sync can be integration-tested with Postgres.
- Neo4j adapter can be tested separately in Docker.

## Monitoring

Track graph sync lag, failed sync events, node/relationship counts, Neo4j availability, mentor latency, exam autosave failures, and graph query response time.
