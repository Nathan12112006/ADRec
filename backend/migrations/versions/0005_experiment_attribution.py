"""Persist experiment assignment on ad opportunities and selected ads."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table, constraint in (
        ("recommendations", "recommendation_experiment_attribution"),
        ("request_outcomes", "outcome_experiment_attribution"),
    ):
        op.add_column(table, sa.Column("experiment_id", pg.UUID(), nullable=True))
        op.add_column(table, sa.Column("experiment_variant", sa.Text(), nullable=True))
        op.create_check_constraint(
            constraint,
            table,
            "(experiment_id IS NULL AND experiment_variant IS NULL) OR "
            "(experiment_id IS NOT NULL AND experiment_variant IS NOT NULL AND "
            "experiment_variant IN ('control','treatment'))",
        )
    op.create_index(
        "recommendations_experiment_cohort",
        "recommendations",
        ["experiment_id", "created_at"],
        postgresql_where=sa.text("experiment_id IS NOT NULL"),
    )


def downgrade() -> None:
    raise RuntimeError("Attribution history migration: downgrade is intentionally unsupported")
