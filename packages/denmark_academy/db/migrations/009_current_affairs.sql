-- Current Affairs Articles
CREATE TABLE IF NOT EXISTS current_affairs_articles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  url TEXT NOT NULL UNIQUE,
  source TEXT NOT NULL,
  published_date TIMESTAMPTZ,
  summary TEXT,
  exam_type TEXT CHECK (exam_type IN ('citizenship', 'pr', 'both')),
  topic TEXT,
  is_relevant BOOLEAN DEFAULT FALSE,
  processing_status TEXT DEFAULT 'pending' CHECK (processing_status IN ('pending', 'processed', 'failed', 'skipped')),
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ca_articles_exam_type ON current_affairs_articles(exam_type);
CREATE INDEX IF NOT EXISTS idx_ca_articles_processing_status ON current_affairs_articles(processing_status);
CREATE INDEX IF NOT EXISTS idx_ca_articles_published_date ON current_affairs_articles(published_date DESC);
CREATE INDEX IF NOT EXISTS idx_ca_articles_is_relevant ON current_affairs_articles(is_relevant) WHERE is_relevant = TRUE;

-- Current Affairs Questions
CREATE TABLE IF NOT EXISTS current_affairs_questions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  article_id UUID NOT NULL REFERENCES current_affairs_articles(id) ON DELETE CASCADE,
  question_stem TEXT NOT NULL,
  choice_a TEXT NOT NULL,
  choice_b TEXT NOT NULL,
  choice_c TEXT NOT NULL,
  correct_choice TEXT NOT NULL CHECK (correct_choice IN ('a', 'b', 'c')),
  explanation TEXT NOT NULL,
  difficulty TEXT NOT NULL CHECK (difficulty IN ('easy', 'medium', 'hard')),
  exam_type TEXT NOT NULL CHECK (exam_type IN ('citizenship', 'pr', 'both')),
  topic TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ca_questions_article_id ON current_affairs_questions(article_id);
CREATE INDEX IF NOT EXISTS idx_ca_questions_exam_type ON current_affairs_questions(exam_type);
CREATE INDEX IF NOT EXISTS idx_ca_questions_difficulty ON current_affairs_questions(difficulty);

-- User Practice Sessions for Current Affairs
CREATE TABLE IF NOT EXISTS current_affairs_practice_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID,
  exam_type TEXT NOT NULL,
  difficulty TEXT,
  total_questions INT NOT NULL,
  correct_answers INT NOT NULL DEFAULT 0,
  completed BOOLEAN DEFAULT FALSE,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_ca_sessions_user_id ON current_affairs_practice_sessions(user_id);

-- Track user answers
CREATE TABLE IF NOT EXISTS current_affairs_user_answers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID NOT NULL REFERENCES current_affairs_practice_sessions(id) ON DELETE CASCADE,
  question_id UUID NOT NULL REFERENCES current_affairs_questions(id) ON DELETE CASCADE,
  user_choice TEXT NOT NULL CHECK (user_choice IN ('a', 'b', 'c')),
  is_correct BOOLEAN NOT NULL,
  answered_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ca_answers_session_id ON current_affairs_user_answers(session_id);
