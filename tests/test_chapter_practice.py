from pathlib import Path

import pytest
from pydantic import ValidationError

from apps.api.routers.chapter_practice import (
    MODULE,
    SessionRequest,
    _chapter_question_pattern,
    _question_key,
    _track_question_pattern,
)


def test_sequential_session_requires_a_valid_range() -> None:
    request = SessionRequest(
        track="citizenship",
        chapter_number=2,
        mode="sequential",
        start_number=5,
        end_number=20,
    )
    assert request.start_number == 5
    assert request.end_number == 20

    with pytest.raises(ValidationError):
        SessionRequest(
            track="citizenship",
            chapter_number=2,
            mode="sequential",
            start_number=20,
            end_number=5,
        )


def test_random_session_requires_a_count() -> None:
    request = SessionRequest(track="pr", chapter_number=26, mode="random", count=12)
    assert request.count == 12
    with pytest.raises(ValidationError):
        SessionRequest(track="pr", chapter_number=26, mode="random")


def test_question_progress_key_is_stable() -> None:
    assert _question_key("pr", 4, 17) == "chapter:pr:4:17"


def test_progress_like_wildcards_are_passed_as_query_parameters() -> None:
    assert _track_question_pattern("citizenship") == "chapter:citizenship:%"
    assert _chapter_question_pattern("pr", 4) == "chapter:pr:4:%"


def test_generated_seed_contains_every_validated_question() -> None:
    migration = (
        Path(__file__).parents[1]
        / "packages"
        / "denmark_academy"
        / "db"
        / "migrations"
        / "019_chapter_practice.sql"
    ).read_text(encoding="utf-8")
    assert "citizenship_count <> 600" in migration
    assert "pr_count <> 780" in migration
    assert "Hvilken udvikling viser Harald Blåtands ringborge tydeligst?" in migration
    assert "Hvad betyder undervisningspligten i Danmark?" in migration


def test_chapter_practice_progress_is_isolated_from_past_papers() -> None:
    assert MODULE == "chapter_practice"
    assert MODULE != "past_papers"
    migration = (
        Path(__file__).parents[1]
        / "packages"
        / "denmark_academy"
        / "db"
        / "migrations"
        / "020_isolate_chapter_practice_progress.sql"
    ).read_text(encoding="utf-8")
    assert "SET module = 'chapter_practice'" in migration
    assert "SET module = 'past_papers'" not in migration
