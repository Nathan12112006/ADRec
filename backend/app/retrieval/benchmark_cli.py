"""Explicit offline benchmark; seeding and migrations are separate commands."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import ConfigurationError, load_settings
from app.core.errors import WorkflowError
from app.db.session import Database
from app.retrieval.benchmark import BenchmarkConfig, run_comparison
from app.retrieval.snapshots import HnswSettings


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare frozen full-ad/Flat/HNSW components; not HTTP load"
    )
    parser.add_argument("--dataset-id", type=UUID, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--database", choices=["test", "application"], default="test")
    parser.add_argument("--queries", type=int, default=100)
    parser.add_argument("--empty-queries", type=int, default=5)
    parser.add_argument("--query-seed", type=int, default=1601)
    parser.add_argument("--warmup-queries", type=int, default=10)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--boundary-tolerance", type=float, default=1e-6)
    parser.add_argument("--hnsw-m", type=int, default=32)
    parser.add_argument("--ef-construction", type=int, default=200)
    parser.add_argument("--ef-search", type=int, default=128)
    args = parser.parse_args(argv)
    database: Database | None = None
    try:
        config = BenchmarkConfig(
            candidate_limit=args.limit,
            query_count=args.queries,
            empty_query_count=args.empty_queries,
            query_seed=args.query_seed,
            warmup_queries=args.warmup_queries,
            repetitions=args.repetitions,
            threads=args.threads,
            boundary_tolerance=args.boundary_tolerance,
            hnsw=HnswSettings(
                m=args.hnsw_m, ef_construction=args.ef_construction, ef_search=args.ef_search
            ),
        )
        database = Database(load_settings(), use_test_database=args.database == "test")
        report = run_comparison(database, args.dataset_id, args.output, config)
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "run_id": report["run_id"],
                    "report_path": str(args.output.resolve() / "report.json"),
                    "counts": report["provenance"]["counts"],
                    "promotion": report["promotion"],
                    "summary": report["summary"],
                },
                sort_keys=True,
            )
        )
        return 0
    except (ValueError, ConfigurationError):
        print(
            "Benchmark rejected; check dataset identity, query controls and configuration.",
            file=sys.stderr,
        )
        return 2
    except (SQLAlchemyError, WorkflowError):
        print(
            "Benchmark failed; check database availability and migrations. "
            "No complete result claimed.",
            file=sys.stderr,
        )
        return 3
    except (OSError, RuntimeError):
        print(
            "Benchmark failed; check output directory and native runtime. "
            "No complete result claimed.",
            file=sys.stderr,
        )
        return 3
    finally:
        if database is not None:
            database.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
