from typing import Annotated

from fastapi import Depends
from fastapi.testclient import TestClient

from app.api.dependencies import get_settings
from app.core.config import Settings
from app.main import create_app


def test_factory_provides_isolated_settings_to_synchronous_routes() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://demo:secret@localhost/adflow",
        test_database_url="postgresql+psycopg://demo:secret@localhost/adflow_test",
        log_level="WARNING",
    )
    app = create_app(settings)

    @app.get("/test-settings")
    def read_settings(config: Annotated[Settings, Depends(get_settings)]) -> dict[str, str]:
        return {"level": config.log_level}

    with TestClient(app) as client:
        assert client.get("/test-settings").json() == {"level": "WARNING"}
        assert client.get("/openapi.json").status_code == 200
        assert "secret" not in client.get("/openapi.json").text

    other_app = create_app(settings.model_copy(update={"log_level": "DEBUG"}))
    assert other_app is not app
    with TestClient(other_app) as client:
        assert client.get("/test-settings").status_code == 404
