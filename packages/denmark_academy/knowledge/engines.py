import re
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from hashlib import sha256
from typing import Any

from denmark_academy.knowledge.schemas import QualityValidationResult

DANISH_EXAM_TERMS = {
    'grundlov', 'folketing', 'demokrati', 'statsborgerskab', 'ophold', 'kommune',
    'region', 'valg', 'danmark', 'dansk', 'rettigheder', 'pligter', 'kongehuset'
}


class DocumentProcessingPipeline:
    def clean(self, text: str) -> str:
        text = text.replace('\x00', ' ')
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def chunk(self, text: str, target_words: int = 450, overlap: int = 60) -> list[str]:
        words = text.split()
        if not words:
            return []
        chunks = []
        start = 0
        while start < len(words):
            end = min(len(words), start + target_words)
            chunks.append(' '.join(words[start:end]))
            if end == len(words):
                break
            start = max(0, end - overlap)
        return chunks


class MetadataIntelligenceEngine:
    def generate(self, text: str) -> dict[str, Any]:
        lower = text.lower()
        topics = sorted(term for term in DANISH_EXAM_TERMS if term in lower)
        relevance = min(100, len(topics) * 12 + (15 if 'danmark' in lower else 0))
        difficulty = 'easy' if len(text.split()) < 400 else 'medium' if len(text.split()) < 1200 else 'hard'
        category = 'current_affairs' if any(term in lower for term in ['minister', 'regering', 'ny', 'aftale', 'lovforslag']) else None
        return {
            'topics': topics,
            'concepts': [{'name': topic, 'confidence': 0.72} for topic in topics],
            'relevance_score': relevance,
            'audience_level': 'exam_candidate',
            'difficulty': difficulty,
            'current_affairs_category': category,
        }


class DuplicateDetectionEngine:
    def exact_key(self, text: str) -> str:
        return sha256(text.encode('utf-8')).hexdigest()

    def similarity(self, left: str, right: str) -> float:
        return round(SequenceMatcher(None, left[:4000], right[:4000]).ratio() * 100, 2)

    def is_duplicate(self, similarity_score: float, threshold: float = 92) -> bool:
        return similarity_score >= threshold


class VersionControlEngine:
    def summarize_change(self, previous_text: str | None, new_text: str) -> str:
        if not previous_text:
            return 'Initial version collected.'
        previous_words = set(previous_text.lower().split())
        new_words = set(new_text.lower().split())
        added = len(new_words - previous_words)
        removed = len(previous_words - new_words)
        return f'Content changed: {added} terms added, {removed} terms removed.'


class ContentQualityValidationEngine:
    def validate(self, *, text: str, metadata: dict[str, Any], duplication_risk: float, trace: dict[str, Any]) -> QualityValidationResult:
        extraction = 95 if len(text.split()) >= 50 else 45 if text else 0
        metadata_quality = 90 if metadata.get('topics') else 50
        relevance = float(metadata.get('relevance_score', 0))
        traceability = 95 if trace.get('source_id') or trace.get('canonical_url') else 55
        overall = round((extraction * 0.25) + (metadata_quality * 0.20) + (relevance * 0.25) + ((100 - duplication_risk) * 0.15) + (traceability * 0.15), 2)
        decision = 'approve'
        if overall < 72 or duplication_risk > 80:
            decision = 'needs_review'
        if overall < 45:
            decision = 'reject'
        return QualityValidationResult(
            extraction_quality=extraction,
            metadata_quality=metadata_quality,
            relevance_score=relevance,
            duplication_risk=duplication_risk,
            traceability_score=traceability,
            overall_score=overall,
            decision=decision,
            findings={'word_count': len(text.split()), 'topics': metadata.get('topics', []), 'has_trace': traceability >= 90},
        )


class CurrentAffairsIntelligencePipeline:
    def is_relevant(self, metadata: dict[str, Any]) -> bool:
        return metadata.get('relevance_score', 0) >= 35 and bool(metadata.get('topics'))

    def summarize(self, title: str, text: str) -> str:
        sentences = re.split(r'(?<=[.!?])\s+', text)
        excerpt = ' '.join(sentences[:3]).strip()
        return excerpt or title


class AICurrentAffairsGenerator:
    def generate_resources(self, title: str, summary: str, resource_types: list[str]) -> list[dict[str, Any]]:
        resources = []
        for resource_type in resource_types:
            if resource_type == 'summary':
                content = {'summary': summary}
            elif resource_type == 'revision_note':
                content = {'note': f'Remember why this current affair matters for Danish society: {summary}'}
            elif resource_type == 'flashcard':
                content = {'front': title, 'back': summary}
            elif resource_type in {'practice_question', 'official_style_question'}:
                content = {'stem': f'Which topic is most closely related to: {title}?', 'choices': {'A': 'Danish society', 'B': 'Unrelated sports result', 'C': 'Private entertainment'}, 'correct_choice': 'A', 'explanation': summary}
            else:
                content = {'text': summary}
            resources.append({'resource_type': resource_type, 'title': f'{resource_type}: {title}', 'content': content})
        return resources


class SchedulerEngine:
    def next_run(self, interval_minutes: int | None) -> datetime | None:
        if not interval_minutes:
            return None
        return datetime.now(timezone.utc) + timedelta(minutes=interval_minutes)

    def is_due(self, next_run_at: datetime | None) -> bool:
        return bool(next_run_at and next_run_at <= datetime.now(timezone.utc))


class NotificationEngine:
    def approval_needed(self, entity_type: str, title: str) -> dict[str, str]:
        return {'notification_type': 'approval_needed', 'title': f'Approval needed: {title}', 'body': f'A {entity_type} is waiting for admin review.'}
