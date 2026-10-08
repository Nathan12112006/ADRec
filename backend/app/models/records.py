"""Typed PostgreSQL records; historical exposures live outside these tables."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Numeric,
    Text,
    UniqueConstraint,
    func,
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
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("datasets.id"))
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    ad_id: Mapped[int] = mapped_column(BigInteger, index=True)
    bid: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    selected_ad: Mapped[dict[str, Any]] = mapped_column(JSONB)
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
    )

    request_key: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    recommendation_id: Mapped[UUID | None] = mapped_column()
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
