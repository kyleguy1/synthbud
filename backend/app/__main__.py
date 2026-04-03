import uvicorn

from .config import get_settings
from .main import app


def _should_reload(environment: str) -> bool:
    return environment.lower() in {"dev", "development", "local"}


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=_should_reload(settings.environment),
    )
