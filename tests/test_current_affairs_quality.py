import asyncio
from types import SimpleNamespace

import pytest

from denmark_academy.ai.mcq_generator import MCQGenerator
from denmark_academy.current_affairs.quality import QuestionQualityValidator


def question(stem: str, objective: str, difficulty: str = "medium", choices=None):
    choices = choices or ("Folketinget vedtager love", "Kommunen vedtager love", "Domstolene vedtager love")
    return SimpleNamespace(
        stem=stem,
        learning_objective=objective,
        difficulty=difficulty,
        topic="demokrati",
        choice_a=choices[0],
        choice_b=choices[1],
        choice_c=choices[2],
    )


def test_semantic_and_objective_duplicates_are_rejected():
    validator = QuestionQualityValidator()
    existing = [("Hvordan vedtages en lov i Folketinget?", "Folketingets lovgivningsproces")]
    duplicate = question(
        "Hvordan bliver et lovforslag vedtaget af Folketinget?",
        "Folketingets lovgivningsproces",
    )
    assert validator.is_duplicate(duplicate.stem, duplicate.learning_objective, existing)


def test_selection_balances_difficulty_and_rejects_repeated_objectives():
    validator = QuestionQualityValidator()
    candidates = [
        question("Hvem vedtager lovene i Danmark?", "lovgivende magt", "easy"),
        question("Hvordan kontrollerer Folketinget regeringen?", "parlamentarisk kontrol", "medium"),
        question("Hvorfor beskytter magtens tredeling demokratiet?", "magtens tredeling", "hard"),
        question("Hvordan vedtager Folketinget nye love?", "lovgivende magt", "medium"),
    ]
    selected = validator.select_unique(candidates, [], limit=3)
    assert len(selected) == 3
    assert {item.difficulty for item in selected} == {"easy", "medium", "hard"}


def test_implausible_duplicate_choices_fail_validation():
    validator = QuestionQualityValidator()
    invalid = question("Hvem vedtager lovene?", "lovgivning", choices=("Folketinget", "Folketinget", "Kommunen"))
    assert not validator.valid_choices(invalid)


def test_rag_generator_requires_three_distinct_choices():
    generator = object.__new__(MCQGenerator)
    valid = {
        "choice_a": "Folketinget vedtager loven",
        "choice_b": "Regeringen dømmer i sagen",
        "choice_c": "Kommunen ændrer grundloven",
        "correct_choice": "A",
    }
    assert generator._valid_question(valid)
    assert not generator._valid_question({**valid, "choice_b": valid["choice_a"]})

async def _no_refresh(**_kwargs):
    return {"status": "ready"}


def _practice_row(index: int, stem: str | None = None, objective: str | None = None):
    return {
        "id": f"00000000-0000-0000-0000-{index:012d}",
        "question_stem": stem or [
            "Who supervises parliamentary committee work?",
            "What is the central bank responsible for?",
            "When are municipal elections normally held?",
            "Why did Denmark expand offshore wind capacity?",
            "Which authority coordinates national health planning?",
            "What constitutional duty belongs to the monarch?",
            "How are collective labour agreements negotiated?",
            "Which institution allocates public education funding?",
            "Why did Denmark join the new defence agreement?",
            "How does the tax authority verify annual returns?",
            "Which measure protects coastal biodiversity?",
            "What right governs processing personal information?",
        ][index],
        "learning_objective": objective or [
            "parliamentary oversight", "central bank mandate", "municipal elections",
            "renewable energy policy", "public health planning", "royal constitutional role",
            "labour market agreement", "education funding model", "defence cooperation",
            "tax administration rules", "environmental protection", "digital privacy rights",
        ][index],
        "choice_a": "Svar A",
        "choice_b": "Svar B",
        "choice_c": "Svar C",
        "topic": f"topic {index}",
        "difficulty": "medium",
        "article_title": "Article",
        "article_url": "https://example.com/article",
    }


def test_current_affairs_session_contract_returns_exact_requested_count():
    from denmark_academy.current_affairs import service as service_module
    from denmark_academy.current_affairs.models import PracticeRequest

    instance = object.__new__(service_module.CurrentAffairsService)
    instance.ensure_priority_pool = _no_refresh
    expected = {
        "session_id": "00000000-0000-0000-0000-000000000099",
        "questions": [_practice_row(i) for i in range(5)],
        "total": 5,
        "pool_total": 30,
        "cycle_reset": False,
    }
    instance._create_persistent_session = lambda *_args, **_kwargs: expected
    result = asyncio.run(instance.start_practice_session(
        PracticeRequest(count=5, refresh_articles=False),
        "00000000-0000-0000-0000-000000000001",
    ))
    assert result["total"] == 5
    assert len(result["questions"]) == 5


def test_current_affairs_session_rejects_truncated_pool():
    from denmark_academy.current_affairs import service as service_module
    from denmark_academy.current_affairs.models import PracticeRequest

    instance = object.__new__(service_module.CurrentAffairsService)
    instance.ensure_priority_pool = _no_refresh
    instance._create_persistent_session = lambda *_args, **_kwargs: None
    with pytest.raises(ValueError, match="Could not prepare 5"):
        asyncio.run(instance.start_practice_session(
            PracticeRequest(count=5, refresh_articles=False),
            "00000000-0000-0000-0000-000000000001",
        ))


def test_consecutive_sessions_are_disjoint_and_exact_sized():
    validator = QuestionQualityValidator()
    pool = [_practice_row(index) for index in range(12)]
    served: set[str] = set()

    def next_session(count: int) -> list[dict]:
        available = [row for row in pool if row["id"] not in served]
        selected = validator.select_session_rows(available, count)
        served.update(row["id"] for row in selected)
        return selected

    first = next_session(5)
    second = next_session(5)
    assert len(first) == len(second) == 5
    assert {row["id"] for row in first}.isdisjoint(row["id"] for row in second)
    assert [row["id"] for row in first] != [row["id"] for row in second]


def test_session_filter_removes_exact_semantic_and_objective_duplicates():
    validator = QuestionQualityValidator(similarity_threshold=0.85)
    rows = [
        _practice_row(1, "Hvordan vedtages en lov i Folketinget?", "Folketingets lovgivningsproces"),
        _practice_row(2, "Hvordan vedtages en lov i Folketinget?", "gentaget ordlyd"),
        _practice_row(3, "Hvordan bliver et lovforslag vedtaget af Folketinget?", "anden formulering"),
        _practice_row(4, "Hvilken rolle har udvalgene før en lov vedtages?", "Folketingets lovgivningsproces"),
        _practice_row(5, "Hvad er Nationalbankens vigtigste opgave?", "Nationalbankens ansvar"),
    ]
    selected = validator.select_session_rows(rows, 5)
    selected_ids = {row["id"] for row in selected}
    assert rows[0]["id"] in selected_ids
    assert rows[1]["id"] not in selected_ids
    assert rows[2]["id"] not in selected_ids
    assert rows[3]["id"] not in selected_ids
    assert rows[4]["id"] in selected_ids

def test_objective_fallback_keeps_exact_count_without_semantic_duplicates():
    validator = QuestionQualityValidator(similarity_threshold=0.85)
    rows = [
        _practice_row(0, objective="recent government decision"),
        _practice_row(1, objective="recent government decision"),
        _practice_row(2, objective="recent government decision"),
    ]
    strict = validator.select_session_rows(rows, 3)
    fallback = validator.select_session_rows(rows, 3, enforce_objectives=False)
    assert len(strict) == 1
    assert len(fallback) == 3
    for index, left in enumerate(fallback):
        for right in fallback[index + 1:]:
            assert validator.similarity(left["question_stem"], right["question_stem"]) < 0.85

class _PsycopgCursorShape:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def executemany(self, statement, records):
        self.calls.append((statement, records))


class _PsycopgConnectionShape:
    """Matches psycopg.Connection: bulk execution is available only on cursor()."""

    def __init__(self):
        self.bulk_cursor = _PsycopgCursorShape()

    def cursor(self):
        return self.bulk_cursor


def test_served_history_bulk_insert_uses_psycopg_cursor():
    from denmark_academy.current_affairs.service import CurrentAffairsService

    connection = _PsycopgConnectionShape()
    records = [("user", "question", "fingerprint", 1, "session")]
    CurrentAffairsService._record_served_questions(connection, records)
    assert len(connection.bulk_cursor.calls) == 1
    statement, inserted = connection.bulk_cursor.calls[0]
    assert "current_affairs_served_questions" in statement
    assert inserted == records

def test_current_affairs_tries_second_groq_key_after_first_fails():
    from pydantic import SecretStr

    from denmark_academy.current_affairs.models import AIArticleAnalysis
    from denmark_academy.current_affairs.processor import AIProcessor

    class Keys:
        def __init__(self):
            self.keys = [SecretStr("first"), SecretStr("second")]
            self.index = 0

        def get_grok_keys(self):
            return self.keys

        def get_gemini_keys(self):
            return []

        def get_next_grok_key(self):
            key = self.keys[self.index % len(self.keys)]
            self.index += 1
            return key

    processor = object.__new__(AIProcessor)
    processor.api_key_manager = Keys()
    calls = []

    async def call_groq(_prompt, key):
        calls.append(key.get_secret_value())
        if key.get_secret_value() == "first":
            raise RuntimeError("rate limited")
        return AIArticleAnalysis(is_relevant=False)

    processor._call_grok = call_groq
    result = asyncio.run(processor._call_provider_with_key_fallback("grok", "prompt"))
    assert result.is_relevant is False
    assert calls == ["first", "second"]


def test_priority_refresh_checks_rss_even_when_the_question_pool_is_populated():
    from denmark_academy.current_affairs.service import CurrentAffairsService

    service = object.__new__(CurrentAffairsService)
    service.cleanup_expired = lambda: {"expired": 0}
    captured = []

    async def refresh(**kwargs):
        captured.append(kwargs)
        return {"fetched": 6, "new": 1}

    service.fetch_and_process_articles = refresh
    CurrentAffairsService._last_priority_refresh = None
    result = asyncio.run(service.ensure_priority_pool(force=True))
    assert result["fetched"] == 6
    assert captured == [{"max_articles": 6, "regenerate_existing": False}]
