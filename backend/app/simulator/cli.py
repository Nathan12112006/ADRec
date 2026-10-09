"""Run reproducible live synthetic traffic against the HTTP API."""

import argparse
import json
import sys
from collections.abc import Sequence

from sqlalchemy import exists, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import ConfigurationError, load_settings
from app.db.session import Database
from app.models.records import Ad, Advertiser, User
from app.simulator.traffic import UserProfile, simulate


def _profiles(database: Database, scenario: str) -> tuple[UserProfile, ...]:
    eligible_ads = exists(
        select(Ad.id)
        .join(Advertiser, Ad.advertiser_id == Advertiser.id)
        .where(
            Ad.dataset_id == User.dataset_id,
            Ad.active.is_(True),
            Advertiser.active.is_(True),
        )
    )
    query = select(User).order_by(User.id)
    if scenario == "no-interest":
        query = query.where(User.interests == [])
    elif scenario == "no-ad":
        query = query.where(~eligible_ads)
    with database.session() as session:
        return tuple(
            UserProfile(
                id=row.id,
                interests=tuple(row.interests),
                category_preferences=tuple(row.category_preferences),
                device=row.device,
            )
            for row in session.scalars(query)
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate reproducible AdFlow demo traffic")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--duration-seconds", type=float, default=120)
    parser.add_argument("--rate-per-second", type=float, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--scenario", choices=("normal", "duplicates", "no-interest", "no-ad"), default="normal"
    )
    parser.add_argument("--max-retries", type=int, default=3)
    args = parser.parse_args(argv)
    if args.duration_seconds <= 0 or args.rate_per_second <= 0 or not 0 <= args.max_retries <= 8:
        parser.error("duration/rate must be positive and max-retries must be between 0 and 8")
    database: Database | None = None
    try:
        database = Database(load_settings())
        profiles = _profiles(database, args.scenario)
        if not profiles:
            print(
                f"No synthetic users match the {args.scenario!r} scenario; no traffic sent.",
                file=sys.stderr,
            )
            return 2
        summary = simulate(
            base_url=args.base_url,
            users=profiles,
            duration_seconds=args.duration_seconds,
            rate_per_second=args.rate_per_second,
            seed=args.seed,
            scenario=args.scenario,
            max_retries=args.max_retries,
        )
        print(json.dumps(summary, sort_keys=True))
        return 0
    except (ConfigurationError, SQLAlchemyError, OSError, ValueError) as error:
        print(f"Traffic simulation failed: {error}", file=sys.stderr)
        return 3
    finally:
        if database is not None:
            database.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
