-- Runtime guard for current-affairs generated question deduplication.
-- Keeps repeated scheduled/manual fetches from storing the same question wording again.
CREATE UNIQUE INDEX IF NOT EXISTS idx_ca_questions_exam_stem_unique
ON current_affairs_questions (
  exam_type,
  md5(lower(regexp_replace(question_stem, '\s+', ' ', 'g')))
);
