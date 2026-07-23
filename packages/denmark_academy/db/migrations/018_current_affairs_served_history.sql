-- Durable per-user Current Affairs delivery history.
CREATE TABLE IF NOT EXISTS current_affairs_user_progress (
  user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  cycle INTEGER NOT NULL DEFAULT 1 CHECK (cycle > 0),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS current_affairs_served_questions (
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  question_id UUID NOT NULL,
  question_fingerprint TEXT NOT NULL,
  cycle INTEGER NOT NULL CHECK (cycle > 0),
  session_id UUID NOT NULL REFERENCES current_affairs_practice_sessions(id) ON DELETE CASCADE,
  served_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, question_id, cycle)
);

CREATE INDEX IF NOT EXISTS idx_ca_served_user_cycle
  ON current_affairs_served_questions(user_id, cycle, served_at DESC);

CREATE INDEX IF NOT EXISTS idx_ca_served_session
  ON current_affairs_served_questions(session_id);

CREATE INDEX IF NOT EXISTS idx_ca_served_fingerprint
  ON current_affairs_served_questions(user_id, question_fingerprint);

CREATE INDEX IF NOT EXISTS idx_ca_sessions_user_started
  ON current_affairs_practice_sessions(user_id, started_at DESC);

-- Preserve resumability for sessions created before server-side ownership/history existed.
UPDATE current_affairs_practice_sessions session
SET user_id = state.user_id
FROM user_learning_states state
WHERE session.user_id IS NULL
  AND state.module = 'current_affairs'
  AND state.state->>'session_id' = session.id::text;

UPDATE current_affairs_practice_sessions session
SET user_id = attempt.user_id
FROM user_question_attempts attempt
WHERE session.user_id IS NULL
  AND attempt.module = 'current_affairs'
  AND CASE
        WHEN attempt.session_key ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        THEN attempt.session_key::uuid
      END = session.id;

INSERT INTO current_affairs_user_progress(user_id)
SELECT DISTINCT user_id
FROM current_affairs_practice_sessions
WHERE user_id IS NOT NULL
ON CONFLICT(user_id) DO NOTHING;

INSERT INTO current_affairs_served_questions(
  user_id, question_id, question_fingerprint, cycle, session_id, served_at
)
SELECT state.user_id,
       question.id,
       lower(regexp_replace(question.question_stem, '[^[:alnum:]_]+', ' ', 'g')),
       1,
       session.id,
       session.started_at
FROM user_learning_states state
JOIN current_affairs_practice_sessions session
  ON state.state->>'session_id' = session.id::text AND session.user_id = state.user_id
CROSS JOIN LATERAL jsonb_array_elements(
  CASE WHEN jsonb_typeof(state.state->'questions') = 'array'
       THEN state.state->'questions' ELSE '[]'::jsonb END
) item
JOIN current_affairs_questions question ON question.id::text = item->>'id'
WHERE state.module = 'current_affairs'
  AND jsonb_typeof(state.state->'questions') = 'array'
ON CONFLICT(user_id, question_id, cycle) DO NOTHING;

INSERT INTO current_affairs_served_questions(
  user_id, question_id, question_fingerprint, cycle, session_id, served_at
)
SELECT attempt.user_id,
       question.id,
       lower(regexp_replace(question.question_stem, '[^[:alnum:]_]+', ' ', 'g')),
       1,
       session.id,
       attempt.attempted_at
FROM user_question_attempts attempt
JOIN current_affairs_practice_sessions session
  ON session.user_id = attempt.user_id
 AND CASE
       WHEN attempt.session_key ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
       THEN attempt.session_key::uuid
     END = session.id
JOIN current_affairs_questions question ON question.id::text = attempt.question_id
WHERE attempt.module = 'current_affairs'
ON CONFLICT(user_id, question_id, cycle) DO NOTHING;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'fk_ca_session_user'
  ) THEN
    ALTER TABLE current_affairs_practice_sessions
      ADD CONSTRAINT fk_ca_session_user
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
  END IF;
END $$;
