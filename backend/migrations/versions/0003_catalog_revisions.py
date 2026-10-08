"""Track inventory freshness independently of immutable dataset provenance."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "catalog_revisions",
        sa.Column("dataset_id", pg.UUID(), sa.ForeignKey("datasets.id"), primary_key=True),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="0"),
        sa.CheckConstraint("revision >= 0", name="catalog_revision_nonnegative"),
    )
    op.execute("INSERT INTO catalog_revisions (dataset_id) SELECT id FROM datasets")
    op.execute("""
        CREATE FUNCTION initialize_catalog_revision() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            INSERT INTO catalog_revisions (dataset_id) VALUES (NEW.id);
            RETURN NULL;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER initialize_catalog_revision AFTER INSERT ON datasets
        FOR EACH ROW EXECUTE FUNCTION initialize_catalog_revision()
    """)
    op.execute("""
        CREATE FUNCTION advance_catalog_revision() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'UPDATE' AND NEW IS NOT DISTINCT FROM OLD THEN
                RETURN NULL;
            END IF;
            IF TG_OP <> 'INSERT' THEN
                UPDATE catalog_revisions SET revision = revision + 1
                WHERE dataset_id = OLD.dataset_id;
            END IF;
            IF TG_OP = 'INSERT' OR (TG_OP = 'UPDATE' AND NEW.dataset_id <> OLD.dataset_id) THEN
                UPDATE catalog_revisions SET revision = revision + 1
                WHERE dataset_id = NEW.dataset_id;
            END IF;
            RETURN NULL;
        END;
        $$
    """)
    op.execute("""
        CREATE FUNCTION invalidate_truncated_catalogs() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            UPDATE catalog_revisions SET revision = revision + 1;
            RETURN NULL;
        END;
        $$
    """)
    for table in ("ads", "advertisers"):
        op.execute(f"""
            CREATE TRIGGER advance_{table}_catalog_revision
            AFTER INSERT OR UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION advance_catalog_revision()
        """)
        op.execute(f"""
            CREATE TRIGGER invalidate_{table}_catalogs BEFORE TRUNCATE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION invalidate_truncated_catalogs()
        """)


def downgrade() -> None:
    raise RuntimeError("History-preserving migration: downgrade is intentionally unsupported")
