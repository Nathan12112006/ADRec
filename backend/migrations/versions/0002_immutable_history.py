"""Make saved selection, request, event and dataset provenance records append-only."""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE FUNCTION reject_history_change() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Durable history is immutable' USING ERRCODE = '23514';
        END;
        $$
    """)
    for table in ("datasets", "recommendations", "request_outcomes", "events"):
        op.execute(f"""
            CREATE TRIGGER immutable_{table}
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION reject_history_change()
        """)
        op.execute(f"""
            CREATE TRIGGER no_truncate_{table}
            BEFORE TRUNCATE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION reject_history_change()
        """)


def downgrade() -> None:
    raise RuntimeError("History-preserving migration: downgrade is intentionally unsupported")
