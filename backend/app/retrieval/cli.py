"""Explicit offline snapshot build/load; no application startup or request-path work."""

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from uuid import UUID

import faiss
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import ConfigurationError, load_settings
from app.db.catalog import read_catalog
from app.db.session import Database
from app.retrieval.snapshots import ActiveSnapshot, IndexHit, build_snapshot
from app.retrieval.vectors import user_vector


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build/load immutable exact CPU FAISS snapshots")
    commands = parser.add_subparsers(dest="action", required=True)
    build = commands.add_parser(
        "build", help="Export one dataset and prepare a new snapshot version"
    )
    build.add_argument("--dataset-id", type=UUID, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--database", choices=["application", "test"], default="application")
    load = commands.add_parser("load", help="Validate/load a version into this command's process")
    load.add_argument("directory", type=Path)
    load.add_argument("--expected-catalog-version")
    load.add_argument("--dataset-id", type=UUID)
    load.add_argument("--interests", nargs="*")
    load.add_argument("--limit", type=int, default=500)
    for command in (build, load):
        command.add_argument("--threads", type=int, default=1)
    args = parser.parse_args(argv)
    database: Database | None = None
    try:
        if not 1 <= args.threads <= 64:
            raise ValueError("threads must be between 1 and 64")
        faiss.omp_set_num_threads(args.threads)
        hits: tuple[IndexHit, ...] = ()
        if args.action == "build":
            database = Database(load_settings(), use_test_database=args.database == "test")
            with database.session() as session:
                catalog = read_catalog(session, args.dataset_id)
            snapshot = build_snapshot(
                args.output,
                catalog.entries,
                dataset_id=catalog.dataset_id,
                catalog_version=catalog.version,
            )
        else:
            snapshot = ActiveSnapshot().reload(
                args.directory,
                expected_catalog_version=args.expected_catalog_version,
                expected_dataset_id=args.dataset_id,
            )
            if args.interests is not None:
                query = user_vector(args.interests)
                if query is None:
                    raise ValueError(
                        "empty interests require nonpersonalized retrieval, not a vector query"
                    )
                hits = snapshot.search(query, limit=args.limit)
        print(
            json.dumps(
                {
                    "status": args.action,
                    "manifest": snapshot.manifest.model_dump(mode="json"),
                    "hits": [asdict(hit) for hit in hits],
                },
                sort_keys=True,
            )
        )
        return 0
    except (ConfigurationError, ValueError) as error:
        print(f"Snapshot command rejected: {error}", file=sys.stderr)
        return 2
    except SQLAlchemyError:
        print("Snapshot build failed; check database availability and migrations.", file=sys.stderr)
        return 3
    except (OSError, RuntimeError):
        print(
            "Snapshot preparation failed; check artifact storage and native runtime.",
            file=sys.stderr,
        )
        return 3
    finally:
        if database is not None:
            database.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
