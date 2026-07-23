from uuid import UUID

from denmark_academy.knowledge.engines import (
    AICurrentAffairsGenerator,
    ContentQualityValidationEngine,
    CurrentAffairsIntelligencePipeline,
    DocumentProcessingPipeline,
    DuplicateDetectionEngine,
    MetadataIntelligenceEngine,
    NotificationEngine,
)
from denmark_academy.knowledge.repository import KnowledgeRepository
from denmark_academy.knowledge.schemas import (
    ApprovalDecisionRequest,
    CollectedDocumentInput,
    CurrentAffairsGenerateRequest,
    KnowledgeSourceCreate,
    NotificationCreate,
    ProcessingRequest,
    SchedulerJobCreate,
)


class KnowledgeAutomationService:
    def __init__(self, repository: KnowledgeRepository | None = None) -> None:
        self.repository = repository or KnowledgeRepository()
        self.processor = DocumentProcessingPipeline()
        self.metadata_engine = MetadataIntelligenceEngine()
        self.duplicate_engine = DuplicateDetectionEngine()
        self.quality_engine = ContentQualityValidationEngine()
        self.current_affairs = CurrentAffairsIntelligencePipeline()
        self.generator = AICurrentAffairsGenerator()
        self.notifications = NotificationEngine()

    def create_source(self, payload: KnowledgeSourceCreate) -> dict:
        with self.repository.connection() as conn:
            row = self.repository.create_source(conn, payload)
            conn.commit()
            return row

    def list_sources(self) -> list[dict]:
        with self.repository.connection() as conn:
            return self.repository.list_sources(conn)

    def ingest_manual_document(self, payload: CollectedDocumentInput) -> dict:
        with self.repository.connection() as conn:
            run = self.repository.create_collection_run(conn, payload.source_id)
            version = self.repository.upsert_document_version(
                conn,
                source_id=payload.source_id,
                run_id=run['id'],
                track=payload.track,
                canonical_url=payload.canonical_url,
                title=payload.title,
                document_type=payload.document_type,
                raw_text=payload.raw_text,
                language=payload.language,
                metadata=payload.metadata,
            )
            for job in ['extract', 'clean', 'chunk', 'metadata', 'duplicate_check', 'quality_validate']:
                self.repository.create_processing_job(conn, version['id'], job)
            report = {'discovered_count': 1, 'stored_count': 1, 'skipped_count': 0, 'version_id': str(version['id'])}
            self.repository.complete_collection_run(conn, run['id'], 'completed', report)
            conn.commit()
            return {'run': run, 'version': version, 'report': report}

    def process_document(self, payload: ProcessingRequest) -> dict:
        with self.repository.connection() as conn:
            version = conn.execute('SELECT * FROM document_versions_automation WHERE id=%s', (payload.document_version_id,)).fetchone()
            if not version:
                raise ValueError('Document version not found')
            document = conn.execute('SELECT * FROM collected_documents WHERE id=%s', (version['collected_document_id'],)).fetchone()
            cleaned = self.processor.clean(version['extracted_text'] or '')
            chunks = self.processor.chunk(cleaned)
            track_slug = None
            if document['exam_track_id']:
                track_row = conn.execute('SELECT slug FROM exam_tracks WHERE id=%s', (document['exam_track_id'],)).fetchone()
                track_slug = track_row['slug'] if track_row else None
            metadata = self.metadata_engine.generate(cleaned)
            metadata_row = self.repository.store_metadata(conn, payload.document_version_id, track_slug, metadata)
            duplication_risk = 0
            quality = self.quality_engine.validate(text=cleaned, metadata=metadata, duplication_risk=duplication_risk, trace=version['trace'] or {})
            quality_row = self.repository.store_quality_validation(conn, track_slug, 'document_version', payload.document_version_id, quality)
            status = 'processed' if quality.decision == 'approve' else 'needs_review'
            conn.execute('UPDATE document_versions_automation SET processing_status=%s, cleaned_storage_uri=%s WHERE id=%s', (status, f'internal://cleaned/{payload.document_version_id}', payload.document_version_id))
            if quality.decision != 'approve':
                approval = self.repository.submit_approval(conn, track_slug, 'document_version', payload.document_version_id, {'quality_validation_id': str(quality_row['id'])})
            else:
                approval = None
            conn.commit()
            return {'document_version_id': str(payload.document_version_id), 'chunks': len(chunks), 'metadata': metadata_row, 'quality': quality_row, 'approval': approval}

    def generate_current_affairs(self, payload: CurrentAffairsGenerateRequest) -> dict:
        with self.repository.connection() as conn:
            version = conn.execute('SELECT * FROM document_versions_automation WHERE id=%s', (payload.document_version_id,)).fetchone()
            if not version:
                raise ValueError('Document version not found')
            document = conn.execute('SELECT * FROM collected_documents WHERE id=%s', (version['collected_document_id'],)).fetchone()
            metadata = self.metadata_engine.generate(version['extracted_text'] or '')
            if not self.current_affairs.is_relevant(metadata):
                return {'created': False, 'reason': 'Document is below current-affairs relevance threshold.', 'metadata': metadata}
            summary = self.current_affairs.summarize(document['title'], version['extracted_text'] or '')
            item = self.repository.create_current_affairs_item(conn, payload.track, payload.document_version_id, document['title'], summary, metadata['relevance_score'], metadata.get('current_affairs_category'), {'document_version_id': str(payload.document_version_id)})
            resources = []
            for generated in self.generator.generate_resources(document['title'], summary, payload.generate_resources):
                resource = self.repository.create_generated_resource(conn, payload.track, item['id'], payload.document_version_id, generated['resource_type'], generated['title'], generated['content'], {'current_affairs_item_id': str(item['id'])})
                quality = self.quality_engine.validate(text=str(generated['content']), metadata=metadata, duplication_risk=0, trace={'current_affairs_item_id': str(item['id'])})
                quality_row = self.repository.store_quality_validation(conn, payload.track, 'generated_resource', resource['id'], quality)
                conn.execute('UPDATE generated_content_resources SET quality_validation_id=%s, status=%s WHERE id=%s', (quality_row['id'], 'needs_review' if quality.decision != 'approve' else 'approved', resource['id']))
                approval = self.repository.submit_approval(conn, payload.track, 'generated_resource', resource['id'], {'quality_validation_id': str(quality_row['id'])})
                resources.append({'resource': resource, 'quality': quality_row, 'approval': approval})
            self.repository.submit_approval(conn, payload.track, 'current_affairs_item', item['id'])
            conn.commit()
            return {'created': True, 'current_affairs_item': item, 'resources': resources}

    def decide_approval(self, payload: ApprovalDecisionRequest) -> dict:
        with self.repository.connection() as conn:
            row = self.repository.decide_approval(conn, payload)
            conn.commit()
            return row

    def create_scheduler_job(self, payload: SchedulerJobCreate) -> dict:
        with self.repository.connection() as conn:
            row = self.repository.create_scheduler_job(conn, payload)
            conn.commit()
            return row

    def create_notification(self, payload: NotificationCreate) -> dict:
        with self.repository.connection() as conn:
            row = self.repository.create_notification(conn, payload)
            conn.commit()
            return row

    def analytics(self) -> dict:
        with self.repository.connection() as conn:
            return self.repository.analytics(conn)
