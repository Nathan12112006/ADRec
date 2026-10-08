"""Explicit seed command; migrations and replacement are separate operations."""

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import ConfigurationError, load_settings
from app.db.session import Database
from app.seeding import SeedConfig, SeedConflict, seed_database


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a reproducible synthetic entity dataset")
    parser.add_argument("--users", type=int, default=100)
    parser.add_argument("--advertisers", type=int, default=20)
    parser.add_argument("--ads", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--database", choices=["application", "test"], default="application")
    parser.add_argument(
        "--append",
        action="store_true",
        help="Allow an additional dataset; never replace existing data",
    )
    args = parser.parse_args(argv)
    try:
        config = SeedConfig(
            seed=args.seed, users=args.users, advertisers=args.advertisers, ads=args.ads
        )
        if not 1 <= args.batch_size <= 10000:
            raise ValueError("batch_size must be between 1 and 10000")
    except (ValidationError, ValueError) as error:
        print(f"Invalid seed configuration: {error}", file=sys.stderr)
        return 2
    database: Database | None = None
    try:
        settings = load_settings()
        database = Database(settings, use_test_database=args.database == "test")
        result = seed_database(database, config, append=args.append, batch_size=args.batch_size)
        print(
            json.dumps(
                {
                    **asdict(result),
                    "dataset_id": str(result.dataset_id),
                    "manifest": config.manifest(),
                },
                sort_keys=True,
            )
        )
        return 0
    except (ConfigurationError, SeedConflict) as error:
        print(str(error), file=sys.stderr)
        return 2
    except SQLAlchemyError:
        print(
            "Seed failed; transaction rolled back. Check database availability, migrations "
            "and entity ID conflicts.",
            file=sys.stderr,
        )
        return 3
    finally:
        if database is not None:
            database.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
