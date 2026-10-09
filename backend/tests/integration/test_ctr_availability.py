from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.core.config import Settings
from app.db.session import Database
from app.main import create_app
from app.models.records import User
from app.seeding import SeedConfig, seed_database


@pytest.mark.parametrize("artifact", ["absent", "missing", "corrupt"])
def test_baseline_recommendations_remain_usable_without_ctr(
    database: Database, database_settings: Settings, tmp_path: Path, artifact: str
) -> None:
    config = SeedConfig(seed=uuid4().int % 2**62, users=1, advertisers=1, ads=2)
    seed_database(database, config, append=True)
    with database.session() as session:
        user_id = session.scalar(select(User.id).where(User.dataset_id == config.dataset_id))
    path = None if artifact == "absent" else tmp_path / artifact
    if artifact == "corrupt":
        assert path is not None
        path.mkdir()
        (path / "manifest.json").write_text("invalid JSON")
    app = create_app(database_settings.model_copy(update={"ctr_model_path": path}))

    def session_dependency() -> Iterator[Session]:
        with database.session() as session:
            yield session

    app.dependency_overrides[get_session] = session_dependency
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/recommendations",
            json={"user_id": user_id},
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert response.status_code == 200
        assert response.json()["selection"]["strategy"] == "interest-overlap"
        assert response.json()["selection"]["predicted_ctr"] is None
