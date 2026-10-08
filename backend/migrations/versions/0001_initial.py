"""Initial durable lifecycle schema."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "datasets",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("seed", sa.BigInteger(), nullable=False),
        sa.Column("generator_version", sa.Text(), nullable=False),
        sa.Column("configuration", pg.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("jsonb_typeof(configuration) = 'object'", name="dataset_config_object"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("dataset_id", pg.UUID(), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("interests", pg.ARRAY(sa.Text()), nullable=False),
        sa.Column("category_preferences", pg.ARRAY(sa.Text()), nullable=False),
        sa.Column("age_group", sa.Text(), nullable=False),
        sa.Column("country", sa.Text(), nullable=False),
        sa.Column("device", sa.Text(), nullable=False),
        sa.UniqueConstraint("id", "dataset_id", name="user_dataset_identity"),
        sa.CheckConstraint("id > 0", name="user_positive_id"),
    )
    op.create_table(
        "advertisers",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("dataset_id", pg.UUID(), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("id", "dataset_id", name="advertiser_dataset_identity"),
        sa.CheckConstraint("id > 0", name="advertiser_positive_id"),
    )
    op.create_table(
        "ads",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("dataset_id", pg.UUID(), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("advertiser_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("target_url", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("interests", pg.ARRAY(sa.Text()), nullable=False),
        sa.Column("bid", sa.Numeric(12, 4), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(
            ["advertiser_id", "dataset_id"], ["advertisers.id", "advertisers.dataset_id"]
        ),
        sa.UniqueConstraint("id", "dataset_id", name="ad_dataset_identity"),
        sa.CheckConstraint("bid >= 0 AND bid <> 'NaN'::numeric", name="ad_nonnegative_bid"),
        sa.CheckConstraint("id > 0", name="ad_positive_id"),
    )
    op.create_index("ix_ads_advertiser_id", "ads", ["advertiser_id"])
    op.create_table(
        "recommendations",
        sa.Column("id", pg.UUID(), primary_key=True),
        sa.Column("dataset_id", pg.UUID(), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("ad_id", sa.BigInteger(), nullable=False),
        sa.Column("bid", sa.Numeric(12, 4), nullable=False),
        sa.Column("selected_ad", pg.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["user_id", "dataset_id"], ["users.id", "users.dataset_id"]),
        sa.ForeignKeyConstraint(["ad_id", "dataset_id"], ["ads.id", "ads.dataset_id"]),
        sa.UniqueConstraint("id", "user_id", name="recommendation_user_identity"),
        sa.CheckConstraint("bid >= 0 AND bid <> 'NaN'::numeric", name="selection_nonnegative_bid"),
        sa.CheckConstraint(
            "jsonb_typeof(selected_ad) = 'object'", name="selection_snapshot_object"
        ),
    )
    op.create_index("ix_recommendations_user_id", "recommendations", ["user_id"])
    op.create_index("ix_recommendations_ad_id", "recommendations", ["ad_id"])
    op.create_index("ix_recommendations_created_at", "recommendations", ["created_at"])
    op.create_table(
        "request_outcomes",
        sa.Column("request_key", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("recommendation_id", pg.UUID(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["recommendation_id", "user_id"], ["recommendations.id", "recommendations.user_id"]
        ),
        sa.UniqueConstraint("recommendation_id", name="one_outcome_per_recommendation"),
        sa.CheckConstraint("length(request_key) BETWEEN 1 AND 255", name="bounded_request_key"),
    )
    op.create_index("ix_request_outcomes_user_id", "request_outcomes", ["user_id"])
    op.create_table(
        "events",
        sa.Column(
            "recommendation_id", pg.UUID(), sa.ForeignKey("recommendations.id"), primary_key=True
        ),
        sa.Column("event_type", sa.Text(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("simulated_revenue", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.CheckConstraint("event_type IN ('impression', 'click')", name="valid_event_type"),
        sa.CheckConstraint(
            "simulated_revenue >= 0 AND simulated_revenue <> 'NaN'::numeric",
            name="event_nonnegative_revenue",
        ),
        sa.CheckConstraint(
            "event_type = 'click' OR simulated_revenue = 0", name="only_click_has_revenue"
        ),
    )


def downgrade() -> None:
    raise RuntimeError("History-preserving migration: downgrade is intentionally unsupported")
