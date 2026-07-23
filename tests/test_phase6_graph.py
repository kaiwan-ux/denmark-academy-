from uuid import UUID

import pytest

from denmark_academy.graph.algorithms import GraphAlgorithmEngine, GraphEdge
from denmark_academy.graph.schemas import ExamSimulationCreate, MentorRequest
from denmark_academy.graph.services import MentorService

USER = UUID('00000000-0000-0000-0000-000000000001')


def test_shortest_learning_path():
    engine = GraphAlgorithmEngine()
    edges = [GraphEdge('concept:a', 'concept:b', 'PREREQUISITE_FOR'), GraphEdge('concept:b', 'concept:c', 'PREREQUISITE_FOR')]
    assert engine.shortest_path(edges, 'concept:a', 'concept:c') == ['concept:a', 'concept:b', 'concept:c']


def test_downstream_mistake_causes_prioritizes_prerequisite():
    engine = GraphAlgorithmEngine()
    edges = [GraphEdge('concept:a', 'concept:b', 'CONCEPT_RELATED_TO_CONCEPT'), GraphEdge('concept:b', 'concept:c', 'CONCEPT_RELATED_TO_CONCEPT')]
    ranked = engine.downstream_mistake_causes(edges, {'concept:a': 0.9, 'concept:c': 0.9})
    assert ranked[0]['concept'] == 'concept:a'


def test_centrality_and_similarity():
    engine = GraphAlgorithmEngine()
    centrality = engine.centrality([GraphEdge('a', 'b', 'REL'), GraphEdge('a', 'c', 'REL')])
    assert centrality['a'] == 100
    assert engine.concept_similarity({'q1', 'q2'}, {'q2', 'q3'}) == 33.33


def test_exam_simulation_ratio_validation():
    payload = ExamSimulationCreate(user_id=USER, track='pr', name='Bad ratio', mode='mixed', official_percent=80, ai_percent=10)
    with pytest.raises(ValueError):
        payload.validate_ratio()


def test_mentor_short_session_plan_without_database():
    class FakeGraph:
        def graph_metrics(self, track, user_id=None):
            return {'centrality': {'concept:grundlov': 100}, 'communities': []}

    response = MentorService(FakeGraph()).advise(MentorRequest(user_id=USER, track='citizenship', message='I only have 20 minutes today.', available_minutes=20))
    assert response['available_minutes'] == 20
    assert len(response['plan']) == 2
