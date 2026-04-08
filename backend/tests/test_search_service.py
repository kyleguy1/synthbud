from app.services.search import build_sound_search_query


def test_build_sound_search_query_basic():
    class DummyCountResult:
        def scalar_one(self):
            return 1

    class DummySession:
        def execute(self, statement):
            statement_text = str(statement)
            if "count(" in statement_text.lower():
                return DummyCountResult()
            return []

    db = DummySession()
    stmt, total = build_sound_search_query(
        db,
        q="synth",
        tags=["synth"],
        min_brightness=1000.0,
        max_brightness=5000.0,
    )
    assert stmt is not None
    assert total == 1
    statement_text = str(stmt)
    assert "raw_tags" in statement_text
