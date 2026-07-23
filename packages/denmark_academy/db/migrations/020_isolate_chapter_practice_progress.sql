-- Give imported chapter-wise practice its own progress namespace.
-- Past-paper progress remains under `past_papers` and is intentionally untouched.
UPDATE user_question_attempts
SET module = 'chapter_practice'
WHERE module = 'ai_generated_mcqs'
  AND question_id LIKE 'chapter:%';

UPDATE user_learning_states
SET module = 'chapter_practice'
WHERE module = 'ai_generated_mcqs'
  AND route LIKE '/revision%';

CREATE INDEX IF NOT EXISTS idx_question_attempt_chapter_practice
  ON user_question_attempts(user_id, track, question_id)
  WHERE module = 'chapter_practice';