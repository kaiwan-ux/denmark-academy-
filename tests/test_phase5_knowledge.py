from datetime import datetime, timedelta, timezone

from denmark_academy.knowledge.engines import (
    AICurrentAffairsGenerator,
    ContentQualityValidationEngine,
    CurrentAffairsIntelligencePipeline,
    DocumentProcessingPipeline,
    DuplicateDetectionEngine,
    MetadataIntelligenceEngine,
    SchedulerEngine,
)


def test_document_processing_cleans_and_chunks_text():
    pipeline = DocumentProcessingPipeline()
    cleaned = pipeline.clean('  Danmark\n\n grundlov   valg  ')
    assert cleaned == 'Danmark grundlov valg'
    assert pipeline.chunk('word ' * 1000)


def test_metadata_detects_exam_relevance():
    metadata = MetadataIntelligenceEngine().generate('Danmark grundlov folketing demokrati kommune valg')
    assert metadata['relevance_score'] >= 35
    assert 'grundlov' in metadata['topics']


def test_duplicate_detection_similarity():
    engine = DuplicateDetectionEngine()
    score = engine.similarity('danmark grundlov folketing', 'danmark grundlov folketing')
    assert engine.is_duplicate(score)


def test_quality_validation_routes_low_content_to_review_or_reject():
    result = ContentQualityValidationEngine().validate(
        text='short',
        metadata={'topics': [], 'relevance_score': 0},
        duplication_risk=0,
        trace={},
    )
    assert result.decision in {'needs_review', 'reject'}


def test_current_affairs_generator_creates_requested_resources():
    resources = AICurrentAffairsGenerator().generate_resources(
        'New Danish law',
        'The Danish government changed rules relevant to society.',
        ['summary', 'flashcard', 'practice_question'],
    )
    assert [item['resource_type'] for item in resources] == ['summary', 'flashcard', 'practice_question']


def test_scheduler_due_logic():
    scheduler = SchedulerEngine()
    assert scheduler.is_due(datetime.now(timezone.utc) - timedelta(minutes=1))
    assert not scheduler.is_due(datetime.now(timezone.utc) + timedelta(minutes=5))
