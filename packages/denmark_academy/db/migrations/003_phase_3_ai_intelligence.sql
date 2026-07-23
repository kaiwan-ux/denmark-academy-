CREATE TABLE IF NOT EXISTS ai_providers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  provider_key text NOT NULL UNIQUE CHECK (provider_key IN ('ollama', 'openai', 'anthropic', 'gemini', 'grok', 'disabled')),
  display_name text NOT NULL,
  is_enabled boolean NOT NULL DEFAULT false,
  default_model text,
  config jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO ai_providers (provider_key, display_name, is_enabled, default_model)
VALUES
  ('disabled', 'Disabled deterministic provider', true, 'disabled-local'),
  ('ollama', 'Ollama', false, NULL),
  ('openai', 'OpenAI', false, NULL),
  ('anthropic', 'Anthropic', false, NULL),
  ('gemini', 'Gemini', false, NULL),
  ('grok', 'Grok / Groq OpenAI-compatible', false, NULL)
ON CONFLICT (provider_key) DO NOTHING;

CREATE TABLE IF NOT EXISTS ai_prompt_templates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  template_key text NOT NULL,
  version int NOT NULL,
  purpose text NOT NULL CHECK (purpose IN (
    'tutor', 'explanation', 'similar_question', 'mock_question', 'recommendation',
    'revision', 'flashcard', 'notes', 'quiz', 'study_plan', 'evaluation'
  )),
  system_template text NOT NULL,
  user_template text NOT NULL,
  output_schema jsonb NOT NULL DEFAULT '{}',
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'retired')),
  created_by_user_id uuid REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (template_key, version)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_prompt_templates_one_active
  ON ai_prompt_templates(template_key)
  WHERE status = 'active';

CREATE TABLE IF NOT EXISTS ai_cache_entries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  cache_key text NOT NULL UNIQUE,
  provider_key text NOT NULL,
  model text NOT NULL,
  purpose text NOT NULL,
  request_hash text NOT NULL,
  response_payload jsonb NOT NULL,
  token_usage jsonb NOT NULL DEFAULT '{}',
  expires_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ai_retrieval_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  query text NOT NULL,
  retrieval_strategy text NOT NULL DEFAULT 'hybrid_rag',
  filters jsonb NOT NULL DEFAULT '{}',
  sources jsonb NOT NULL DEFAULT '[]',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ai_prompt_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  user_id uuid REFERENCES users(id),
  prompt_template_id uuid REFERENCES ai_prompt_templates(id),
  retrieval_snapshot_id uuid REFERENCES ai_retrieval_snapshots(id),
  provider_key text NOT NULL,
  model text NOT NULL,
  purpose text NOT NULL,
  prompt_messages jsonb NOT NULL,
  response_payload jsonb NOT NULL DEFAULT '{}',
  token_usage jsonb NOT NULL DEFAULT '{}',
  cache_hit boolean NOT NULL DEFAULT false,
  status text NOT NULL DEFAULT 'completed' CHECK (status IN ('pending', 'completed', 'failed')),
  error_message text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ai_content_artifacts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  user_id uuid REFERENCES users(id),
  artifact_type text NOT NULL CHECK (artifact_type IN (
    'explanation', 'similar_question', 'mock_question', 'recommendation', 'revision_plan',
    'flashcard', 'notes', 'quiz', 'study_plan', 'tutor_response', 'summary'
  )),
  source_entity_type text,
  source_entity_id uuid,
  prompt_run_id uuid REFERENCES ai_prompt_runs(id),
  title text,
  content jsonb NOT NULL,
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'needs_review', 'approved', 'rejected', 'published', 'archived')),
  quality_score numeric(5,2),
  metadata jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  reviewed_at timestamptz,
  reviewed_by_user_id uuid REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_ai_content_artifacts_track_type
  ON ai_content_artifacts(exam_track_id, artifact_type, status);

CREATE TABLE IF NOT EXISTS ai_generated_questions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  artifact_id uuid REFERENCES ai_content_artifacts(id),
  stem text NOT NULL,
  choice_a text NOT NULL,
  choice_b text NOT NULL,
  choice_c text,
  correct_choice text NOT NULL CHECK (correct_choice IN ('A', 'B', 'C')),
  explanation text,
  difficulty text NOT NULL DEFAULT 'medium' CHECK (difficulty IN ('easy', 'medium', 'hard')),
  chapter_id uuid REFERENCES course_chapters(id),
  topic_id uuid REFERENCES course_topics(id),
  source_snapshot_id uuid REFERENCES ai_retrieval_snapshots(id),
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'needs_review', 'approved', 'rejected', 'published', 'archived')),
  quality_score numeric(5,2),
  metadata jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ai_generated_questions_track_status
  ON ai_generated_questions(exam_track_id, status, difficulty);

CREATE TABLE IF NOT EXISTS ai_mock_exam_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  practice_session_id uuid REFERENCES practice_sessions(id) ON DELETE CASCADE,
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  source_kind text NOT NULL CHECK (source_kind IN ('official', 'ai')),
  official_question_id uuid REFERENCES official_questions(id),
  ai_generated_question_id uuid REFERENCES ai_generated_questions(id),
  question_order int NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}',
  CHECK (
    (source_kind = 'official' AND official_question_id IS NOT NULL AND ai_generated_question_id IS NULL)
    OR (source_kind = 'ai' AND ai_generated_question_id IS NOT NULL AND official_question_id IS NULL)
  )
);

CREATE TABLE IF NOT EXISTS ai_conversation_threads (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  title text,
  learning_objective text,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
  memory_summary text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ai_conversation_messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  thread_id uuid NOT NULL REFERENCES ai_conversation_threads(id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
  content text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ai_evaluations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  artifact_id uuid REFERENCES ai_content_artifacts(id),
  ai_generated_question_id uuid REFERENCES ai_generated_questions(id),
  evaluator_version text NOT NULL,
  groundedness_score numeric(5,2) NOT NULL,
  exam_alignment_score numeric(5,2) NOT NULL,
  hallucination_risk numeric(5,2) NOT NULL,
  duplication_score numeric(5,2) NOT NULL,
  quality_score numeric(5,2) NOT NULL,
  decision text NOT NULL CHECK (decision IN ('approve', 'needs_review', 'reject')),
  findings jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ai_analytics_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  user_id uuid REFERENCES users(id),
  event_type text NOT NULL,
  provider_key text,
  model text,
  purpose text,
  latency_ms int,
  token_usage jsonb NOT NULL DEFAULT '{}',
  cost_estimate jsonb NOT NULL DEFAULT '{}',
  metadata jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ai_study_plans (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  artifact_id uuid REFERENCES ai_content_artifacts(id),
  plan_start_date date NOT NULL,
  plan_end_date date NOT NULL,
  plan jsonb NOT NULL,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'archived')),
  created_at timestamptz NOT NULL DEFAULT now()
);

