CREATE TABLE IF NOT EXISTS courses (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  title text NOT NULL,
  description text,
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
  sort_order int NOT NULL DEFAULT 0,
  estimated_minutes int,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (exam_track_id)
);

CREATE TABLE IF NOT EXISTS course_chapters (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  course_id uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  title text NOT NULL,
  summary text,
  slug text NOT NULL,
  sort_order int NOT NULL,
  estimated_minutes int,
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (course_id, slug),
  UNIQUE (course_id, sort_order)
);

CREATE TABLE IF NOT EXISTS course_topics (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  chapter_id uuid NOT NULL REFERENCES course_chapters(id) ON DELETE CASCADE,
  course_id uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  title text NOT NULL,
  summary text,
  slug text NOT NULL,
  sort_order int NOT NULL,
  estimated_minutes int,
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (chapter_id, slug),
  UNIQUE (chapter_id, sort_order)
);

CREATE TABLE IF NOT EXISTS course_subtopics (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  topic_id uuid NOT NULL REFERENCES course_topics(id) ON DELETE CASCADE,
  chapter_id uuid NOT NULL REFERENCES course_chapters(id) ON DELETE CASCADE,
  course_id uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  title text NOT NULL,
  slug text NOT NULL,
  sort_order int NOT NULL,
  estimated_minutes int,
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (topic_id, slug),
  UNIQUE (topic_id, sort_order)
);

CREATE TABLE IF NOT EXISTS learning_units (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  course_id uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  chapter_id uuid REFERENCES course_chapters(id) ON DELETE SET NULL,
  topic_id uuid REFERENCES course_topics(id) ON DELETE SET NULL,
  subtopic_id uuid REFERENCES course_subtopics(id) ON DELETE SET NULL,
  source_document_id uuid REFERENCES source_documents(id),
  document_chunk_id uuid REFERENCES document_chunks(id),
  title text NOT NULL,
  body text NOT NULL,
  reading_level text,
  estimated_minutes int,
  sort_order int NOT NULL DEFAULT 0,
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
  metadata jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_learning_units_track ON learning_units(exam_track_id);
CREATE INDEX IF NOT EXISTS idx_learning_units_topic ON learning_units(topic_id);

CREATE TABLE IF NOT EXISTS question_categories (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  name text NOT NULL,
  slug text NOT NULL,
  description text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (exam_track_id, slug)
);

CREATE TABLE IF NOT EXISTS official_question_classifications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  official_question_id uuid NOT NULL REFERENCES official_questions(id),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  chapter_id uuid REFERENCES course_chapters(id),
  topic_id uuid REFERENCES course_topics(id),
  subtopic_id uuid REFERENCES course_subtopics(id),
  category_id uuid REFERENCES question_categories(id),
  difficulty text NOT NULL DEFAULT 'medium' CHECK (difficulty IN ('easy', 'medium', 'hard')),
  metadata jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (official_question_id)
);

CREATE INDEX IF NOT EXISTS idx_question_classifications_topic
  ON official_question_classifications(exam_track_id, topic_id, difficulty);

CREATE TABLE IF NOT EXISTS student_course_enrollments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  course_id uuid NOT NULL REFERENCES courses(id),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'paused')),
  enrolled_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  UNIQUE (user_id, course_id)
);

CREATE TABLE IF NOT EXISTS reading_progress (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  learning_unit_id uuid NOT NULL REFERENCES learning_units(id) ON DELETE CASCADE,
  percent_complete numeric(5,2) NOT NULL DEFAULT 0 CHECK (percent_complete >= 0 AND percent_complete <= 100),
  last_position jsonb NOT NULL DEFAULT '{}',
  time_spent_seconds int NOT NULL DEFAULT 0,
  completed_at timestamptz,
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, learning_unit_id)
);

CREATE TABLE IF NOT EXISTS user_bookmarks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  entity_type text NOT NULL CHECK (entity_type IN ('learning_unit', 'official_question', 'official_exam_paper', 'chapter', 'topic')),
  entity_id uuid NOT NULL,
  label text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, entity_type, entity_id)
);

CREATE TABLE IF NOT EXISTS user_notes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  entity_type text NOT NULL CHECK (entity_type IN ('learning_unit', 'official_question', 'official_exam_paper', 'chapter', 'topic')),
  entity_id uuid NOT NULL,
  body text NOT NULL,
  anchor jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_highlights (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  learning_unit_id uuid NOT NULL REFERENCES learning_units(id) ON DELETE CASCADE,
  selected_text text NOT NULL,
  color text NOT NULL DEFAULT 'yellow',
  anchor jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS practice_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  mode text NOT NULL CHECK (mode IN (
    'chapter_practice', 'topic_practice', 'random_practice', 'official_question_practice',
    'study_mode', 'exam_mode', 'review_mode', 'wrong_question_practice',
    'bookmarked_question_practice', 'past_paper', 'mock_exam'
  )),
  status text NOT NULL DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'submitted', 'abandoned')),
  source_type text NOT NULL CHECK (source_type IN ('chapter', 'topic', 'question_set', 'past_paper', 'blueprint', 'revision')),
  source_id uuid,
  official_exam_paper_id uuid REFERENCES official_exam_papers(id),
  exam_blueprint_id uuid REFERENCES exam_blueprints(id),
  total_questions int NOT NULL,
  correct_count int NOT NULL DEFAULT 0,
  incorrect_count int NOT NULL DEFAULT 0,
  unanswered_count int NOT NULL DEFAULT 0,
  score_percent numeric(5,2),
  duration_seconds int NOT NULL DEFAULT 0,
  started_at timestamptz NOT NULL DEFAULT now(),
  submitted_at timestamptz,
  metadata jsonb NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS practice_session_questions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  practice_session_id uuid NOT NULL REFERENCES practice_sessions(id) ON DELETE CASCADE,
  official_question_id uuid NOT NULL REFERENCES official_questions(id),
  question_order int NOT NULL,
  selected_choice text CHECK (selected_choice IN ('A', 'B', 'C')),
  is_correct boolean,
  answered_at timestamptz,
  time_spent_seconds int NOT NULL DEFAULT 0,
  marked_for_review boolean NOT NULL DEFAULT false,
  UNIQUE (practice_session_id, question_order),
  UNIQUE (practice_session_id, official_question_id)
);

CREATE TABLE IF NOT EXISTS revision_queue_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  official_question_id uuid NOT NULL REFERENCES official_questions(id),
  reason text NOT NULL CHECK (reason IN ('wrong_answer', 'bookmarked', 'manual', 'weak_topic')),
  status text NOT NULL DEFAULT 'due' CHECK (status IN ('due', 'completed', 'snoozed')),
  due_at timestamptz NOT NULL DEFAULT now(),
  attempts int NOT NULL DEFAULT 0,
  last_seen_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, official_question_id, reason)
);

CREATE TABLE IF NOT EXISTS study_activity_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  event_type text NOT NULL,
  entity_type text,
  entity_id uuid,
  duration_seconds int NOT NULL DEFAULT 0,
  metadata jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_study_activity_user_track_date
  ON study_activity_events(user_id, exam_track_id, created_at DESC);

CREATE TABLE IF NOT EXISTS user_achievements (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  achievement_key text NOT NULL,
  title text NOT NULL,
  description text,
  earned_at timestamptz NOT NULL DEFAULT now(),
  metadata jsonb NOT NULL DEFAULT '{}',
  UNIQUE (user_id, exam_track_id, achievement_key)
);

CREATE TABLE IF NOT EXISTS user_streaks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  current_streak_days int NOT NULL DEFAULT 0,
  longest_streak_days int NOT NULL DEFAULT 0,
  last_activity_date date,
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, exam_track_id)
);

CREATE TABLE IF NOT EXISTS exam_countdowns (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  target_exam_date date NOT NULL,
  label text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, exam_track_id)
);

CREATE TABLE IF NOT EXISTS admin_publish_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_user_id uuid REFERENCES users(id),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  entity_type text NOT NULL,
  entity_id uuid NOT NULL,
  from_status text,
  to_status text NOT NULL,
  note text,
  created_at timestamptz NOT NULL DEFAULT now()
);
