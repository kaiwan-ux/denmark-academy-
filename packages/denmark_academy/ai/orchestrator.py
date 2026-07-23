from denmark_academy.ai.evaluation import AIEvaluator
from denmark_academy.ai.prompt_builder import DEFAULT_TEMPLATES, PromptBuilder
from denmark_academy.ai.providers import AIGateway
from denmark_academy.ai.rag import HybridRAGEngine
from denmark_academy.ai.repository import AIRepository
from denmark_academy.ai.schemas import (
    AIArtifactRequest,
    AICompletionRequest,
    EvaluationRequest,
    PromptBuildRequest,
)


class AIOrchestrator:
    def __init__(
        self,
        repository: AIRepository | None = None,
        rag: HybridRAGEngine | None = None,
        prompt_builder: PromptBuilder | None = None,
        gateway: AIGateway | None = None,
        evaluator: AIEvaluator | None = None,
    ) -> None:
        self.repository = repository or AIRepository()
        self.rag = rag or HybridRAGEngine()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.gateway = gateway or AIGateway()
        self.evaluator = evaluator or AIEvaluator()

    async def generate_artifact(self, request: AIArtifactRequest, artifact_type: str) -> dict:
        sources, retrieval_meta = self.rag.retrieve(
            request=request.__class__(**request.model_dump()).model_copy(update={})
            if False
            else _retrieval_request_from_artifact(request)
        )
        with self.repository.connection() as conn:
            template = self.repository.active_template(conn, request.template_key)
            default = DEFAULT_TEMPLATES.get(request.template_key) or DEFAULT_TEMPLATES["explanation_v1"]
            system_template = template["system_template"] if template else default["system"]
            user_template = template["user_template"] if template else default["user"]
            template_id = template["id"] if template else None
            retrieval_snapshot_id = self.repository.create_retrieval_snapshot(
                conn, request.track, request.query, retrieval_meta, sources
            )
            messages = self.prompt_builder.build(
                PromptBuildRequest(
                    track=request.track,
                    purpose=request.purpose,
                    template_key=request.template_key,
                    retrieved_sources=sources,
                    student_context=request.student_context,
                    difficulty=request.difficulty,
                    metadata=request.metadata,
                ),
                system_template,
                user_template,
            )
            completion = await self.gateway.complete(
                AICompletionRequest(
                    provider=request.provider,
                    model=request.model,
                    purpose=request.purpose,
                    messages=messages,
                    cache_key=self.prompt_builder.cache_key(messages, request.model, request.purpose),
                )
            )
            content = {
                "text": completion.content,
                "purpose": request.purpose,
                "sources": [source.model_dump(mode="json") for source in sources],
            }
            prompt_run_id = self.repository.create_prompt_run(
                conn,
                track=request.track,
                user_id=request.user_id,
                template_id=template_id,
                retrieval_snapshot_id=retrieval_snapshot_id,
                provider_key=completion.provider,
                model=completion.model,
                purpose=request.purpose,
                messages=[message.model_dump(mode="json") for message in messages],
                response_payload=completion.model_dump(mode="json"),
                token_usage=completion.token_usage,
                cache_hit=completion.cache_hit,
            )
            official_texts = self.repository.official_similarity_texts(conn, request.track)
            evaluation = self.evaluator.evaluate(
                EvaluationRequest(
                    track=request.track,
                    artifact_type=artifact_type,
                    content=content,
                    retrieved_sources=sources,
                    official_similarity_texts=official_texts,
                )
            )
            status = "approved" if evaluation.decision == "approve" else evaluation.decision
            artifact_id = self.repository.create_artifact(
                conn,
                track=request.track,
                user_id=request.user_id,
                artifact_type=artifact_type,
                source_entity_type=request.source_entity_type,
                source_entity_id=request.source_entity_id,
                prompt_run_id=prompt_run_id,
                title=f"AI {artifact_type}",
                content=content,
                status=status,
                quality_score=evaluation.quality_score,
                metadata={"retrieval": retrieval_meta},
            )
            evaluation_id = self.repository.create_evaluation(
                conn,
                track=request.track,
                artifact_id=artifact_id,
                ai_generated_question_id=None,
                result=evaluation,
                evaluator_version=self.evaluator.evaluator_version,
            )
            conn.commit()
            return {
                "artifact_id": str(artifact_id),
                "prompt_run_id": str(prompt_run_id),
                "retrieval_snapshot_id": str(retrieval_snapshot_id),
                "evaluation_id": str(evaluation_id),
                "status": status,
                "evaluation": evaluation.model_dump(mode="json"),
                "content": content,
            }


def _retrieval_request_from_artifact(request: AIArtifactRequest):
    from denmark_academy.ai.schemas import RetrievalRequest

    return RetrievalRequest(
        track=request.track,
        query=request.query,
        purpose=request.purpose,
        limit=8,
        include_current_affairs=request.metadata.get("include_current_affairs", False),
        filters=request.metadata,
    )
