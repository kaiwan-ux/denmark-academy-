ALTER TABLE current_affairs_questions
  ADD COLUMN IF NOT EXISTS learning_objective text,
  ADD COLUMN IF NOT EXISTS quality_score numeric(5,2) NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS expires_at timestamptz;

UPDATE current_affairs_questions
SET expires_at = created_at + interval '14 days'
WHERE expires_at IS NULL;

ALTER TABLE current_affairs_questions
  ALTER COLUMN expires_at SET DEFAULT (now() + interval '14 days'),
  ALTER COLUMN expires_at SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ca_questions_active_priority
  ON current_affairs_questions(expires_at, difficulty, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ca_articles_priority
  ON current_affairs_articles(published_date DESC, is_relevant);

DELETE FROM current_affairs_user_answers duplicate
USING current_affairs_user_answers canonical
WHERE duplicate.session_id = canonical.session_id
  AND duplicate.question_id = canonical.question_id
  AND duplicate.id > canonical.id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_ca_answer_session_question_unique
  ON current_affairs_user_answers(session_id, question_id);
