from app.routers.meta import list_tags


def test_list_tags_returns_empty_list_when_no_tags():
    class EmptyResult:
        def all(self):
            return []

    class DummySession:
        def execute(self, *_args, **_kwargs):
            return EmptyResult()

    assert list_tags(db=DummySession()) == []
