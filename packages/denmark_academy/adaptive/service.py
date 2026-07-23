from uuid import UUID

from psycopg.types.json import Jsonb

from denmark_academy.adaptive.engines import (
    AdaptiveMockPlanner,
    ExamReadinessEngine,
    LearningAnalyticsEngine,
    LearningProfileEngine,
    MotivationEngine,
    PassPredictionEngine,
    PersonalizedStudyPlanner,
    RecommendationEngineV2,
)
from denmark_academy.adaptive.repository import AdaptiveRepository
from denmark_academy.adaptive.schemas import AdaptiveMockRequest, ConceptCreate, LearningInteractionEvent, StudyPlannerRequest


class AdaptiveLearningService:
    def __init__(self, repository: AdaptiveRepository | None = None) -> None:
        self.repository = repository or AdaptiveRepository()
        self.profile_engine = LearningProfileEngine(self.repository)
        self.readiness_engine = ExamReadinessEngine()
        self.prediction_engine = PassPredictionEngine()
        self.recommendation_engine = RecommendationEngineV2()
        self.motivation_engine = MotivationEngine()
        self.analytics_engine = LearningAnalyticsEngine()
        self.planner = PersonalizedStudyPlanner()
        self.mock_planner = AdaptiveMockPlanner()

    def create_concept(self, payload: ConceptCreate) -> dict:
        with self.repository.connection() as conn:
            row = self.repository.create_concept(conn, payload)
            conn.commit()
            return dict(row)

    def record_interaction(self, event: LearningInteractionEvent) -> dict:
        return self.profile_engine.update_after_event(event)

    def refresh_profile(self, user_id: UUID, track: str) -> dict:
        with self.repository.connection() as conn:
            self.repository.get_or_create_profile(conn, user_id, track)
            metrics = self.profile_engine.compute_profile_metrics(conn, user_id, track)
            profile = self.repository.upsert_profile_metrics(conn, user_id, track, metrics)
            mastery = self.repository.mastery_rows(conn, user_id, track)
            due = self.repository.due_spaced_items(conn, user_id, track)
            recommendations = self.recommendation_engine.build(dict(profile), mastery, due)
            stored_recommendations = [dict(self.repository.store_recommendation(conn, user_id, track, item)) for item in recommendations]
            for award in self.motivation_engine.achievements(dict(profile)):
                track_id = self.repository.track_id(conn, track)
                conn.execute(
                    """
                    INSERT INTO motivation_events (user_id, exam_track_id, event_key, points, badge_key, title, description)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (user_id, track_id, award["event_key"], award["points"], award["badge_key"], award["title"], award["description"]),
                )
            conn.commit()
            return {"profile": dict(profile), "mastery": mastery, "recommendations": stored_recommendations}

    def readiness(self, user_id: UUID, track: str) -> dict:
        with self.repository.connection() as conn:
            profile = self.repository.get_or_create_profile(conn, user_id, track)
            mastery = self.repository.mastery_rows(conn, user_id, track)
            readiness = self.readiness_engine.calculate(dict(profile), mastery)
            row = self.repository.store_readiness(conn, user_id, track, readiness)
            conn.commit()
            return dict(row)

    def pass_prediction(self, user_id: UUID, track: str) -> dict:
        with self.repository.connection() as conn:
            profile = self.repository.get_or_create_profile(conn, user_id, track)
            mastery = self.repository.mastery_rows(conn, user_id, track)
            readiness = self.readiness_engine.calculate(dict(profile), mastery)
            prediction = self.prediction_engine.predict(readiness, dict(profile))
            row = self.repository.store_prediction(conn, user_id, track, prediction)
            conn.commit()
            return dict(row)

    def dashboard(self, user_id: UUID, track: str) -> dict:
        with self.repository.connection() as conn:
            profile = self.repository.get_or_create_profile(conn, user_id, track)
            mastery = self.repository.mastery_rows(conn, user_id, track)
            due = self.repository.due_spaced_items(conn, user_id, track)
            readiness = self.readiness_engine.calculate(dict(profile), mastery)
            prediction = self.prediction_engine.predict(readiness, dict(profile))
            recommendations = self.recommendation_engine.build(dict(profile), mastery, due)
            analytics = self.analytics_engine.trend_payload(dict(profile), mastery)
            return {"profile": dict(profile), "mastery": mastery, "due_reviews": due, "readiness": readiness, "pass_prediction": prediction, "recommendations": recommendations, "analytics": analytics}

    def study_plan(self, request: StudyPlannerRequest) -> dict:
        dashboard = self.dashboard(request.user_id, request.track)
        return self.planner.build_plan(request, dashboard["recommendations"])

    def adaptive_mock_plan(self, request: AdaptiveMockRequest) -> dict:
        with self.repository.connection() as conn:
            mastery = self.repository.mastery_rows(conn, request.user_id, request.track)
            plan = self.mock_planner.build(request, mastery)
            track_id = self.repository.track_id(conn, request.track)
            row = conn.execute(
                """
                INSERT INTO adaptive_mock_blueprints (
                  user_id, exam_track_id, exam_blueprint_id, official_percent, ai_percent,
                  weak_concept_weight, difficulty_progression, generated_plan
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (request.user_id, track_id, request.blueprint_id, request.official_percent, request.ai_percent, request.weak_concept_weight, Jsonb(plan["difficulty_progression"]), Jsonb(plan)),
            ).fetchone()
            conn.commit()
            return dict(row)
