from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base, Sound, SoundFeatures
from app.services.search import build_sound_search_query


def setup_in_memory_db() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal()


def test_build_sound_search_query_basic():
    db = setup_in_memory_db()
    try:
        sound = Sound(
            source="test",
            source_sound_id="1",
            name="Bright synth pluck",
            description="A bright synth pluck",
            tags=["synth", "pluck"],
            duration_sec=1.5,
        )
        db.add(sound)
        db.flush()
        features = SoundFeatures(
            sound_id=sound.id,
            spectral_centroid=3000.0,
        )
        db.add(features)
        db.commit()

        stmt, total = build_sound_search_query(
            db,
            q="synth",
            tags=["synth"],
            min_brightness=1000.0,
            max_brightness=5000.0,
        )
        rows = db.execute(stmt).all()
        assert total == 1
        assert len(rows) == 1
    finally:
        db.close()

