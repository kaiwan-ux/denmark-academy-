CREATE TABLE IF NOT EXISTS knowledge_sources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  exam_track_id uuid REFERENCES exam_tracks(id),
  source_key text NOT NULL UNIQUE,
  name text NOT NULL,
  source_type text NOT NULL CHECK (source_type IN ('government_site', 'immigration_site', 'citizenship_resource', 'official_pdf', 'rss_feed', 'news_api', 'mcp_connector', 'manual_upload')),
  base_url text,
  config jsonb NOT NULL DEFAULT '{}',
  trust_level text NOT NULL DEFAULT 'official' CHECK (trust_level IN ('official', 'trusted', 'news', 'manual', 'experimental')),
  collection_frequency_minutes int NOT NULL DEFAULT 1440,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS content_collection_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  knowledge_source_id uuid NOT NULL REFERENCES knowledge_sources(id),
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'needs_review')),
  started_at timestamptz,
  completed_at timestamptz,
  discovered_count int NOT NULL DEFAULT 0,
  stored_count int NOT NULL DEFAULT 0,
  skipped_count int NOT NULL DEFAULT 0,
  error_message text,
  report jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS collected_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  knowledge_source_id uuid NOT NULL REFERENCES knowledge_sources(id),
  exam_track_id uuid REFERENCES exam_tracks(id),
  canonical_url text,
  title text NOT NULL,
  document_type text NOT NULL CHECK (document_type IN ('html', 'pdf', 'rss_item', 'news_article', 'manual_upload', 'mcp_resource')),
  language text NOT NULL DEFAULT 'da',
  first_seen_at timestamptz NOT NULL DEFAULT now(),
  latest_version_id uuid,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived', 'blocked')),
  metadata jsonb NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS document_versions_automation (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  collected_document_id uuid NOT NULL REFERENCES collected_documents(id) ON DELETE CASCADE,
  collection_run_id uuid REFERENCES content_collection_runs(id),
  version_number int NOT NULL,
  content_sha256 text NOT NULL,
  raw_storage_uri text,
  cleaned_storage_uri text,
  extracted_text text,
  source_published_at timestamptz,
  change_summary text,
  processing_status text NOT NULL DEFAULT 'pending' CHECK (processing_status IN ('pending', 'processing', 'processed', 'failed', 'duplicate', 'needs_review')),
  trace jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (collected_document_id, version_number),
  UNIQUE (collected_document_id, content_sha256)
);

ALTER TABLE collected_documents
  ADD CONSTRAINT fk_collected_documents_latest_version
  FOREIGN KEY (latest_version_id) REFERENCES document_versions_automation(id) DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE IF NOT EXISTS document_processing_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_version_id uuid NOT NULL REFERENCES document_versions_automation(id) ON DELETE CASCADE,
  job_type text NOT NULL CHECK (job_type IN ('extract', 'clean', 'chunk', 'metadata', 'embed', 'version', 'duplicate_check', 'quality_validate')),
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
  attempts int NOT NULL DEFAULT 0,
  error_message text,
  result jsonb NOT NULL DEFAULT '{}',
  scheduled_at timestamptz NOT NULL DEFAULT now(),
  started_at timestamptz,
  completed_at timestamptz
);

CREATE TABLE IF NOT EXISTS content_metadata_intelligence (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_version_id uuid NOT NULL REFERENCES document_versions_automation(id) ON DELETE CASCADE,
  exam_track_id uuid REFERENCES exam_tracks(id),
  detected_topics jsonb NOT NULL DEFAULT '[]',
  detected_concepts jsonb NOT NULL DEFAULT '[]',
  relevance_score numeric(5,2) NOT NULL DEFAULT 0,
  audience_level text,
  difficulty text CHECK (difficulty IN ('easy', 'medium', 'hard')),
  current_affairs_category text,
  metadata_model_version text NOT NULL DEFAULT 'metadata-intel-v1',
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (document_version_id)
);

CREATE TABLE IF NOT EXISTS duplicate_detection_groups (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  exam_track_id uuid REFERENCES exam_tracks(id),
  group_key text NOT NULL UNIQUE,
  duplicate_type text NOT NULL CHECK (duplicate_type IN ('exact_hash', 'near_duplicate', 'semantic_overlap')),
  canonical_document_version_id uuid REFERENCES document_versions_automation(id),
  confidence numeric(5,2) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS duplicate_detection_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  duplicate_group_id uuid NOT NULL REFERENCES duplicate_detection_groups(id) ON DELETE CASCADE,
  document_version_id uuid NOT NULL REFERENCES document_versions_automation(id),
  similarity_score numeric(5,2) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (duplicate_group_id, document_version_id)
);

CREATE TABLE IF NOT EXISTS current_affairs_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  exam_track_id uuid REFERENCES exam_tracks(id),
  document_version_id uuid REFERENCES document_versions_automation(id),
  title text NOT NULL,
  summary text NOT NULL,
  relevance_score numeric(5,2) NOT NULL,
  event_date date,
  category text,
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'needs_review', 'approved', 'published', 'rejected', 'archived')),
  trace jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS generated_content_resources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  exam_track_id uuid REFERENCES exam_tracks(id),
  current_affairs_item_id uuid REFERENCES current_affairs_items(id),
  document_version_id uuid REFERENCES document_versions_automation(id),
  resource_type text NOT NULL CHECK (resource_type IN ('summary', 'revision_note', 'flashcard', 'practice_question', 'official_style_question')),
  title text,
  content jsonb NOT NULL,
  ai_artifact_id uuid REFERENCES ai_content_artifacts(id),
  quality_validation_id uuid,
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'needs_review', 'approved', 'published', 'rejected', 'archived')),
  trace jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  reviewed_at timestamptz,
  reviewed_by_user_id uuid REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS content_approval_workflows (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  exam_track_id uuid REFERENCES exam_tracks(id),
  entity_type text NOT NULL CHECK (entity_type IN ('document_version', 'current_affairs_item', 'generated_resource')),
  entity_id uuid NOT NULL,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'changes_requested')),
  reviewer_user_id uuid REFERENCES users(id),
  review_note text,
  submitted_at timestamptz NOT NULL DEFAULT now(),
  reviewed_at timestamptz,
  metadata jsonb NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS content_quality_validations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  exam_track_id uuid REFERENCES exam_tracks(id),
  entity_type text NOT NULL CHECK (entity_type IN ('document_version', 'current_affairs_item', 'generated_resource')),
  entity_id uuid NOT NULL,
  validator_version text NOT NULL DEFAULT 'content-quality-v1',
  extraction_quality numeric(5,2) NOT NULL DEFAULT 0,
  metadata_quality numeric(5,2) NOT NULL DEFAULT 0,
  relevance_score numeric(5,2) NOT NULL DEFAULT 0,
  duplication_risk numeric(5,2) NOT NULL DEFAULT 0,
  traceability_score numeric(5,2) NOT NULL DEFAULT 0,
  overall_score numeric(5,2) NOT NULL DEFAULT 0,
  decision text NOT NULL CHECK (decision IN ('approve', 'needs_review', 'reject')),
  findings jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE generated_content_resources
  ADD CONSTRAINT fk_generated_resources_quality_validation
  FOREIGN KEY (quality_validation_id) REFERENCES content_quality_validations(id) DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE IF NOT EXISTS content_notifications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  recipient_user_id uuid REFERENCES users(id),
  channel text NOT NULL DEFAULT 'in_app' CHECK (channel IN ('in_app', 'email', 'webhook')),
  notification_type text NOT NULL,
  title text NOT NULL,
  body text NOT NULL,
  entity_type text,
  entity_id uuid,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed', 'read')),
  created_at timestamptz NOT NULL DEFAULT now(),
  sent_at timestamptz,
  read_at timestamptz
);

CREATE TABLE IF NOT EXISTS background_scheduler_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_key text NOT NULL UNIQUE,
  job_type text NOT NULL CHECK (job_type IN ('collect_source', 'process_document', 'current_affairs', 'past_paper_scan', 'quality_validate', 'notify')),
  schedule_cron text,
  interval_minutes int,
  payload jsonb NOT NULL DEFAULT '{}',
  is_enabled boolean NOT NULL DEFAULT true,
  next_run_at timestamptz,
  last_run_at timestamptz,
  status text NOT NULL DEFAULT 'idle' CHECK (status IN ('idle', 'running', 'failed', 'disabled')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS content_analytics_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  period_start date NOT NULL,
  period_end date NOT NULL,
  source_count int NOT NULL DEFAULT 0,
  documents_collected int NOT NULL DEFAULT 0,
  documents_processed int NOT NULL DEFAULT 0,
  duplicates_found int NOT NULL DEFAULT 0,
  approvals_pending int NOT NULL DEFAULT 0,
  generated_resources int NOT NULL DEFAULT 0,
  average_quality_score numeric(5,2) NOT NULL DEFAULT 0,
  trends jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);
