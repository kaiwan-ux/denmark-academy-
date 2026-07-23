CREATE TABLE IF NOT EXISTS completed_reading_chapters (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  track text NOT NULL CHECK (track IN ('pr', 'citizenship')),
  chapter_key text NOT NULL,
  chapter_title text NOT NULL,
  page_number integer NOT NULL,
  total_chapters integer NOT NULL CHECK (total_chapters > 0),
  route text NOT NULL DEFAULT '/reader/demo',
  completed_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(user_id, track, chapter_key)
);
CREATE INDEX IF NOT EXISTS idx_completed_reading_user_track
  ON completed_reading_chapters(user_id, track, completed_at DESC);

