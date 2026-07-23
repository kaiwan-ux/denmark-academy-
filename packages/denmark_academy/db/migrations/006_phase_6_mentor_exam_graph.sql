CREATE TABLE IF NOT EXISTS graph_nodes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  graph_scope text NOT NULL CHECK (graph_scope IN ('knowledge', 'student_learning')),
  node_type text NOT NULL,
  source_table text,
  source_id uuid,
  exam_track_id uuid REFERENCES exam_tracks(id),
  user_id uuid REFERENCES users(id),
  stable_key text NOT NULL UNIQUE,
  label text NOT NULL,
  properties jsonb NOT NULL DEFAULT '{}',
  neo4j_element_id text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_graph_nodes_scope_type ON graph_nodes(graph_scope, node_type);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_track ON graph_nodes(exam_track_id, node_type);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_user ON graph_nodes(user_id, graph_scope);

CREATE TABLE IF NOT EXISTS graph_relationships (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  graph_scope text NOT NULL CHECK (graph_scope IN ('knowledge', 'student_learning', 'cross_graph')),
  relationship_type text NOT NULL,
  from_node_id uuid NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE,
  to_node_id uuid NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE,
  weight numeric(8,4) NOT NULL DEFAULT 1,
  confidence numeric(5,2) NOT NULL DEFAULT 100,
  properties jsonb NOT NULL DEFAULT '{}',
  neo4j_element_id text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (relationship_type, from_node_id, to_node_id)
);

CREATE INDEX IF NOT EXISTS idx_graph_relationships_type ON graph_relationships(relationship_type);
CREATE INDEX IF NOT EXISTS idx_graph_relationships_from ON graph_relationships(from_node_id);
CREATE INDEX IF NOT EXISTS idx_graph_relationships_to ON graph_relationships(to_node_id);

CREATE TABLE IF NOT EXISTS graph_sync_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_type text NOT NULL CHECK (event_type IN ('upsert_node', 'upsert_relationship', 'delete_node', 'delete_relationship', 'full_rebuild')),
  entity_type text NOT NULL,
  entity_id uuid,
  payload jsonb NOT NULL DEFAULT '{}',
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
  attempts int NOT NULL DEFAULT 0,
  error_message text,
  created_at timestamptz NOT NULL DEFAULT now(),
  processed_at timestamptz
);

CREATE TABLE IF NOT EXISTS graph_saved_views (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES users(id),
  exam_track_id uuid REFERENCES exam_tracks(id),
  name text NOT NULL,
  description text,
  filters jsonb NOT NULL DEFAULT '{}',
  layout jsonb NOT NULL DEFAULT '{}',
  is_shared boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mentor_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  goal text,
  available_minutes int,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'archived')),
  graph_context jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mentor_recommendations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  mentor_session_id uuid REFERENCES mentor_sessions(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES users(id),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  recommendation_type text NOT NULL CHECK (recommendation_type IN ('study_plan', 'revision', 'practice', 'mock', 'motivation', 'learning_path')),
  title text NOT NULL,
  rationale text NOT NULL,
  minutes int,
  priority int NOT NULL DEFAULT 50,
  graph_evidence jsonb NOT NULL DEFAULT '{}',
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'accepted', 'completed', 'dismissed')),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS exam_simulation_configs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES users(id),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  name text NOT NULL,
  mode text NOT NULL CHECK (mode IN ('official', 'ai', 'mixed', 'topic', 'weak_topic', 'current_affairs', 'custom', 'adaptive', 'official_replay')),
  difficulty text NOT NULL DEFAULT 'official' CHECK (difficulty IN ('easy', 'medium', 'official', 'hard', 'adaptive')),
  exam_blueprint_id uuid REFERENCES exam_blueprints(id),
  timer_seconds int,
  official_percent int NOT NULL DEFAULT 100 CHECK (official_percent >= 0 AND official_percent <= 100),
  ai_percent int NOT NULL DEFAULT 0 CHECK (ai_percent >= 0 AND ai_percent <= 100),
  filters jsonb NOT NULL DEFAULT '{}',
  accessibility jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (official_percent + ai_percent = 100)
);

CREATE TABLE IF NOT EXISTS exam_simulation_attempts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  config_id uuid REFERENCES exam_simulation_configs(id),
  practice_session_id uuid REFERENCES practice_sessions(id),
  user_id uuid NOT NULL REFERENCES users(id),
  exam_track_id uuid NOT NULL REFERENCES exam_tracks(id),
  status text NOT NULL DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'paused', 'submitted', 'abandoned')),
  auto_save_state jsonb NOT NULL DEFAULT '{}',
  started_at timestamptz NOT NULL DEFAULT now(),
  submitted_at timestamptz,
  analysis jsonb NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS exam_post_submission_reports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  exam_simulation_attempt_id uuid NOT NULL REFERENCES exam_simulation_attempts(id) ON DELETE CASCADE,
  official_score numeric(5,2) NOT NULL DEFAULT 0,
  ai_evaluation jsonb NOT NULL DEFAULT '{}',
  time_analysis jsonb NOT NULL DEFAULT '{}',
  difficulty_analysis jsonb NOT NULL DEFAULT '{}',
  confidence_analysis jsonb NOT NULL DEFAULT '{}',
  weak_concept_analysis jsonb NOT NULL DEFAULT '{}',
  book_recommendations jsonb NOT NULL DEFAULT '[]',
  revision_plan jsonb NOT NULL DEFAULT '{}',
  learning_path jsonb NOT NULL DEFAULT '{}',
  related_official_questions jsonb NOT NULL DEFAULT '[]',
  related_ai_questions jsonb NOT NULL DEFAULT '[]',
  next_recommended_mock jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);
