"""Persist stable experiment identity and freeze started treatment configuration."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "experiments",
        sa.Column("id", pg.UUID(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "schema_version", sa.Text(), nullable=False, server_default="ranking-experiment-v1"
        ),
        sa.Column(
            "assignment_version", sa.Text(), nullable=False, server_default="sha256-bucket-v1"
        ),
        sa.Column("salt", sa.Text(), nullable=False),
        sa.Column("control_basis_points", sa.Integer(), nullable=False, server_default="5000"),
        sa.Column("control_strategy", sa.Text(), nullable=False, server_default="interest-overlap"),
        sa.Column("treatment_strategy", sa.Text(), nullable=False, server_default="expected-value"),
        sa.Column(
            "control_strategy_version", sa.Text(), nullable=False, server_default="baseline-v1"
        ),
        sa.Column(
            "treatment_strategy_version",
            sa.Text(),
            nullable=False,
            server_default="expected-value-v1",
        ),
        sa.Column("model_id", sa.Text(), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=False, server_default="ctr-logistic-v1"),
        sa.Column("feature_version", sa.Text(), nullable=False, server_default="ctr-features-v1"),
        sa.Column("retrieval_mode", sa.Text(), nullable=False, server_default="exact"),
        sa.Column("candidate_limit", sa.Integer(), nullable=False, server_default="500"),
        sa.Column("search_limit", sa.Integer(), nullable=False, server_default="4000"),
        sa.Column("hnsw_ef_search", sa.Integer(), nullable=True),
        sa.Column("vector_version", sa.Text(), nullable=False, server_default="binary-cosine-v1"),
        sa.Column("vocabulary_version", sa.Text(), nullable=False, server_default="topics-v1"),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "schema_version = 'ranking-experiment-v1'", name="experiment_schema_version"
        ),
        sa.CheckConstraint(
            "assignment_version = 'sha256-bucket-v1'", name="experiment_assignment_version"
        ),
        sa.CheckConstraint("length(salt) = 64 AND salt ~ '^[0-9a-f]{64}$'", name="experiment_salt"),
        sa.CheckConstraint(
            "control_basis_points BETWEEN 0 AND 10000", name="experiment_allocation"
        ),
        sa.CheckConstraint("length(btrim(name)) BETWEEN 1 AND 255", name="experiment_name"),
        sa.CheckConstraint(
            "length(model_id) = 64 AND model_id ~ '^[0-9a-f]{64}$'", name="experiment_model_id"
        ),
        sa.CheckConstraint(
            "control_strategy IN ('interest-overlap', 'expected-value') AND "
            "treatment_strategy IN ('interest-overlap', 'expected-value')",
            name="experiment_strategies",
        ),
        sa.CheckConstraint(
            "length(control_strategy_version) BETWEEN 1 AND 128 AND "
            "length(treatment_strategy_version) BETWEEN 1 AND 128 AND "
            "length(model_version) BETWEEN 1 AND 128 AND length(feature_version) "
            "BETWEEN 1 AND 128 AND length(vector_version) BETWEEN 1 AND 128 AND "
            "length(vocabulary_version) BETWEEN 1 AND 128",
            name="experiment_versions",
        ),
        sa.CheckConstraint(
            "retrieval_mode IN ('exact', 'hnsw') AND candidate_limit BETWEEN 1 AND "
            "500 AND search_limit BETWEEN candidate_limit AND 1000000",
            name="experiment_retrieval",
        ),
        sa.CheckConstraint(
            "(retrieval_mode = 'exact' AND hnsw_ef_search IS NULL) OR "
            "(retrieval_mode = 'hnsw' AND hnsw_ef_search IS NOT NULL AND "
            "hnsw_ef_search BETWEEN 1 AND 1000000)",
            name="experiment_hnsw",
        ),
        sa.CheckConstraint(
            "(status = 'draft' AND started_at IS NULL AND stopped_at IS NULL) OR "
            "(status = 'running' AND started_at IS NOT NULL AND stopped_at IS NULL) "
            "OR (status = 'stopped' AND started_at IS NOT NULL AND stopped_at IS "
            "NOT NULL)",
            name="experiment_lifecycle",
        ),
        sa.CheckConstraint(
            "(started_at IS NULL OR started_at >= created_at) AND (stopped_at IS "
            "NULL OR stopped_at >= started_at)",
            name="experiment_time_order",
        ),
    )
    op.create_index(
        "one_running_ranking_experiment",
        "experiments",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
    )
    op.execute("""
        CREATE FUNCTION preserve_experiment_identity() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.status <> 'draft' THEN
                    RAISE EXCEPTION 'Experiments begin as drafts' USING ERRCODE = '23514';
                END IF;
                RETURN NEW;
            END IF;
            IF NEW.id IS DISTINCT FROM OLD.id
                OR NEW.schema_version IS DISTINCT FROM OLD.schema_version
                OR NEW.assignment_version IS DISTINCT FROM OLD.assignment_version
                OR NEW.salt IS DISTINCT FROM OLD.salt
                OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
                RAISE EXCEPTION 'Experiment identity is immutable' USING ERRCODE = '23514';
            END IF;
            IF OLD.status = 'stopped' AND NEW IS DISTINCT FROM OLD THEN
                RAISE EXCEPTION 'Stopped experiments are immutable' USING ERRCODE = '23514';
            END IF;
            IF OLD.status = 'running' AND NEW IS DISTINCT FROM OLD THEN
                IF NEW.status <> 'stopped' OR
                    (to_jsonb(NEW) - 'status' - 'stopped_at') IS DISTINCT FROM
                    (to_jsonb(OLD) - 'status' - 'stopped_at') THEN
                    RAISE EXCEPTION 'Started treatment is immutable' USING ERRCODE = '23514';
                END IF;
            END IF;
            IF OLD.status = 'draft' AND NEW.status NOT IN ('draft', 'running') THEN
                RAISE EXCEPTION 'Invalid experiment transition' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER preserve_experiment_identity BEFORE INSERT OR UPDATE ON experiments
        FOR EACH ROW EXECUTE FUNCTION preserve_experiment_identity()
    """)
    op.execute("""
        CREATE TRIGGER immutable_experiment_history BEFORE DELETE ON experiments
        FOR EACH ROW EXECUTE FUNCTION reject_history_change()
    """)
    op.execute("""
        CREATE TRIGGER no_truncate_experiments BEFORE TRUNCATE ON experiments
        FOR EACH STATEMENT EXECUTE FUNCTION reject_history_change()
    """)


def downgrade() -> None:
    raise RuntimeError("History-preserving migration: downgrade is intentionally unsupported")
