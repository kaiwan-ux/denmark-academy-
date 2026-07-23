from uuid import UUID

from denmark_academy.ai.orchestrator import AIOrchestrator
from denmark_academy.ai.schemas import AIArtifactRequest, AIMockRequest, RecommendationRequest, StudyPlanRequest
from denmark_academy.lms.repository import Phase2Repository
from denmark_academy.practice.service import PracticeService
from denmark_academy.phase2_schemas import PracticeSessionCreate


class AIIntelligenceService:
    def __init__(
        self,
        orchestrator: AIOrchestrator | None = None,
        lms_repository: Phase2Repository | None = None,
        practice_service: PracticeService | None = None,
    ) -> None:
        self.orchestrator = orchestrator or AIOrchestrator()
        self.lms_repository = lms_repository or Phase2Repository()
        self.practice_service = practice_service or PracticeService(self.lms_repository)

    async def tutor(self, request: AIArtifactRequest) -> dict:
        return await self.orchestrator.generate_artifact(request, "tutor_response")

    async def explanation(self, request: AIArtifactRequest) -> dict:
        return await self.orchestrator.generate_artifact(request, "explanation")

    async def similar_questions(self, request: AIArtifactRequest) -> dict:
        return await self.orchestrator.generate_artifact(request, "similar_question")

    async def flashcards(self, request: AIArtifactRequest) -> dict:
        return await self.orchestrator.generate_artifact(request, "flashcard")

    async def notes(self, request: AIArtifactRequest) -> dict:
        return await self.orchestrator.generate_artifact(request, "notes")

    async def quiz(self, request: AIArtifactRequest) -> dict:
        return await self.orchestrator.generate_artifact(request, "quiz")

    async def revision_assistant(self, request: AIArtifactRequest) -> dict:
        return await self.orchestrator.generate_artifact(request, "revision_plan")

    async def study_plan(self, request: StudyPlanRequest) -> dict:
        artifact_request = AIArtifactRequest(
            track=request.track,
            user_id=request.user_id,
            query=f"Create a {request.days_until_exam}-day study plan with {request.minutes_per_day} minutes per day.",
            purpose="study_plan",
            template_key="study_plan_v1",
            provider=request.provider,
            model=request.model,
            metadata={"days_until_exam": request.days_until_exam, "minutes_per_day": request.minutes_per_day},
        )
        return await self.orchestrator.generate_artifact(artifact_request, "study_plan")

    def recommendations(self, request: RecommendationRequest) -> dict:
        with self.lms_repository.connection() as conn:
            dashboard = self.lms_repository.dashboard(conn, request.user_id, request.track)
            search = self.lms_repository.search(
                conn,
                __import__("denmark_academy.phase2_schemas", fromlist=["SearchRequest"]).SearchRequest(
                    track=request.track,
                    query="",
                    entity_types=["chapter", "topic", "official_question"],
                    limit=request.limit,
                ),
            )
        recommendations = []
        if dashboard["revision"]["due_count"]:
            recommendations.append({"type": "revision", "priority": "high", "title": "Review due questions"})
        for topic in search.get("topics", [])[: request.limit]:
            recommendations.append({"type": "topic", "priority": "medium", "title": topic["title"], "topic_id": str(topic["id"])})
        return {"track": request.track, "user_id": str(request.user_id), "items": recommendations[: request.limit]}

    def weakness_analysis(self, user_id: UUID, track: str) -> dict:
        with self.lms_repository.connection() as conn:
            track_id = self.lms_repository.track_id(conn, track)
            rows = conn.execute(
                """
                SELECT COALESCE(t.title, 'Unclassified') AS topic,
                  COUNT(*) FILTER (WHERE psq.is_correct = false) AS wrong,
                  COUNT(*) FILTER (WHERE psq.is_correct = true) AS correct
                FROM practice_session_questions psq
                JOIN practice_sessions ps ON ps.id = psq.practice_session_id
                JOIN official_questions q ON q.id = psq.official_question_id
                LEFT JOIN official_question_classifications c ON c.official_question_id = q.id
                LEFT JOIN course_topics t ON t.id = c.topic_id
                WHERE ps.user_id = %s AND ps.exam_track_id = %s
                GROUP BY t.title
                ORDER BY wrong DESC NULLS LAST
                LIMIT 10
                """,
                (user_id, track_id),
            ).fetchall()
        return {"track": track, "user_id": str(user_id), "weak_topics": [dict(row) for row in rows]}

    def create_ai_mock(self, request: AIMockRequest) -> dict:
        request.composition.validate_total()
        with self.lms_repository.connection() as conn:
            blueprint = conn.execute("SELECT * FROM exam_blueprints WHERE id = %s", (request.blueprint_id,)).fetchone()
            if not blueprint:
                raise ValueError("Blueprint not found")
            total = blueprint["total_questions"]
        official_count = round(total * (request.composition.official_percent / 100))
        session = self.practice_service.create_session(
            PracticeSessionCreate(
                track=request.track,
                user_id=request.user_id,
                mode="mock_exam",
                source_type="blueprint",
                source_id=request.blueprint_id,
                limit=official_count if official_count > 0 else 1,
            )
        )
        return {
            "session": session["session"],
            "composition": request.composition.model_dump(),
            "official_questions_selected": len(session["questions"]),
            "ai_questions_requested": max(0, total - len(session["questions"])),
            "note": "AI question generation is evaluated and stored separately before being added to student-facing mocks.",
        }
