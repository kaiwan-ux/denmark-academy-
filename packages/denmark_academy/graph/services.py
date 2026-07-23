from uuid import UUID

from denmark_academy.graph.algorithms import GraphAlgorithmEngine
from denmark_academy.graph.schemas import ExamAutoSaveRequest, ExamSimulationCreate, GraphExploreRequest, LearningPathRequest, MentorRequest


class GraphIntelligenceService:
    def __init__(self, repository=None) -> None:
        if repository is None:
            from denmark_academy.graph.repository import GraphRepository

            repository = GraphRepository()
        self.repository = repository
        self.algorithms = GraphAlgorithmEngine()

    def explore(self, request: GraphExploreRequest) -> dict:
        with self.repository.connection() as conn:
            return self.repository.explore(conn, request)

    def node_detail(self, stable_key: str, user_id: UUID | None = None) -> dict:
        with self.repository.connection() as conn:
            return self.repository.node_detail(conn, stable_key, user_id)

    def shortest_learning_path(self, request: LearningPathRequest) -> dict:
        with self.repository.connection() as conn:
            edges = self.repository.edges(conn, request.track, request.user_id if request.include_student_state else None)
            path = self.algorithms.shortest_path(edges, request.from_concept_key, request.to_concept_key)
            prerequisites = self.algorithms.prerequisites(edges, request.to_concept_key)
            centrality = self.algorithms.centrality(edges)
            return {'path': path, 'prerequisites': prerequisites, 'importance': {node: centrality.get(node, 0) for node in path}}

    def graph_metrics(self, track: str, user_id: UUID | None = None) -> dict:
        with self.repository.connection() as conn:
            edges = self.repository.edges(conn, track, user_id)
            return {'centrality': self.algorithms.centrality(edges), 'communities': self.algorithms.communities(edges)}


class MentorService:
    def __init__(self, graph_service: GraphIntelligenceService | None = None) -> None:
        self.graph_service = graph_service or GraphIntelligenceService()

    def advise(self, request: MentorRequest) -> dict:
        metrics = self.graph_service.graph_metrics(request.track, request.user_id)
        top_concepts = sorted(metrics['centrality'].items(), key=lambda item: item[1], reverse=True)[:5]
        minutes = request.available_minutes or 45
        plan = []
        if minutes <= 20:
            plan = [{'title': 'Review one weak concept', 'minutes': min(10, minutes)}, {'title': 'Answer 5 targeted questions', 'minutes': max(5, minutes - 10)}]
        else:
            plan = [{'title': 'Read official material for a central concept', 'minutes': 15}, {'title': 'Practice weak concept questions', 'minutes': 20}, {'title': 'Review mistakes and flashcards', 'minutes': max(10, minutes - 35)}]
        return {'message': request.message, 'goal': request.goal, 'available_minutes': minutes, 'top_graph_concepts': top_concepts, 'plan': plan, 'rationale': 'Plan is based on graph centrality, student weak/mastered concept links, and available time.'}


class ExamSimulationService:
    def __init__(self, repository=None) -> None:
        if repository is None:
            from denmark_academy.graph.repository import GraphRepository

            repository = GraphRepository()
        self.repository = repository

    def create_config(self, payload: ExamSimulationCreate) -> dict:
        payload.validate_ratio()
        with self.repository.connection() as conn:
            track_id = self.repository.track_id(conn, payload.track)
            row = conn.execute(
                """
                INSERT INTO exam_simulation_configs (user_id, exam_track_id, name, mode, difficulty, exam_blueprint_id, timer_seconds, official_percent, ai_percent, filters)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (payload.user_id, track_id, payload.name, payload.mode, payload.difficulty, payload.blueprint_id, payload.timer_seconds, payload.official_percent, payload.ai_percent, __import__('psycopg').types.json.Jsonb(payload.filters)),
            ).fetchone()
            conn.commit()
            return dict(row)

    def autosave(self, attempt_id: UUID, payload: ExamAutoSaveRequest) -> dict:
        with self.repository.connection() as conn:
            row = conn.execute('UPDATE exam_simulation_attempts SET auto_save_state=%s WHERE id=%s RETURNING *', (__import__('psycopg').types.json.Jsonb(payload.state), attempt_id)).fetchone()
            conn.commit()
            return dict(row) if row else {}

    def post_submit_report(self, attempt_id: UUID) -> dict:
        with self.repository.connection() as conn:
            attempt = conn.execute('SELECT * FROM exam_simulation_attempts WHERE id=%s', (attempt_id,)).fetchone()
            if not attempt:
                raise ValueError('Exam simulation attempt not found')
            report = conn.execute(
                """
                INSERT INTO exam_post_submission_reports (
                  exam_simulation_attempt_id, official_score, ai_evaluation, time_analysis,
                  difficulty_analysis, confidence_analysis, weak_concept_analysis,
                  book_recommendations, revision_plan, learning_path, related_official_questions,
                  related_ai_questions, next_recommended_mock
                ) VALUES (%s, 0, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (attempt_id, __import__('psycopg').types.json.Jsonb({'status': 'pending'}), __import__('psycopg').types.json.Jsonb({}), __import__('psycopg').types.json.Jsonb({}), __import__('psycopg').types.json.Jsonb({}), __import__('psycopg').types.json.Jsonb({}), __import__('psycopg').types.json.Jsonb([]), __import__('psycopg').types.json.Jsonb({}), __import__('psycopg').types.json.Jsonb({}), __import__('psycopg').types.json.Jsonb([]), __import__('psycopg').types.json.Jsonb([]), __import__('psycopg').types.json.Jsonb({})),
            ).fetchone()
            conn.commit()
            return dict(report)

