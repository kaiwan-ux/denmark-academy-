from apps.api.routers.mock_ai_bank import (
    GenerateMockBankRequest,
    _clean_display_text,
    _matches_reference,
    _normalize_question,
    _prompt,
    _quality_score,
)


def valid_question():
    return _normalize_question({
        "stem": "Hvilken sammenhæng mellem Folketinget og regeringen følger af parlamentarismen?",
        "choice_a": "Regeringen må ikke have et flertal imod sig i Folketinget",
        "choice_b": "Regeringen udpeger selv alle medlemmer af Folketinget",
        "choice_c": "Folketinget kan kun mødes efter regeringens tilladelse",
        "choice_d": "Regeringen kan ændre Grundloven uden en folkeafstemning",
        "correct_choice": "A",
        "explanation": "KILDE 1 forklarer, at regeringen ikke må have et flertal imod sig.",
        "learning_objective": "parlamentarismens negative flertalsprincip",
        "grounding_source": "KILDE 1",
    })


def test_mock_prompt_uses_qdrant_context_and_cross_bank_avoidance():
    payload = GenerateMockBankRequest(track="citizenship", section="knowledge", count=3)
    prompt = _prompt(payload, 3, "KILDE 1 — Folketinget: parlamentarisme", "- Tidligere spørgsmål")
    assert "AUTORITATIV RAG-KONTEKST FRA QDRANT" in prompt
    assert "KILDE 1 — Folketinget" in prompt
    assert "Tidligere spørgsmål" in prompt
    assert "learning_objective" in prompt
    assert "distraktorer" in prompt


def test_mock_display_text_removes_checkbox_and_choice_label_artifacts():
    assert _clean_display_text("☐. Hvad følger af Grundloven?") == "Hvad følger af Grundloven?"
    assert _clean_display_text("☑ A. Folketinget vedtager love", choice=True) == "Folketinget vedtager love"


def test_mock_quality_requires_grounding_and_balanced_distractors():
    question = valid_question()
    assert _quality_score(question, "knowledge") >= 0.82
    assert _quality_score({**question, "grounding_source": ""}, "knowledge") == 0.0
    assert _quality_score({**question, "choice_b": question["choice_a"]}, "knowledge") == 0.0


def test_mock_cross_bank_semantic_duplicate_is_rejected():
    references = [("Hvordan fungerer parlamentarismen mellem regering og Folketing?", "negativ parlamentarisme")]
    question = valid_question()
    assert _matches_reference(question["stem"], question["learning_objective"], references)


def test_distinct_hard_mock_context_is_accepted():
    references = [("Hvornår afholdes kommunalvalg i Danmark?", "kommunalvalg")]
    question = valid_question()
    assert not _matches_reference(question["stem"], question["learning_objective"], references)

class _RowsResult:
    def __init__(self, rows, one=None):
        self.rows = rows
        self.one = one

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.one


class _ChunkConnection:
    def __init__(self):
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, _params=()):
        self.statements.append(statement)
        return _RowsResult([{
            "text": "Parlamentarisme betyder, at regeringen ikke må have et flertal imod sig.",
            "title": "Det danske demokrati",
            "page_start": 42,
        }])


def test_mock_rag_falls_back_to_learning_chunks_not_stored_questions(monkeypatch):
    from apps.api.routers import mock_ai_bank

    class UnavailableQdrant:
        def search(self, **_kwargs):
            raise RuntimeError("temporary Qdrant outage")

    connection = _ChunkConnection()
    monkeypatch.setattr(mock_ai_bank, "QdrantRepository", lambda: UnavailableQdrant())
    monkeypatch.setattr(mock_ai_bank, "_db_connect", lambda **_kwargs: connection)
    payload = GenerateMockBankRequest(track="citizenship", section="knowledge", count=1)
    context, backend = mock_ai_bank._retrieval_context(payload)
    assert backend == "postgres_official_chunks"
    assert "Parlamentarisme betyder" in context
    assert any("FROM document_chunks" in statement for statement in connection.statements)
    assert all("FROM official_questions" not in statement for statement in connection.statements)


class _MissingOptionalTablesConnection:
    def __init__(self):
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, params=()):
        self.statements.append(statement)
        if "to_regclass" in statement:
            return _RowsResult([], {"relation": None})
        if "FROM ai_generated_questions" in statement:
            raise AssertionError("missing optional table must never be queried")
        return _RowsResult([])


def test_mock_generation_skips_missing_optional_question_banks(monkeypatch):
    from apps.api.routers import mock_ai_bank

    connection = _MissingOptionalTablesConnection()
    monkeypatch.setattr(mock_ai_bank, "_db_connect", lambda **_kwargs: connection)

    assert mock_ai_bank.list_cross_bank_references("citizenship") == []
    assert mock_ai_bank._existing_question_references("citizenship", "knowledge") == []
    assert all("FROM ai_generated_questions" not in statement for statement in connection.statements)

def test_mock_generation_retries_with_the_second_configured_key(monkeypatch):
    import asyncio

    from pydantic import SecretStr

    from apps.api.routers import mock_ai_bank
    from denmark_academy.ai.schemas import AICompletionResponse

    calls = []

    class Manager:
        def get_grok_keys(self):
            return [SecretStr("first"), SecretStr("second")]

        def get_gemini_keys(self):
            return []

    class Gateway:
        async def complete(self, _request):
            calls.append(len(calls) + 1)
            if len(calls) == 1:
                raise RuntimeError("first key rate limited")
            return AICompletionResponse(
                provider="grok",
                model="test",
                content='{"questions":[{"stem":"Spørgsmål"}]}',
                raw={},
                token_usage={},
            )

    monkeypatch.setattr(mock_ai_bank, "get_api_key_manager", lambda: Manager())
    monkeypatch.setattr(mock_ai_bank, "AIGateway", Gateway)
    payload = mock_ai_bank.GenerateMockBankRequest(track="citizenship", count=1)
    result = asyncio.run(mock_ai_bank._generate_with_provider("grok", payload, 1, "KILDE 1", ""))
    assert result == [{"stem": "Spørgsmål"}]
    assert calls == [1, 2]
