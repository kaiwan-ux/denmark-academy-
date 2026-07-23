from denmark_academy.phase2_schemas import PracticeSessionCreate


def test_practice_session_schema_accepts_mock_exam():
    payload = PracticeSessionCreate(
        track="pr",
        user_id="00000000-0000-0000-0000-000000000001",
        mode="mock_exam",
        source_type="blueprint",
        source_id="00000000-0000-0000-0000-000000000002",
        limit=25,
    )
    assert payload.mode == "mock_exam"
    assert payload.track == "pr"
