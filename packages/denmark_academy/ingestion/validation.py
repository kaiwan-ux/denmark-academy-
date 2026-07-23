from denmark_academy.domain import ChoiceLetter, ParsedAnswerKey, ParsedQuestion, ValidationReport


def validate_question_answer_pair(
    questions: list[ParsedQuestion],
    answer_key: ParsedAnswerKey,
    expected_question_count: int | None = None,
) -> ValidationReport:
    errors: list[str] = []
    warnings: list[str] = []

    question_numbers = [question.question_number for question in questions]
    if len(question_numbers) != len(set(question_numbers)):
        errors.append("Duplicate question numbers parsed from question PDF.")

    if question_numbers:
        expected_sequence = list(range(min(question_numbers), max(question_numbers) + 1))
        if question_numbers != expected_sequence:
            warnings.append(
                f"Question numbers are not sequential: parsed={question_numbers}, expected={expected_sequence}"
            )

    if expected_question_count and len(questions) != expected_question_count:
        warnings.append(
            f"Parsed question count {len(questions)} differs from expected {expected_question_count}."
        )

    for question in questions:
        if ChoiceLetter.A not in question.choices or ChoiceLetter.B not in question.choices:
            errors.append(f"Question {question.question_number} is missing A or B choices.")
        correct_choice = answer_key.answers.get(question.question_number)
        if correct_choice is None:
            errors.append(f"Question {question.question_number} has no answer key entry.")
        elif correct_choice not in question.choices:
            errors.append(
                f"Question {question.question_number} answer key points to missing choice {correct_choice}."
            )

    for answer_number in answer_key.answers:
        if answer_number not in question_numbers:
            warnings.append(f"Answer key contains entry for unparsed question {answer_number}.")

    status = "valid" if not errors else "invalid"
    if warnings and not errors:
        status = "needs_review"
    return ValidationReport(
        status=status,
        expected_question_count=expected_question_count,
        parsed_question_count=len(questions),
        parsed_answer_count=len(answer_key.answers),
        errors=errors,
        warnings=warnings,
    )

