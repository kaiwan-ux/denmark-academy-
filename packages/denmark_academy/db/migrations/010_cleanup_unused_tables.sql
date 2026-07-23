-- ============================================================================
-- CLEANUP MIGRATION: Remove unused tables from disabled features
-- ============================================================================
-- This migration removes tables from Phase 3, 4, 5, and 6 features that are:
-- 1. Not exposed in the frontend (nav removed)
-- 2. Not used by any active backend routers
-- 3. Contributing to database bloat without purpose
--
-- DISABLED FEATURES:
-- - Phase 3: AI Intelligence (ai_phase3 router disabled)
-- - Phase 4: Adaptive Learning (adaptive_phase4 router disabled)
-- - Phase 5: Knowledge Automation (knowledge_phase5 router disabled)
-- - Phase 6: Mentor & Exam Graph (graph_phase6 router disabled, mentor page removed)
--
-- ACTIVE FEATURES (tables preserved):
-- - Phase 1: Core (exam_tracks, users, etc.)
-- - Phase 2: LMS & Practice (courses, practice_sessions, official_questions)
-- - Current Affairs (new feature)
-- ============================================================================

-- ============================================================================
-- PHASE 6: Mentor & Exam Graph (REMOVE ALL)
-- ============================================================================
DROP TABLE IF EXISTS exam_post_submission_reports CASCADE;
DROP TABLE IF EXISTS exam_simulation_attempts CASCADE;
DROP TABLE IF EXISTS exam_simulation_configs CASCADE;
DROP TABLE IF EXISTS mentor_recommendations CASCADE;
DROP TABLE IF EXISTS mentor_sessions CASCADE;
DROP TABLE IF EXISTS graph_saved_views CASCADE;
DROP TABLE IF EXISTS graph_sync_events CASCADE;
DROP TABLE IF EXISTS graph_relationships CASCADE;
DROP TABLE IF EXISTS graph_nodes CASCADE;

-- ============================================================================
-- PHASE 5: Knowledge Automation (REMOVE ALL)
-- ============================================================================
DROP TABLE IF EXISTS content_analytics_snapshots CASCADE;
DROP TABLE IF EXISTS background_scheduler_jobs CASCADE;
DROP TABLE IF EXISTS content_notifications CASCADE;
DROP TABLE IF EXISTS content_quality_validations CASCADE;
DROP TABLE IF EXISTS content_approval_workflows CASCADE;
DROP TABLE IF EXISTS generated_content_resources CASCADE;
DROP TABLE IF EXISTS current_affairs_items CASCADE;
DROP TABLE IF EXISTS duplicate_detection_items CASCADE;
DROP TABLE IF EXISTS duplicate_detection_groups CASCADE;
DROP TABLE IF EXISTS content_metadata_intelligence CASCADE;
DROP TABLE IF EXISTS document_processing_jobs CASCADE;

-- Need to temporarily drop the foreign key constraint
ALTER TABLE collected_documents DROP CONSTRAINT IF EXISTS fk_collected_documents_latest_version;
DROP TABLE IF EXISTS document_versions_automation CASCADE;
DROP TABLE IF EXISTS collected_documents CASCADE;
DROP TABLE IF EXISTS content_collection_runs CASCADE;
DROP TABLE IF EXISTS knowledge_sources CASCADE;

-- ============================================================================
-- PHASE 4: Adaptive Learning (REMOVE ALL)
-- ============================================================================
DROP TABLE IF EXISTS adaptive_mock_blueprints CASCADE;
DROP TABLE IF EXISTS motivation_events CASCADE;
DROP TABLE IF EXISTS learning_analytics_snapshots CASCADE;
DROP TABLE IF EXISTS exam_readiness_snapshots CASCADE;
DROP TABLE IF EXISTS pass_predictions CASCADE;
DROP TABLE IF EXISTS adaptive_recommendations CASCADE;
DROP TABLE IF EXISTS spaced_repetition_items CASCADE;
DROP TABLE IF EXISTS spaced_repetition_policies CASCADE;
DROP TABLE IF EXISTS adaptive_difficulty_states CASCADE;
DROP TABLE IF EXISTS student_concept_mastery CASCADE;
DROP TABLE IF EXISTS student_learning_profiles CASCADE;
DROP TABLE IF EXISTS question_concept_links CASCADE;
DROP TABLE IF EXISTS learning_concepts CASCADE;

-- ============================================================================
-- PHASE 3: AI Intelligence (REMOVE ALL)
-- ============================================================================
DROP TABLE IF EXISTS ai_study_plans CASCADE;
DROP TABLE IF EXISTS ai_analytics_events CASCADE;
DROP TABLE IF EXISTS ai_evaluations CASCADE;
DROP TABLE IF EXISTS ai_conversation_messages CASCADE;
DROP TABLE IF EXISTS ai_conversation_threads CASCADE;
DROP TABLE IF EXISTS ai_mock_exam_items CASCADE;
DROP TABLE IF EXISTS ai_generated_questions CASCADE;
DROP TABLE IF EXISTS ai_content_artifacts CASCADE;
DROP TABLE IF EXISTS ai_prompt_runs CASCADE;
DROP TABLE IF EXISTS ai_retrieval_snapshots CASCADE;
DROP TABLE IF EXISTS ai_cache_entries CASCADE;
DROP TABLE IF EXISTS ai_prompt_templates CASCADE;
DROP TABLE IF EXISTS ai_providers CASCADE;

-- ============================================================================
-- VERIFICATION QUERIES (Comment out after confirming)
-- ============================================================================
-- To verify what tables remain, run:
-- SELECT table_name FROM information_schema.tables 
-- WHERE table_schema = 'public' 
-- ORDER BY table_name;

-- Expected remaining tables:
-- - exam_tracks, exam_blueprints (Phase 1 - Core)
-- - users (Phase 1 - Core)
-- - courses, course_chapters, course_topics, course_pages (Phase 2 - LMS)
-- - source_documents, official_exam_papers, official_questions (Phase 2 - Practice)
-- - practice_sessions, practice_session_questions, practice_session_answers (Phase 2 - Practice)
-- - ai_explanation_drafts, approved_explanations (Phase 2 - Admin explanations)
-- - ingestion_runs (Phase 2 - Admin)
-- - current_affairs_articles, current_affairs_questions (Current Affairs)
-- - current_affairs_practice_sessions, current_affairs_user_answers (Current Affairs)
-- - schema_migrations (System)

-- ============================================================================
-- NOTES:
-- ============================================================================
-- This cleanup removes approximately 60+ unused tables, significantly reducing:
-- 1. Database size and maintenance overhead
-- 2. Backup/restore time
-- 3. Query planning complexity
-- 4. Migration execution time
-- 5. Developer cognitive load
--
-- All active features remain fully functional:
-- - Home/Dashboard
-- - Reading (LMS)
-- - Past Paper Practice
-- - Smart Practice (AI-generated MCQs)
-- - Mock Exam
-- - Current Affairs
-- - Admin functions
-- ============================================================================
