"""Verify additive migration, stored assignment and constraints in an isolated runtime."""

import io
import json
import platform
import subprocess
import sys
from pathlib import Path
from uuid import UUID

from alembic import command
from alembic.config import Config
from app.core.config import load_settings
from app.db.session import Database
from app.experiments.assignment import AssignmentConfig, assign_variant
from app.models.records import Dataset, Experiment
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

settings = load_settings(env_file=None)
assert settings.database_url.get_secret_value().endswith("/adflow_ticket27_smoke")
database = Database(settings)
users = [1, 2, 3, 42, 9223372036854775807]
if len(sys.argv) > 1 and sys.argv[1] == "--read":
    with database.session() as session:
        record = session.get(Experiment, UUID(sys.argv[2]))
        assert record is not None
        config = AssignmentConfig.model_validate(record)
        print(
            json.dumps(
                {
                    "config": config.model_dump(mode="json"),
                    "variants": [assign_variant(user, config) for user in users],
                }
            )
        )
    database.dispose()
    sys.exit(0)

assert not inspect(database.engine).has_table("alembic_version"), (
    "Use a fresh isolated smoke database"
)
migration = Config(
    str(Path(__import__("app").__file__).resolve().parents[1] / "alembic.ini"),
    stdout=io.StringIO(),
)
migration.attributes["settings"] = settings
command.upgrade(migration, "0003")
with database.transaction() as session:
    original = Dataset(
        seed=27,
        generator_version="pre-experiment-smoke",
        configuration={"retained": True},
    )
    session.add(original)
    session.flush()
    dataset_id, created_at = original.id, original.created_at
command.upgrade(migration, "head")
with database.transaction() as session:
    saved = session.get(Dataset, dataset_id)
    assert saved is not None and saved.created_at == created_at
    assert saved.configuration == {"retained": True}
    records = [
        Experiment(name="Schema-only fixture", model_id="a" * 64) for _ in range(2)
    ]
    session.add_all(records)
    session.flush()
    identity, other_id = records[0].id, records[1].id
    config = AssignmentConfig.model_validate(records[0])
    expected = {
        "config": config.model_dump(mode="json"),
        "variants": [assign_variant(user, config) for user in users],
    }
    assert (
        records[0].control_basis_points == 5000
        and records[0].schema_version == "ranking-experiment-v1"
    )
    session.execute(
        text(
            "UPDATE experiments SET status='running', started_at=clock_timestamp() WHERE id=:id"
        ),
        {"id": identity},
    )
restarted = json.loads(
    subprocess.check_output(
        [sys.executable, str(Path(__file__).resolve()), "--read", str(identity)],
        text=True,
        timeout=30,
    )
)
assert restarted == expected
rejections = {}
for name, sql, target in [
    (
        "second_running",
        "UPDATE experiments SET status='running', started_at=clock_timestamp() WHERE id=:id",
        other_id,
    ),
    (
        "changed_treatment",
        "UPDATE experiments SET control_basis_points=0 WHERE id=:id",
        identity,
    ),
    ("deleted_history", "DELETE FROM experiments WHERE id=:id", identity),
]:
    try:
        with database.transaction() as session:
            session.execute(text(sql), {"id": target})
    except IntegrityError as error:
        rejections[name] = error.orig.sqlstate
    else:
        raise AssertionError(name)
with database.transaction() as session:
    session.execute(
        text(
            "UPDATE experiments SET status='stopped', stopped_at=clock_timestamp() WHERE id=:id"
        ),
        {"id": identity},
    )
    saved_experiment = session.get(Experiment, identity)
    assert saved_experiment is not None and saved_experiment.status == "stopped"
    assert saved_experiment.model_id == "a" * 64
command.check(migration)
database.dispose()
print(
    json.dumps(
        {
            "passed": True,
            "python": platform.python_version(),
            "upgrade": "0003 to 0004 after inserting durable dataset history",
            "old_dataset_id": str(dataset_id),
            "old_dataset_unchanged": True,
            "stored_assignment": expected,
            "subprocess_assignment_equal": True,
            "rejections_sqlstate": rejections,
            "stopped_history_retained": True,
            "schema_matches_metadata": True,
            "limitation": "Schema smoke only; model_id is a valid-format fixture. API activation/model validation and serving routing belong to tickets28/29.",
        },
        sort_keys=True,
    )
)
