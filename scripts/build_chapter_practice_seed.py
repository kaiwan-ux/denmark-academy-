"""Build the chapter-practice database migration from the supplied PDF sets.

The build is intentionally strict: it refuses to create a migration unless every
expected question has three choices and one matching answer-key entry.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT / "packages" / "denmark_academy" / "db" / "migrations" / "019_chapter_practice.sql"
)

CITIZENSHIP_TITLES = {
    1: "Danmarks historie",
    2: "Det danske demokrati",
    3: "Den danske økonomi",
    4: "Danmark og omverdenen",
    5: "Dansk kulturliv",
    6: "Temaopslag",
}

PR_TITLES = {
    1: "Skole",
    2: "Uddannelse",
    3: "Dagtilbud",
    4: "Det danske arbejdsmarked",
    5: "Dansk erhvervsliv",
    6: "Det danske velfærdssamfund",
    7: "Familieliv",
    8: "Forenings- og fritidsliv",
    9: "Sundhed og sygdom",
    10: "Ligestilling",
    11: "Demokrati og grundloven",
    12: "Det danske retssamfund",
    13: "Folketing og regering",
    14: "Det lokale selvstyre",
    15: "Folkestyret i praksis - valg og partier",
    16: "Borgernes rettigheder og pligter",
    17: "Religion og kirke",
    18: "Danmark og omverdenen",
    19: "Danmarks geografi og befolkning",
    20: "Danmarks historie før 1945",
    21: "Danmarks historie efter 1945",
    22: "Dansk kultur",
    23: "Traditioner og mærkedage",
    24: "Danmarks forsvars- og sikkerhedspolitik",
    25: "Diskrimination, antisemitisme, hadforbrydelser og ekstremisme",
    26: "Klima",
}


@dataclass(frozen=True)
class SourceSet:
    track: str
    question_pdf: Path
    answer_dir: Path
    answer_file_pattern: re.Pattern[str]
    titles: dict[int, str]
    expected_per_chapter: int
    source_name: str


@dataclass(frozen=True)
class Question:
    track: str
    chapter_number: int
    question_number: int
    stem: str
    choice_a: str
    choice_b: str
    choice_c: str
    correct_choice: str


SOURCES = (
    SourceSet(
        track="citizenship",
        question_pdf=ROOT
        / "citizenship mcqs"
        / "mcqs"
        / "Indfoedsretsproeven_100_MCQs_pr_kapitel.pdf",
        answer_dir=ROOT / "citizenship mcqs" / "answers",
        answer_file_pattern=re.compile(r"Kapitel_(\d+)", re.IGNORECASE),
        titles=CITIZENSHIP_TITLES,
        expected_per_chapter=100,
        source_name="Indfødsretsprøven - 100 MCQs pr. kapitel (august 2025)",
    ),
    SourceSet(
        track="pr",
        question_pdf=ROOT / "pr mcqs" / "mcqs" / "Medborgerskabsproeven_30_MCQs_pr_faktaark.pdf",
        answer_dir=ROOT / "pr mcqs" / "answers",
        answer_file_pattern=re.compile(r"Faktaark_(\d+)", re.IGNORECASE),
        titles=PR_TITLES,
        expected_per_chapter=30,
        source_name="Medborgerskabsprøven - 30 MCQs pr. fakta-ark (august 2025)",
    ),
)


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def parse_answer_keys(source: SourceSet) -> dict[int, dict[int, str]]:
    answers: dict[int, dict[int, str]] = {}
    for path in sorted(source.answer_dir.glob("*.pdf")):
        match = source.answer_file_pattern.search(path.name)
        if not match:
            continue
        chapter_number = int(match.group(1))
        text = "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
        pairs = [
            (int(number), choice)
            for number, choice in re.findall(r"(?m)^\s*(\d{1,3})\s*\n\s*([ABC])\s*$", text)
        ]
        chapter_answers = dict(pairs)
        if len(chapter_answers) != len(pairs):
            raise ValueError(f"Duplicate answer number in {path}")
        answers[chapter_number] = chapter_answers
    return answers


def parse_questions(source: SourceSet) -> dict[int, list[tuple[int, str, dict[str, str]]]]:
    chapters: dict[int, list[tuple[int, str, dict[str, str]]]] = {}
    active_chapter: int | None = None
    chapter_pattern = (
        re.compile(r"(?m)^\s*Kapitel\s+(\d+)\s*-\s*(.+)$")
        if source.track == "citizenship"
        else re.compile(r"(?m)^\s*Fakta-ark\s+(\d+)\s*:\s*(.+)$")
    )

    for page in PdfReader(str(source.question_pdf)).pages[1:]:
        text = page.extract_text() or ""
        text = re.sub(r"(?m)^Side\s+\d+\s*$", "", text)
        text = re.sub(r"(?m)^.*(?:ikke en officiel prøve|august 2025-materialet).*$", "", text)
        heading = chapter_pattern.search(text)
        if heading:
            active_chapter = int(heading.group(1))
            chapters.setdefault(active_chapter, [])
            text = text[heading.end() :]
        if active_chapter is None:
            continue

        question_matches = list(re.finditer(r"(?m)^(\d{1,3})\.\s+(.+)$", text))
        for index, question_match in enumerate(question_matches):
            block_end = (
                question_matches[index + 1].start()
                if index + 1 < len(question_matches)
                else len(text)
            )
            block = text[question_match.start() : block_end]
            option_matches = list(re.finditer(r"(?m)^[^A-Za-z0-9\n]*([ABC]):\s*(.+)$", block))
            if len(option_matches) != 3 or [item.group(1) for item in option_matches] != [
                "A",
                "B",
                "C",
            ]:
                raise ValueError(
                    f"Question {active_chapter}.{question_match.group(1)} in {source.question_pdf} "
                    f"has {len(option_matches)} choices"
                )

            question_prefix = re.match(r"^\d{1,3}\.\s*", block)
            if not question_prefix:
                raise ValueError(f"Malformed question prefix: {block[:80]!r}")
            stem = normalize(block[question_prefix.end() : option_matches[0].start()])
            choices: dict[str, str] = {}
            for option_index, option_match in enumerate(option_matches):
                option_end = (
                    option_matches[option_index + 1].start() if option_index + 1 < 3 else len(block)
                )
                choices[option_match.group(1)] = normalize(
                    block[option_match.start(2) : option_end]
                )
            chapters[active_chapter].append((int(question_match.group(1)), stem, choices))
    return chapters


def extract_and_validate() -> tuple[list[Question], list[tuple[str, int, str, int, str]]]:
    all_questions: list[Question] = []
    chapter_rows: list[tuple[str, int, str, int, str]] = []
    for source in SOURCES:
        if not source.question_pdf.exists():
            raise FileNotFoundError(source.question_pdf)
        questions = parse_questions(source)
        answer_keys = parse_answer_keys(source)
        if set(questions) != set(source.titles):
            raise ValueError(f"{source.track}: question chapters do not match expected chapters")
        if set(answer_keys) != set(source.titles):
            raise ValueError(f"{source.track}: answer-key chapters do not match expected chapters")

        for chapter_number, title in source.titles.items():
            chapter_questions = questions[chapter_number]
            chapter_answers = answer_keys[chapter_number]
            expected_numbers = set(range(1, source.expected_per_chapter + 1))
            actual_numbers = [item[0] for item in chapter_questions]
            if len(actual_numbers) != len(set(actual_numbers)):
                raise ValueError(
                    f"{source.track} chapter {chapter_number}: duplicate question numbers"
                )
            if set(actual_numbers) != expected_numbers:
                raise ValueError(
                    f"{source.track} chapter {chapter_number}: incomplete question sequence"
                )
            if set(chapter_answers) != expected_numbers:
                raise ValueError(f"{source.track} chapter {chapter_number}: incomplete answer key")

            for number, stem, choices in sorted(chapter_questions):
                if not stem or any(not choices[key] for key in ("A", "B", "C")):
                    raise ValueError(
                        f"{source.track} chapter {chapter_number}, question {number}: empty content"
                    )
                all_questions.append(
                    Question(
                        track=source.track,
                        chapter_number=chapter_number,
                        question_number=number,
                        stem=stem,
                        choice_a=choices["A"],
                        choice_b=choices["B"],
                        choice_c=choices["C"],
                        correct_choice=chapter_answers[number],
                    )
                )
            chapter_rows.append(
                (
                    source.track,
                    chapter_number,
                    title,
                    source.expected_per_chapter,
                    source.source_name,
                )
            )

    if len(all_questions) != 1380:
        raise ValueError(f"Expected 1,380 questions, extracted {len(all_questions)}")
    return all_questions, chapter_rows


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def build_sql(questions: list[Question], chapters: list[tuple[str, int, str, int, str]]) -> str:
    chapter_values = ",\n".join(
        f"  ({sql_literal(track)}, {number}, {sql_literal(title)}, {count}, {sql_literal(source_name)})"
        for track, number, title, count, source_name in chapters
    )
    question_values = ",\n".join(
        "  ("
        + ", ".join(
            (
                sql_literal(item.track),
                str(item.chapter_number),
                str(item.question_number),
                sql_literal(item.stem),
                sql_literal(item.choice_a),
                sql_literal(item.choice_b),
                sql_literal(item.choice_c),
                sql_literal(item.correct_choice),
            )
        )
        + ")"
        for item in questions
    )
    return f"""-- Generated by scripts/build_chapter_practice_seed.py.
-- Source validation: 600 Citizenship + 780 Permanent Residence questions.

CREATE TABLE IF NOT EXISTS chapter_practice_chapters (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  track text NOT NULL CHECK (track IN ('pr', 'citizenship')),
  chapter_number smallint NOT NULL CHECK (chapter_number > 0),
  title text NOT NULL,
  question_count smallint NOT NULL CHECK (question_count > 0),
  source_name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(track, chapter_number)
);

CREATE TABLE IF NOT EXISTS chapter_practice_questions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  chapter_id uuid NOT NULL REFERENCES chapter_practice_chapters(id) ON DELETE CASCADE,
  question_number smallint NOT NULL CHECK (question_number > 0),
  stem text NOT NULL,
  choice_a text NOT NULL,
  choice_b text NOT NULL,
  choice_c text NOT NULL,
  correct_choice char(1) NOT NULL CHECK (correct_choice IN ('A', 'B', 'C')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(chapter_id, question_number)
);

CREATE INDEX IF NOT EXISTS idx_chapter_practice_chapters_track
  ON chapter_practice_chapters(track, chapter_number);
CREATE INDEX IF NOT EXISTS idx_chapter_practice_questions_chapter
  ON chapter_practice_questions(chapter_id, question_number);

INSERT INTO chapter_practice_chapters(track, chapter_number, title, question_count, source_name)
VALUES
{chapter_values}
ON CONFLICT (track, chapter_number) DO UPDATE SET
  title = EXCLUDED.title,
  question_count = EXCLUDED.question_count,
  source_name = EXCLUDED.source_name,
  updated_at = now();

WITH question_seed(track, chapter_number, question_number, stem, choice_a, choice_b, choice_c, correct_choice) AS (
VALUES
{question_values}
)
INSERT INTO chapter_practice_questions(
  chapter_id, question_number, stem, choice_a, choice_b, choice_c, correct_choice
)
SELECT chapter.id, seed.question_number, seed.stem, seed.choice_a, seed.choice_b, seed.choice_c, seed.correct_choice
FROM question_seed seed
JOIN chapter_practice_chapters chapter
  ON chapter.track = seed.track AND chapter.chapter_number = seed.chapter_number
ON CONFLICT (chapter_id, question_number) DO UPDATE SET
  stem = EXCLUDED.stem,
  choice_a = EXCLUDED.choice_a,
  choice_b = EXCLUDED.choice_b,
  choice_c = EXCLUDED.choice_c,
  correct_choice = EXCLUDED.correct_choice,
  updated_at = now();

DO $$
DECLARE
  citizenship_count integer;
  pr_count integer;
BEGIN
  SELECT COUNT(*) INTO citizenship_count
  FROM chapter_practice_questions question
  JOIN chapter_practice_chapters chapter ON chapter.id = question.chapter_id
  WHERE chapter.track = 'citizenship';
  SELECT COUNT(*) INTO pr_count
  FROM chapter_practice_questions question
  JOIN chapter_practice_chapters chapter ON chapter.id = question.chapter_id
  WHERE chapter.track = 'pr';
  IF citizenship_count <> 600 OR pr_count <> 780 THEN
    RAISE EXCEPTION 'Chapter-practice seed validation failed: citizenship %, PR %', citizenship_count, pr_count;
  END IF;
END $$;
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    questions, chapters = extract_and_validate()
    print(
        f"Validated {len(chapters)} chapters and {len(questions)} questions with matching answer keys."
    )
    if not args.validate_only:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(build_sql(questions, chapters), encoding="utf-8")
        print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
