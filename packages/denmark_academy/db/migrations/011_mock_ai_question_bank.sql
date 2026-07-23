CREATE TABLE IF NOT EXISTS mock_ai_question_bank (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  provider_key text NOT NULL CHECK (provider_key IN ('gemini', 'grok')),
  section text NOT NULL CHECK (section IN ('knowledge', 'current_affairs', 'danish_values')),
  stem text NOT NULL,
  choice_a text NOT NULL,
  choice_b text NOT NULL,
  choice_c text NOT NULL,
  choice_d text,
  correct_choice text NOT NULL CHECK (correct_choice IN ('A', 'B', 'C', 'D')),
  explanation text,
  difficulty text NOT NULL DEFAULT 'hard' CHECK (difficulty IN ('easy', 'medium', 'hard')),
  status text NOT NULL DEFAULT 'needs_review' CHECK (status IN ('needs_review', 'approved', 'rejected', 'archived')),
  quality_score numeric(5,2),
  content_sha256 text NOT NULL UNIQUE,
  metadata jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  reviewed_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_mock_ai_question_bank_track_status
  ON mock_ai_question_bank(exam_track_id, status, section, difficulty);