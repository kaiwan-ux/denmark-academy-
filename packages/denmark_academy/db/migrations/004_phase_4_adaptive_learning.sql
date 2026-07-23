CREATE TABLE IF NOT EXISTS learning_concepts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  course_id uuid REFERENCES courses(id) ON DELETE CASCADE,
  chapter_id uuid REFERENCES course_chapters(id) ON DELETE SET NULL,
  topic_id uuid REFERENCES course_topics(id) ON DELETE SET NULL,
  parent_concept_id uuid REFERENCES learning_concepts(id) ON DELETE SET NULL,
  name text NOT NULL,
  slug text NOT NULL,
  description text,
  sort_order int NOT NULL DEFAULT 0,
  metadata jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (exam_track_id, slug)
);

CREATE TABLE IF NOT EXISTS question_concept_links (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  concept_id uuid NOT NULL REFERENCES learning_concepts(id) ON DELETE CASCADE,
  official_question_id uuid REFERENCES official_questions(id),
  ai_generated_question_id uuid REFERENCES ai_generated_questions(id),
  weight numeric(5,2) NOT NULL DEFAULT 1,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (official_question_id IS NOT NULL OR ai_generated_question_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_question_concept_links_concept ON question_concept_links(concept_id);

CREATE TABLE IF NOT EXISTS student_learning_profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  reading_progress numeric(5,2) NOT NULL DEFAULT 0,
  overall_accuracy numeric(5,2) NOT NULL DEFAULT 0,
  average_mastery numeric(5,2) NOT NULL DEFAULT 0,
  confidence_score numeric(5,2) NOT NULL DEFAULT 50,
  study_frequency_days numeric(6,2) NOT NULL DEFAULT 0,
  preferred_difficulty text NOT NULL DEFAULT 'medium' CHECK (preferred_difficulty IN ('easy', 'medium', 'hard')),
  learning_velocity numeric(8,2) NOT NULL DEFAULT 0,
  time_spent_seconds int NOT NULL DEFAULT 0,
  revision_accuracy numeric(5,2) NOT NULL DEFAULT 0,
  last_interaction_at timestamptz,
  profile jsonb NOT NULL DEFAULT '{}',
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, exam_track_id)
);

CREATE TABLE IF NOT EXISTS student_concept_mastery (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  concept_id uuid NOT NULL REFERENCES learning_concepts(id) ON DELETE CASCADE,
  mastery_score numeric(5,2) NOT NULL DEFAULT 0 CHECK (mastery_score >= 0 AND mastery_score <= 100),
  confidence_score numeric(5,2) NOT NULL DEFAULT 50 CHECK (confidence_score >= 0 AND confidence_score <= 100),
  attempts int NOT NULL DEFAULT 0,
  correct_attempts int NOT NULL DEFAULT 0,
  incorrect_attempts int NOT NULL DEFAULT 0,
  last_practiced_at timestamptz,
  decay_factor numeric(6,4) NOT NULL DEFAULT 0.015,
  metadata jsonb NOT NULL DEFAULT '{}',
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, concept_id)
);

CREATE INDEX IF NOT EXISTS idx_student_concept_mastery_user_track ON student_concept_mastery(user_id, exam_track_id, mastery_score);

CREATE TABLE IF NOT EXISTS adaptive_difficulty_states (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  concept_id uuid REFERENCES learning_concepts(id) ON DELETE CASCADE,
  current_difficulty text NOT NULL DEFAULT 'medium' CHECK (current_difficulty IN ('easy', 'medium', 'hard')),
  target_difficulty text NOT NULL DEFAULT 'medium' CHECK (target_difficulty IN ('easy', 'medium', 'hard')),
  reason jsonb NOT NULL DEFAULT '{}',
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, exam_track_id, concept_id)
);

CREATE TABLE IF NOT EXISTS spaced_repetition_policies (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  policy_key text NOT NULL UNIQUE,
  name text NOT NULL,
  intervals_days int[] NOT NULL,
  algorithm text NOT NULL DEFAULT 'default_ladder',
  is_active boolean NOT NULL DEFAULT false,
  config jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO spaced_repetition_policies (policy_key, name, intervals_days, is_active)
VALUES ('default_ladder_v1', 'Default ladder', ARRAY[1, 3, 7, 14, 30], true)
ON CONFLICT (policy_key) DO NOTHING;

CREATE TABLE IF NOT EXISTS spaced_repetition_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  concept_id uuid REFERENCES learning_concepts(id) ON DELETE SET NULL,
  official_question_id uuid REFERENCES official_questions(id),
  ai_generated_question_id uuid REFERENCES ai_generated_questions(id),
  policy_id uuid REFERENCES spaced_repetition_policies(id),
  interval_index int NOT NULL DEFAULT 0,
  due_at timestamptz NOT NULL DEFAULT now(),
  status text NOT NULL DEFAULT 'due' CHECK (status IN ('due', 'completed', 'snoozed', 'retired')),
  ease_factor numeric(6,3) NOT NULL DEFAULT 2.5,
  repetitions int NOT NULL DEFAULT 0,
  lapses int NOT NULL DEFAULT 0,
  last_result text CHECK (last_result IN ('correct', 'incorrect', 'low_confidence')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (official_question_id IS NOT NULL OR ai_generated_question_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_spaced_repetition_due ON spaced_repetition_items(user_id, exam_track_id, status, due_at);

CREATE TABLE IF NOT EXISTS adaptive_recommendations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  recommendation_type text NOT NULL CHECK (recommendation_type IN ('read', 'practice', 'revise', 'mock', 'rest', 'review_notes')),
  title text NOT NULL,
  rationale text NOT NULL,
  priority int NOT NULL DEFAULT 50,
  target_entity_type text,
  target_entity_id uuid,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'dismissed', 'expired')),
  expires_at timestamptz,
  metadata jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_adaptive_recommendations_active ON adaptive_recommendations(user_id, exam_track_id, status, priority DESC);

CREATE TABLE IF NOT EXISTS pass_predictions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  pass_probability numeric(5,2) NOT NULL CHECK (pass_probability >= 0 AND pass_probability <= 100),
  confidence numeric(5,2) NOT NULL CHECK (confidence >= 0 AND confidence <= 100),
  readiness_level text NOT NULL CHECK (readiness_level IN ('not_ready', 'developing', 'near_ready', 'ready')),
  explainability jsonb NOT NULL DEFAULT '{}',
  model_version text NOT NULL DEFAULT 'pass-predictor-v1',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pass_predictions_user_track ON pass_predictions(user_id, exam_track_id, created_at DESC);

CREATE TABLE IF NOT EXISTS exam_readiness_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  readiness_score numeric(5,2) NOT NULL,
  coverage_score numeric(5,2) NOT NULL,
  mastery_score numeric(5,2) NOT NULL,
  mock_score numeric(5,2) NOT NULL,
  revision_score numeric(5,2) NOT NULL,
  consistency_score numeric(5,2) NOT NULL,
  blockers jsonb NOT NULL DEFAULT '[]',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS learning_analytics_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  period_start date NOT NULL,
  period_end date NOT NULL,
  study_seconds int NOT NULL DEFAULT 0,
  questions_answered int NOT NULL DEFAULT 0,
  accuracy numeric(5,2) NOT NULL DEFAULT 0,
  mastery_delta numeric(6,2) NOT NULL DEFAULT 0,
  revision_completion numeric(5,2) NOT NULL DEFAULT 0,
  improvement_rate numeric(6,2) NOT NULL DEFAULT 0,
  trends jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS motivation_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  event_key text NOT NULL,
  points int NOT NULL DEFAULT 0,
  badge_key text,
  title text NOT NULL,
  description text,
  metadata jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS adaptive_mock_blueprints (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  exam_blueprint_id uuid NOT NULL REFERENCES exam_blueprints(id),
  official_percent int NOT NULL DEFAULT 70 CHECK (official_percent >= 0 AND official_percent <= 100),
  ai_percent int NOT NULL DEFAULT 30 CHECK (ai_percent >= 0 AND ai_percent <= 100),
  weak_concept_weight numeric(5,2) NOT NULL DEFAULT 1.5,
  difficulty_progression jsonb NOT NULL DEFAULT '{}',
  generated_plan jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (official_percent + ai_percent = 100)
);
