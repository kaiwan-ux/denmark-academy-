-- Remove runtime-unused tables after frontend/backend scope reduction.
-- These tables are not referenced by active API routers, services, or frontend routes.

DROP TABLE IF EXISTS admin_publish_events CASCADE;
DROP TABLE IF EXISTS audit_events CASCADE;
DROP TABLE IF EXISTS course_subtopics CASCADE;
DROP TABLE IF EXISTS exam_blueprint_sections CASCADE;
DROP TABLE IF EXISTS official_question_errata CASCADE;
DROP TABLE IF EXISTS student_course_enrollments CASCADE;
DROP TABLE IF EXISTS user_achievements CASCADE;
