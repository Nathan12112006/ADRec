"""Typed PostgreSQL records; historical exposures live outside these tables."""

from datetime import datetime
from decimal import Decimal
from secrets import token_hex
from typing import Any, Literal
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
    true,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Dataset(Base):
    __tablename__ = "datasets"
    __table_args__ = (
        CheckConstraint("jsonb_typeof(configuration) = 'object'", name="dataset_config_object"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    seed: Mapped[int] = mapped_column(BigInteger)
    generator_version: Mapped[str] = mapped_column(Text)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CatalogRevision(Base):
    __tablename__ = "catalog_revisions"
    __table_args__ = (CheckConstraint("revision >= 0", name="catalog_revision_nonnegative"),)

    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("datasets.id"), primary_key=True)
    revision: Mapped[int] = mapped_column(BigInteger, server_default="0")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("id", "dataset_id", name="user_dataset_identity"),
        CheckConstraint("id > 0", name="user_positive_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("datasets.id"))
    interests: Mapped[list[str]] = mapped_column(ARRAY(Text))
    category_preferences: Mapped[list[str]] = mapped_column(ARRAY(Text))
    age_group: Mapped[str] = mapped_column(Text)
    country: Mapped[str] = mapped_column(Text)
    device: Mapped[str] = mapped_column(Text)


class Advertiser(Base):
    __tablename__ = "advertisers"
    __table_args__ = (
        UniqueConstraint("id", "dataset_id", name="advertiser_dataset_identity"),
        CheckConstraint("id > 0", name="advertiser_positive_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("datasets.id"))
    name: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(server_default=true())


class Ad(Base):
    __tablename__ = "ads"
    __table_args__ = (
        ForeignKeyConstraint(
            ["advertiser_id", "dataset_id"], ["advertisers.id", "advertisers.dataset_id"]
        ),
        UniqueConstraint("id", "dataset_id", name="ad_dataset_identity"),
        CheckConstraint("bid >= 0 AND bid <> 'NaN'::numeric", name="ad_nonnegative_bid"),
        CheckConstraint("id > 0", name="ad_positive_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("datasets.id"))
    advertiser_id: Mapped[int] = mapped_column(BigInteger, index=True)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    target_url: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    interests: Mapped[list[str]] = mapped_column(ARRAY(Text))
    bid: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    active: Mapped[bool] = mapped_column(server_default=true())


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        ForeignKeyConstraint(["user_id", "dataset_id"], ["users.id", "users.dataset_id"]),
        ForeignKeyConstraint(["ad_id", "dataset_id"], ["ads.id", "ads.dataset_id"]),
        UniqueConstraint("id", "user_id", name="recommendation_user_identity"),
        CheckConstraint("bid >= 0 AND bid <> 'NaN'::numeric", name="selection_nonnegative_bid"),
        CheckConstraint("jsonb_typeof(selected_ad) = 'object'", name="selection_snapshot_object"),
        CheckConstraint(
            "(experiment_id IS NULL AND experiment_variant IS NULL) OR "
            "(experiment_id IS NOT NULL AND experiment_variant IS NOT NULL AND "
            "experiment_variant IN ('control','treatment'))",
            name="recommendation_experiment_attribution",
        ),
        Index(
            "recommendations_experiment_cohort",
            "experiment_id",
            "created_at",
            postgresql_where=text("experiment_id IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("datasets.id"))
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    ad_id: Mapped[int] = mapped_column(BigInteger, index=True)
    bid: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    selected_ad: Mapped[dict[str, Any]] = mapped_column(JSONB)
    experiment_id: Mapped[UUID | None] = mapped_column()
    experiment_variant: Mapped[Literal["control", "treatment"] | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class RequestOutcome(Base):
    __tablename__ = "request_outcomes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["recommendation_id", "user_id"], ["recommendations.id", "recommendations.user_id"]
        ),
        UniqueConstraint("recommendation_id", name="one_outcome_per_recommendation"),
        CheckConstraint("length(request_key) BETWEEN 1 AND 255", name="bounded_request_key"),
        CheckConstraint(
            "(experiment_id IS NULL AND experiment_variant IS NULL) OR "
            "(experiment_id IS NOT NULL AND experiment_variant IS NOT NULL AND "
            "experiment_variant IN ('control','treatment'))",
            name="outcome_experiment_attribution",
        ),
    )

    request_key: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    recommendation_id: Mapped[UUID | None] = mapped_column()
    experiment_id: Mapped[UUID | None] = mapped_column()
    experiment_variant: Mapped[Literal["control", "treatment"] | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("event_type IN ('impression', 'click')", name="valid_event_type"),
        CheckConstraint(
            "simulated_revenue >= 0 AND simulated_revenue <> 'NaN'::numeric",
            name="event_nonnegative_revenue",
        ),
        CheckConstraint(
            "event_type = 'click' OR simulated_revenue = 0", name="only_click_has_revenue"
        ),
    )

    recommendation_id: Mapped[UUID] = mapped_column(
        ForeignKey("recommendations.id"), primary_key=True
    )
    event_type: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    simulated_revenue: Mapped[Decimal] = mapped_column(Numeric(12, 4), server_default="0")


class Experiment(Base):
    __tablename__ = "experiments"
    __table_args__ = (
        CheckConstraint(
            "schema_version = 'ranking-experiment-v1'", name="experiment_schema_version"
        ),
        CheckConstraint(
            "assignment_version = 'sha256-bucket-v1'", name="experiment_assignment_version"
        ),
        CheckConstraint("length(salt) = 64 AND salt ~ '^[0-9a-f]{64}$'", name="experiment_salt"),
        CheckConstraint("control_basis_points BETWEEN 0 AND 10000", name="experiment_allocation"),
        CheckConstraint("length(btrim(name)) BETWEEN 1 AND 255", name="experiment_name"),
        CheckConstraint(
            "length(model_id) = 64 AND model_id ~ '^[0-9a-f]{64}$'", name="experiment_model_id"
        ),
        CheckConstraint(
            "control_strategy IN ('interest-overlap', 'expected-value') AND "
            "treatment_strategy IN ('interest-overlap', 'expected-value')",
            name="experiment_strategies",
        ),
        CheckConstraint(
            "length(control_strategy_version) BETWEEN 1 AND 128 AND "
            "length(treatment_strategy_version) BETWEEN 1 AND 128 AND "
            "length(model_version) BETWEEN 1 AND 128 AND length(feature_version) "
            "BETWEEN 1 AND 128 AND length(vector_version) BETWEEN 1 AND 128 AND "
            "length(vocabulary_version) BETWEEN 1 AND 128",
            name="experiment_versions",
        ),
        CheckConstraint(
            "retrieval_mode IN ('exact', 'hnsw') AND candidate_limit BETWEEN 1 AND "
            "500 AND search_limit BETWEEN candidate_limit AND 1000000",
            name="experiment_retrieval",
        ),
        CheckConstraint(
            "(retrieval_mode = 'exact' AND hnsw_ef_search IS NULL) OR "
            "(retrieval_mode = 'hnsw' AND hnsw_ef_search IS NOT NULL AND "
            "hnsw_ef_search BETWEEN 1 AND 1000000)",
            name="experiment_hnsw",
        ),
        CheckConstraint(
            "(status = 'draft' AND started_at IS NULL AND stopped_at IS NULL) OR "
            "(status = 'running' AND started_at IS NOT NULL AND stopped_at IS NULL) "
            "OR (status = 'stopped' AND started_at IS NOT NULL AND stopped_at IS "
            "NOT NULL)",
            name="experiment_lifecycle",
        ),
        CheckConstraint(
            "(started_at IS NULL OR started_at >= created_at) AND (stopped_at IS "
            "NULL OR stopped_at >= started_at)",
            name="experiment_time_order",
        ),
        Index(
            "one_running_ranking_experiment",
            "status",
            unique=True,
            postgresql_where=text("status = 'running'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(Text)
    schema_version: Mapped[str] = mapped_column(Text, server_default="ranking-experiment-v1")
    assignment_version: Mapped[str] = mapped_column(Text, server_default="sha256-bucket-v1")
    salt: Mapped[str] = mapped_column(Text, default=lambda: token_hex(32))
    control_basis_points: Mapped[int] = mapped_column(Integer, server_default="5000")
    control_strategy: Mapped[str] = mapped_column(Text, server_default="interest-overlap")
    treatment_strategy: Mapped[str] = mapped_column(Text, server_default="expected-value")
    control_strategy_version: Mapped[str] = mapped_column(Text, server_default="baseline-v1")
    treatment_strategy_version: Mapped[str] = mapped_column(
        Text, server_default="expected-value-v1"
    )
    model_id: Mapped[str] = mapped_column(Text)
    model_version: Mapped[str] = mapped_column(Text, server_default="ctr-logistic-v1")
    feature_version: Mapped[str] = mapped_column(Text, server_default="ctr-features-v1")
    retrieval_mode: Mapped[str] = mapped_column(Text, server_default="exact")
    candidate_limit: Mapped[int] = mapped_column(Integer, server_default="500")
    search_limit: Mapped[int] = mapped_column(Integer, server_default="4000")
    hnsw_ef_search: Mapped[int | None] = mapped_column(Integer)
    vector_version: Mapped[str] = mapped_column(Text, server_default="binary-cosine-v1")
    vocabulary_version: Mapped[str] = mapped_column(Text, server_default="topics-v1")
    status: Mapped[str] = mapped_column(Text, server_default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
