"""Explicitly create/reset the dedicated adflow_benchmark PostgreSQL database."""

from __future__ import annotations

import argparse
import os
import sys

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

BENCHMARK_DATABASE = "adflow_benchmark"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.environ.get("ADFLOW_BENCHMARK_DATABASE_URL"),
        help="host-reachable psycopg URL for the benchmark database",
    )
    parser.add_argument(
        "--application-database-url",
        default=os.environ.get("ADFLOW_DATABASE_URL"),
        help="application database URL used to verify isolation",
    )
    parser.add_argument(
        "--template-database-url",
        help=(
            "optional host-reachable URL for adflow_benchmark_template; when set, clone its "
            "migrated and seeded baseline"
        ),
    )
    parser.add_argument(
        "--confirm-database",
        required=True,
        help="must be exactly adflow_benchmark to authorize resetting that database",
    )
    args = parser.parse_args()
    if args.confirm_database != BENCHMARK_DATABASE:
        parser.error("--confirm-database must be exactly adflow_benchmark")
    if not args.database_url or not args.application_database_url:
        parser.error("provide benchmark and application database URLs")

    target = make_url(args.database_url)
    application = make_url(args.application_database_url)
    if target.drivername != "postgresql+psycopg" or target.database != BENCHMARK_DATABASE:
        parser.error("benchmark URL must target the exact adflow_benchmark database")
    if application.database == BENCHMARK_DATABASE:
        parser.error("application URL cannot target adflow_benchmark")
    template = make_url(args.template_database_url) if args.template_database_url else None
    if template is not None and (
        template.drivername != "postgresql+psycopg"
        or template.database != "adflow_benchmark_template"
        or (template.host, template.port) != (target.host, target.port)
    ):
        parser.error(
            "template URL must target adflow_benchmark_template on the same PostgreSQL host"
        )
    admin_url = target.set(drivername="postgresql", database="postgres")
    try:
        with psycopg.connect(
            admin_url.render_as_string(hide_password=False), autocommit=True
        ) as connection:
            exists = connection.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (BENCHMARK_DATABASE,)
            ).fetchone()
            if template is not None:
                template_exists = connection.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s", (template.database,)
                ).fetchone()
                if not template_exists:
                    print(
                        "Benchmark template database is missing; target database was not reset.",
                        file=sys.stderr,
                    )
                    return 2
            if exists:
                connection.execute(
                    sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                        sql.Identifier(BENCHMARK_DATABASE)
                    )
                )
            create = sql.SQL("CREATE DATABASE {} OWNER {}").format(
                sql.Identifier(BENCHMARK_DATABASE), sql.Identifier(target.username or "")
            )
            if template is not None:
                create += sql.SQL(" TEMPLATE {}").format(sql.Identifier(template.database))
            connection.execute(create)
    except (OSError, psycopg.Error):
        print(
            "Benchmark database reset failed; verify the dedicated database and PostgreSQL access.",
            file=sys.stderr,
        )
        return 2
    if template is None:
        print(f"Created empty {BENCHMARK_DATABASE}; seed a dataset before running benchmarks.")
    else:
        print(f"Cloned {template.database} into {BENCHMARK_DATABASE}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
