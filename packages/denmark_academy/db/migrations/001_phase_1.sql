CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;

CREATE TABLE IF NOT EXISTS users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email citext NOT NULL UNIQUE,
  password_hash text,
  external_auth_provider text,
  external_auth_subject text,
  role text NOT NULL CHECK (role IN ('student', 'admin', 'reviewer')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_user_id uuid REFERENCES users(id),
  action text NOT NULL,
  entity_type text NOT NULL,
  entity_id uuid,
  metadata jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS exam_tracks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug text NOT NULL UNIQUE CHECK (slug IN ('pr', 'citizenship')),
  name text NOT NULL,
  official_name text NOT NULL,
  locale text NOT NULL DEFAULT 'da-DK',
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO exam_tracks (slug, name, official_name)
VALUES
  ('pr', 'Permanent Residence', 'Medborgerskabsproeven'),
  ('citizenship', 'Danish Citizenship', 'Indfoedsretsproeven')
ON CONFLICT (slug) DO NOTHING;

CREATE TABLE IF NOT EXISTS source_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  source_type text NOT NULL CHECK (source_type IN ('learning_material', 'question_paper', 'answer_key')),
  original_filename text NOT NULL,
  source_path text NOT NULL,
  storage_uri text NOT NULL,
  content_sha256 text NOT NULL,
  file_size_bytes bigint NOT NULL,
  page_count int,
  publication_date date,
  exam_date date,
  exam_session_label text,
  language text NOT NULL DEFAULT 'da',
  ingestion_status text NOT NULL DEFAULT 'pending'
    CHECK (ingestion_status IN ('pending', 'extracting', 'validated', 'failed', 'needs_review')),
  parser_version text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (exam_track_id, source_type, content_sha256)
);

CREATE INDEX IF NOT EXISTS idx_source_documents_track_type
  ON source_documents(exam_track_id, source_type);

CREATE TABLE IF NOT EXISTS document_pages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_document_id uuid NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,
  page_number int NOT NULL,
  extracted_text text NOT NULL,
  extraction_method text NOT NULL CHECK (extraction_method IN ('text', 'ocr', 'hybrid')),
  extraction_confidence numeric(5,4),
  metadata jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source_document_id, page_number)
);

CREATE TABLE IF NOT EXISTS document_chunks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_document_id uuid NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,
  page_start int NOT NULL,
  page_end int NOT NULL,
  section_title text,
  chunk_index int NOT NULL,
  text text NOT NULL,
  token_count int,
  qdrant_point_id uuid,
  metadata jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source_document_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS official_exam_papers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  question_document_id uuid NOT NULL REFERENCES source_documents(id),
  answer_document_id uuid REFERENCES source_documents(id),
  paper_code text NOT NULL,
  exam_date date,
  title text NOT NULL,
  duration_minutes int,
  expected_question_count int,
  parser_version text NOT NULL,
  validation_status text NOT NULL DEFAULT 'pending'
    CHECK (validation_status IN ('pending', 'valid', 'invalid', 'needs_review')),
  validation_report jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (exam_track_id, paper_code)
);

CREATE TABLE IF NOT EXISTS official_questions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  official_exam_paper_id uuid NOT NULL REFERENCES official_exam_papers(id),
  question_number int NOT NULL,
  stem text NOT NULL,
  choice_a text NOT NULL,
  choice_b text NOT NULL,
  choice_c text,
  correct_choice text NOT NULL CHECK (correct_choice IN ('A', 'B', 'C')),
  source_page_start int,
  source_page_end int,
  qdrant_point_id uuid,
  content_sha256 text NOT NULL,
  immutable_version int NOT NULL DEFAULT 1,
  metadata jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (official_exam_paper_id, question_number),
  UNIQUE (content_sha256)
);

CREATE OR REPLACE FUNCTION prevent_official_question_update()
RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'official_questions are immutable; create a superseding record instead';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_official_questions_immutable ON official_questions;
CREATE TRIGGER trg_official_questions_immutable
BEFORE UPDATE OR DELETE ON official_questions
FOR EACH ROW EXECUTE FUNCTION prevent_official_question_update();

CREATE TABLE IF NOT EXISTS official_question_errata (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  official_question_id uuid NOT NULL REFERENCES official_questions(id),
  errata_type text NOT NULL CHECK (errata_type IN ('typo', 'answer_key_correction', 'source_reference', 'other')),
  proposed_by_user_id uuid REFERENCES users(id),
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'rejected')),
  note text NOT NULL,
  replacement_payload jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  reviewed_at timestamptz,
  reviewed_by_user_id uuid REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS ai_explanation_drafts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  official_question_id uuid NOT NULL REFERENCES official_questions(id),
  generated_text text NOT NULL,
  model_provider text NOT NULL,
  model_name text NOT NULL,
  prompt_version text NOT NULL,
  retrieval_snapshot jsonb NOT NULL,
  status text NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft', 'approved', 'rejected', 'superseded')),
  reviewer_user_id uuid REFERENCES users(id),
  review_note text,
  approved_text text,
  created_at timestamptz NOT NULL DEFAULT now(),
  reviewed_at timestamptz
);

CREATE TABLE IF NOT EXISTS approved_explanations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  official_question_id uuid NOT NULL REFERENCES official_questions(id),
  ai_explanation_draft_id uuid NOT NULL REFERENCES ai_explanation_drafts(id),
  explanation_text text NOT NULL,
  qdrant_point_id uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (official_question_id)
);

CREATE TABLE IF NOT EXISTS exam_blueprints (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  name text NOT NULL,
  version int NOT NULL,
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'retired')),
  total_questions int NOT NULL,
  duration_minutes int NOT NULL,
  passing_score int,
  rules jsonb NOT NULL,
  effective_from date,
  effective_to date,
  created_by_user_id uuid REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (exam_track_id, version)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_exam_blueprints_one_active
  ON exam_blueprints(exam_track_id)
  WHERE status = 'active';

CREATE TABLE IF NOT EXISTS exam_blueprint_sections (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  exam_blueprint_id uuid NOT NULL REFERENCES exam_blueprints(id) ON DELETE CASCADE,
  section_key text NOT NULL,
  name text NOT NULL,
  question_count int NOT NULL,
  source_filter jsonb NOT NULL DEFAULT '{}',
  selection_strategy text NOT NULL CHECK (selection_strategy IN ('fixed', 'random', 'weighted_random')),
  sort_order int NOT NULL,
  UNIQUE (exam_blueprint_id, section_key)
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'needs_review')),
  root_path text NOT NULL,
  parser_version text NOT NULL,
  manifest jsonb NOT NULL DEFAULT '{}',
  report jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  started_at timestamptz,
  completed_at timestamptz
);

