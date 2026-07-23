from hashlib import sha256
from string import Template

from denmark_academy.ai.schemas import PromptBuildRequest, PromptMessage


class PromptBuilder:
    def build(self, request: PromptBuildRequest, system_template: str, user_template: str) -> list[PromptMessage]:
        context = self._format_context(request)
        variables = {
            "exam_type": request.track,
            "purpose": request.purpose,
            "student_level": request.student_context.level,
            "difficulty": request.difficulty,
            "learning_objective": request.student_context.learning_objective or "general exam preparation",
            "weak_topics": ", ".join(request.student_context.weak_topics) or "none provided",
            "retrieved_context": context,
            "metadata": request.metadata,
        }
        return [
            PromptMessage(role="system", content=Template(system_template).safe_substitute(variables)),
            PromptMessage(role="user", content=Template(user_template).safe_substitute(variables)),
        ]

    def cache_key(self, messages: list[PromptMessage], model: str, purpose: str) -> str:
        raw = "|".join([purpose, model, *[f"{m.role}:{m.content}" for m in messages]])
        return sha256(raw.encode("utf-8")).hexdigest()

    def _format_context(self, request: PromptBuildRequest) -> str:
        lines: list[str] = []
        for index, source in enumerate(request.retrieved_sources, start=1):
            title = source.title or source.source_type
            lines.append(
                f"[Source {index}] type={source.source_type}; title={title}; score={source.score}\n{source.text}"
            )
        return "\n\n".join(lines)


DEFAULT_TEMPLATES = {
    "explanation_v1": {
        "system": "You are an exam-grounded Danish learning assistant for $exam_type. Use only supplied sources.",
        "user": "Explain the answer for this learning objective: $learning_objective. Difficulty: $difficulty. Context:\n$retrieved_context",
    },
    "similar_question_v1": {
        "system": "You create non-official practice questions for $exam_type. Never copy official questions.",
        "user": "Create practice questions aligned to $difficulty using this context:\n$retrieved_context",
    },
    "study_plan_v1": {
        "system": "You produce structured study plans for $exam_type using progress metadata and official content only.",
        "user": "Student level: $student_level. Weak topics: $weak_topics. Objective: $learning_objective. Context:\n$retrieved_context",
    },
    "evaluation_v1": {
        "system": "You evaluate AI educational content for groundedness, exam alignment, hallucination risk, duplication, and quality.",
        "user": "Evaluate the content using these sources:\n$retrieved_context",
    },
}
