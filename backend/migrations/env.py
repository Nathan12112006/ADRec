"""Explicit migrations only. Never create tables at application startup."""

from alembic import context

from app.core.config import Settings, load_settings
from app.db.session import Database
from app.models.records import Base

config = context.config
settings: Settings = config.attributes.get("settings") or load_settings()
use_test_database = config.attributes.get("use_test_database", False)
if "database" in context.get_x_argument(as_dictionary=True):
    target = context.get_x_argument(as_dictionary=True)["database"]
    if target not in {"application", "test"}:
        raise ValueError("database must be application or test")
    use_test_database = target == "test"

if context.is_offline_mode():
    context.configure(dialect_name="postgresql", literal_binds=True, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
else:
    database = Database(settings, use_test_database=use_test_database)
    try:
        with database.engine.connect() as connection:
            context.configure(connection=connection, target_metadata=Base.metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        database.dispose()
