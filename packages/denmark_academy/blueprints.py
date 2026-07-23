from typing import Any

from denmark_academy.domain import BlueprintValidationResult


def validate_blueprint_payload(payload: dict[str, Any]) -> BlueprintValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    total_questions = payload.get("total_questions")
    duration_minutes = payload.get("duration_minutes")
    sections = payload.get("sections") or payload.get("rules", {}).get("sections", [])

    if not isinstance(total_questions, int) or total_questions <= 0:
        errors.append("total_questions must be a positive integer.")
    if not isinstance(duration_minutes, int) or duration_minutes <= 0:
        errors.append("duration_minutes must be a positive integer.")
    if not isinstance(sections, list) or not sections:
        errors.append("At least one blueprint section is required.")

    section_total = 0
    seen_keys: set[str] = set()
    for section in sections if isinstance(sections, list) else []:
        section_key = section.get("section_key")
        question_count = section.get("question_count")
        if not section_key:
            errors.append("Every section requires section_key.")
        elif section_key in seen_keys:
            errors.append(f"Duplicate section_key: {section_key}")
        else:
            seen_keys.add(section_key)
        if not isinstance(question_count, int) or question_count <= 0:
            errors.append(f"Section {section_key or '<missing>'} needs positive question_count.")
        else:
            section_total += question_count

    if isinstance(total_questions, int) and section_total and section_total != total_questions:
        errors.append(
            f"Section question total {section_total} does not equal total_questions {total_questions}."
        )

    if payload.get("passing_score") and payload["passing_score"] > total_questions:
        errors.append("passing_score cannot exceed total_questions.")

    if not payload.get("effective_from"):
        warnings.append("effective_from is not set; activation should confirm the intended start date.")

    return BlueprintValidationResult(valid=not errors, errors=errors, warnings=warnings)

