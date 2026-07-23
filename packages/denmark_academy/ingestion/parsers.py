import re
from pathlib import Path

from denmark_academy.domain import ChoiceLetter, ParsedAnswerKey, ParsedOfficialQuestion, ParsedQuestion
from denmark_academy.ingestion.hashing import text_sha256
from denmark_academy.ingestion.pdf import ExtractedPage, extract_pdf_pages

QUESTION_START_RE = re.compile(r"(?m)(?P<number>\d{1,2})\.\s+")
CHOICE_RE = re.compile(r"(?P<label>[ABC]):\s*(?P<text>.*?)(?=\s+[ABC]:\s*|$)", re.S)
ANSWER_RE = re.compile(r"\b(?P<number>\d{1,2})\s+(?P<choice>[ABC])\b")


def parse_answer_key_pdf(path: Path) -> ParsedAnswerKey:
    text = "\n".join(page.text for page in extract_pdf_pages(path))
    answers = {
        int(match.group("number")): ChoiceLetter(match.group("choice"))
        for match in ANSWER_RE.finditer(text)
    }
    return ParsedAnswerKey(answers=answers)


def parse_question_pdf(path: Path, expected_numbers: list[int] | None = None) -> list[ParsedQuestion]:
    pages = extract_pdf_pages(path)
    if expected_numbers:
        return _parse_expected_questions(pages, expected_numbers)

    parsed: list[ParsedQuestion] = []
    for page in pages:
        parsed.extend(_parse_questions_from_page(page))
    return parsed


def combine_questions_and_answers(
    questions: list[ParsedQuestion], answer_key: ParsedAnswerKey
) -> list[ParsedOfficialQuestion]:
    official_questions: list[ParsedOfficialQuestion] = []
    for question in questions:
        correct_choice = answer_key.answers.get(question.question_number)
        if correct_choice is None:
            continue
        canonical = "|".join(
            [
                str(question.question_number),
                question.stem,
                question.choices.get(ChoiceLetter.A, ""),
                question.choices.get(ChoiceLetter.B, ""),
                question.choices.get(ChoiceLetter.C, ""),
                correct_choice.value,
            ]
        )
        official_questions.append(
            ParsedOfficialQuestion(
                **question.model_dump(),
                correct_choice=correct_choice,
                content_sha256=text_sha256(canonical),
            )
        )
    return official_questions


def _parse_expected_questions(
    pages: list[ExtractedPage], expected_numbers: list[int]
) -> list[ParsedQuestion]:
    full_text, page_offsets = _join_pages(pages)
    questions: list[ParsedQuestion] = []
    cursor = 0
    for index, number in enumerate(expected_numbers):
        start_match = _find_question_number(full_text, number, cursor)
        if not start_match:
            continue
        next_number = expected_numbers[index + 1] if index + 1 < len(expected_numbers) else None
        if next_number is not None:
            next_match = _find_question_number(full_text, next_number, start_match.end())
            end = next_match.start() if next_match else len(full_text)
        else:
            end = len(full_text)
        block = _strip_page_footer(full_text[start_match.end() : end])
        page_number = _page_for_offset(start_match.start(), page_offsets)
        parsed = _parse_question_block(number, block, page_number)
        if parsed:
            questions.append(parsed)
            cursor = end
        else:
            cursor = start_match.end()
    return questions


def _parse_questions_from_page(page: ExtractedPage) -> list[ParsedQuestion]:
    text = _single_line(page.text)
    matches = list(QUESTION_START_RE.finditer(text))
    questions: list[ParsedQuestion] = []
    for index, match in enumerate(matches):
        number = int(match.group("number"))
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = _strip_page_footer(text[start:end])
        parsed = _parse_question_block(number, block, page.page_number)
        if parsed:
            questions.append(parsed)
    return questions


def _parse_question_block(number: int, block: str, page_number: int) -> ParsedQuestion | None:
    block = _single_line(block)
    first_choice = re.search(r"\sA:\s", block)
    if not first_choice:
        return None
    stem = block[: first_choice.start()].strip(" -")
    if len(stem) < 4:
        return None
    choice_text = block[first_choice.start() :].strip()
    choices: dict[ChoiceLetter, str] = {}
    for match in CHOICE_RE.finditer(choice_text):
        label = ChoiceLetter(match.group("label"))
        text = _cleanup_choice(match.group("text"))
        if text:
            choices[label] = text
    if ChoiceLetter.A not in choices or ChoiceLetter.B not in choices:
        return None
    return ParsedQuestion(
        question_number=number,
        stem=stem,
        choices=choices,
        source_page_start=page_number,
        source_page_end=page_number,
    )


def _find_question_number(text: str, number: int, start: int) -> re.Match[str] | None:
    pattern = re.compile(rf"(?<!\d){number}\.\s+")
    return pattern.search(text, start)


def _join_pages(pages: list[ExtractedPage]) -> tuple[str, list[tuple[int, int]]]:
    parts: list[str] = []
    offsets: list[tuple[int, int]] = []
    cursor = 0
    for page in pages:
        text = _single_line(page.text)
        offsets.append((cursor, page.page_number))
        parts.append(text)
        cursor += len(text) + 1
    return " ".join(parts), offsets


def _page_for_offset(offset: int, page_offsets: list[tuple[int, int]]) -> int:
    current_page = 1
    for page_start, page_number in page_offsets:
        if page_start > offset:
            break
        current_page = page_number
    return current_page


def _single_line(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _strip_page_footer(text: str) -> str:
    return re.sub(
        r"\s+\d+\s+.\s+(Medborgerskabsproeven|Medborgerskabsprøven|Indfoedsretsproeven|Indfødsretsprøven).*$",
        "",
        text,
        flags=re.I,
    ).strip()


def _cleanup_choice(text: str) -> str:
    text = _strip_page_footer(text)
    return text.strip(" -")
