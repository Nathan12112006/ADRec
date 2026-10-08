"""Explicit offline generation; never seeds, migrates, trains, or calls serving APIs."""

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import ConfigurationError, load_settings
from app.db.session import Database
from app.history.artifacts import HistoryConfig, write_history
from app.history.outcomes import OutcomeConfig
from app.history.source import export_source


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate separate synthetic historical exposure artifacts"
    )
    parser.add_argument("--dataset-id", type=UUID, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--database", choices=["test", "application"], default="test")
    parser.add_argument("--impressions", type=int, default=10000)
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=18)
    parser.add_argument("--start", type=datetime.fromisoformat, default="2026-01-01T00:00:00+00:00")
    parser.add_argument("--interval-seconds", type=int, default=1)
    parser.add_argument("--max-click-delay-seconds", type=int, default=300)
    parser.add_argument(
        "--outcome-config", type=Path, help="JSON OutcomeConfig; all parameters saved in manifest"
    )
    args = parser.parse_args(argv)
    database: Database | None = None
    try:
        outcome = (
            OutcomeConfig.model_validate_json(args.outcome_config.read_text(encoding="utf-8"))
            if args.outcome_config
            else OutcomeConfig()
        )
        config = HistoryConfig(
            seed=args.seed,
            impressions=args.impressions,
            batch_size=args.batch_size,
            start=args.start,
            interval_seconds=args.interval_seconds,
            max_click_delay_seconds=args.max_click_delay_seconds,
            outcome=outcome,
        )
        if args.output.exists():
            raise ValueError("output already exists; select a new directory")
        database = Database(load_settings(), use_test_database=args.database == "test")
        source = export_source(database, args.dataset_id)
        manifest = write_history(source, args.output, config)
        print(
            json.dumps(
                {
                    "history_id": manifest["history_id"],
                    "counts": manifest["counts"],
                    "manifest_path": str(args.output.resolve() / "manifest.json"),
                    "observed_ctr": manifest["observed_ctr"],
                    "sanity_rates": manifest["sanity_rates"],
                },
                sort_keys=True,
            )
        )
        return 0
    except (ValueError, ConfigurationError):
        print(
            "History rejected; check source dataset, configuration and unused output directory.",
            file=sys.stderr,
        )
        return 2
    except SQLAlchemyError:
        print(
            "History failed; check database availability and migrations. No live records written.",
            file=sys.stderr,
        )
        return 3
    except OSError:
        print(
            "History failed; check artifact filesystem. No complete history claimed.",
            file=sys.stderr,
        )
        return 3
    finally:
        if database is not None:
            database.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
