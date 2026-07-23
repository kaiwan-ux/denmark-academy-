from denmark_academy.blueprints import validate_blueprint_payload


def test_blueprint_validation_rejects_bad_section_total():
    result = validate_blueprint_payload(
        {
            "total_questions": 10,
            "duration_minutes": 30,
            "sections": [
                {"section_key": "core", "question_count": 7},
                {"section_key": "current", "question_count": 2},
            ],
        }
    )
    assert not result.valid
    assert "Section question total" in result.errors[0]


def test_blueprint_validation_accepts_valid_payload():
    result = validate_blueprint_payload(
        {
            "total_questions": 10,
            "duration_minutes": 30,
            "effective_from": "2026-01-01",
            "sections": [{"section_key": "core", "question_count": 10}],
        }
    )
    assert result.valid
