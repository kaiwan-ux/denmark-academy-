ALTER TABLE users
  ADD COLUMN IF NOT EXISTS display_name text,
  ADD COLUMN IF NOT EXISTS first_name text,
  ADD COLUMN IF NOT EXISTS last_name text,
  ADD COLUMN IF NOT EXISTS avatar_url text,
  ADD COLUMN IF NOT EXISTS preferred_track text CHECK (preferred_track IS NULL OR preferred_track IN ('pr', 'citizenship')),
  ADD COLUMN IF NOT EXISTS timezone text NOT NULL DEFAULT 'Europe/Copenhagen',
  ADD COLUMN IF NOT EXISTS email_verified_at timestamptz,
  ADD COLUMN IF NOT EXISTS last_login_at timestamptz,
  ADD COLUMN IF NOT EXISTS failed_login_count integer NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS locked_until timestamptz;

CREATE TABLE IF NOT EXISTS auth_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash text NOT NULL UNIQUE,
  remember_me boolean NOT NULL DEFAULT false,
  user_agent text,
  ip_address inet,
  created_at timestamptz NOT NULL DEFAULT now(),
  last_seen_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz
);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_active ON auth_sessions(user_id, expires_at DESC) WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS password_reset_tokens (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash text NOT NULL UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  used_at timestamptz
);
CREATE INDEX IF NOT EXISTS idx_password_reset_active ON password_reset_tokens(user_id, expires_at DESC) WHERE used_at IS NULL;

CREATE TABLE IF NOT EXISTS user_learning_states (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  module text NOT NULL,
  state_key text NOT NULL DEFAULT 'default',
  route text NOT NULL,
  entity_id text,
  title text,
  completion_percent numeric(5,2) NOT NULL DEFAULT 0 CHECK (completion_percent BETWEEN 0 AND 100),
  state jsonb NOT NULL DEFAULT '{}',
  started_at timestamptz NOT NULL DEFAULT now(),
  last_activity_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  UNIQUE(user_id, module, state_key)
);
CREATE INDEX IF NOT EXISTS idx_learning_states_continue ON user_learning_states(user_id, last_activity_at DESC);

CREATE TABLE IF NOT EXISTS user_question_attempts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  module text NOT NULL,
  question_id text NOT NULL,
  session_key text,
  selected_choice text,
  correct_choice text,
  is_correct boolean NOT NULL,
  topic text,
  track text,
  time_spent_seconds integer NOT NULL DEFAULT 0 CHECK (time_spent_seconds >= 0),
  metadata jsonb NOT NULL DEFAULT '{}',
  client_attempt_id text,
  attempted_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_question_attempt_client_id
  ON user_question_attempts(user_id, client_attempt_id) WHERE client_attempt_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_question_attempt_user_module ON user_question_attempts(user_id, module, attempted_at DESC);
CREATE INDEX IF NOT EXISTS idx_question_attempt_seen ON user_question_attempts(user_id, module, question_id);

CREATE TABLE IF NOT EXISTS saved_bookmarks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  module text NOT NULL,
  entity_id text NOT NULL,
  title text,
  route text,
  metadata jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(user_id, module, entity_id)
);
CREATE INDEX IF NOT EXISTS idx_saved_bookmarks_user ON saved_bookmarks(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS saved_notes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  module text NOT NULL,
  entity_id text NOT NULL,
  body text NOT NULL,
  route text,
  anchor jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(user_id, module, entity_id)
);
CREATE INDEX IF NOT EXISTS idx_saved_notes_user ON saved_notes(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS completed_mock_exams (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  track text NOT NULL,
  score integer NOT NULL,
  total_questions integer NOT NULL CHECK (total_questions > 0),
  correct_answers integer NOT NULL DEFAULT 0,
  incorrect_answers integer NOT NULL DEFAULT 0,
  duration_seconds integer NOT NULL DEFAULT 0,
  answers jsonb NOT NULL DEFAULT '[]',
  insights jsonb NOT NULL DEFAULT '{}',
  completed_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_completed_mocks_user ON completed_mock_exams(user_id, completed_at DESC);

CREATE TABLE IF NOT EXISTS user_activity_log (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  module text NOT NULL,
  activity_type text NOT NULL,
  duration_seconds integer NOT NULL DEFAULT 0 CHECK (duration_seconds >= 0),
  route text,
  metadata jsonb NOT NULL DEFAULT '{}',
  occurred_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_user_activity_timeline ON user_activity_log(user_id, occurred_at DESC);

