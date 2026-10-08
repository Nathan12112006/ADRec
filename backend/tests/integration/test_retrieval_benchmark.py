import gzip
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.session import Database
from app.retrieval.benchmark import BenchmarkConfig, run_comparison
from app.seeding import SeedConfig, seed_database


def test_comparison_saves_frozen_inputs_raw_samples_and_separate_fallback(
    database: Database, tmp_path: Path
) -> None:
    seed = SeedConfig(seed=uuid4().int % 2**62, users=4, advertisers=2, ads=12)
    seed_database(database, seed, append=True)
    output = tmp_path / "comparison"
    report = run_comparison(
        database,
        seed.dataset_id,
        output,
        BenchmarkConfig(
            query_count=3, empty_query_count=1, warmup_queries=1, repetitions=1, candidate_limit=2
        ),
    )
    saved = json.loads((output / "report.json").read_text())
    assert saved == report
    assert report["provenance"]["counts"]["ads"] == 12
    assert report["provenance"]["eligible_ads"] == 12
    assert len(report["samples"]) == 12  # 3 paths * (3 personalized + 1 empty query)
    assert {row["population"] for row in report["samples"]} == {"personalized", "empty_interests"}
    assert {row["path"] for row in report["samples"]} == {"full_ad", "flat", "hnsw"}
    assert all(row["candidate_count"] <= 2 for row in report["samples"] if row["path"] != "full_ad")
    assert report["promotion"]["applied"] is False
    assert report["summary"]["personalized"]["flat"]["count"] == 3
    assert (output / "queries.json").exists()
    assert (output / "catalog.jsonl.gz").exists()


def test_cli_runs_a_real_small_comparison_and_refuses_to_overwrite(
    tmp_path: Path, database: Database
) -> None:
    seed = SeedConfig(seed=uuid4().int % 2**62, users=2, advertisers=1, ads=4)
    seed_database(database, seed, append=True)
    args = [
        sys.executable,
        "-m",
        "app.retrieval.benchmark_cli",
        "--dataset-id",
        str(seed.dataset_id),
        "--output",
        str(tmp_path / "run"),
        "--queries",
        "2",
        "--warmup-queries",
        "0",
        "--empty-queries",
        "1",
        "--limit",
        "2",
        "--repetitions",
        "1",
    ]
    result = subprocess.run(args, capture_output=True, text=True, timeout=40)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["counts"]["ads"] == 4
    before = (tmp_path / "run" / "report.json").read_bytes()
    repeat = subprocess.run(args, capture_output=True, text=True, timeout=15)
    assert repeat.returncode == 3
    assert (tmp_path / "run" / "report.json").read_bytes() == before


def test_empty_inventory_keeps_recall_unavailable_and_never_promotes(
    database: Database, tmp_path: Path
) -> None:
    seed = SeedConfig(seed=uuid4().int % 2**62, users=1, advertisers=0, ads=0)
    seed_database(database, seed, append=True)
    report = run_comparison(
        database,
        seed.dataset_id,
        tmp_path / "empty",
        BenchmarkConfig(query_count=1, warmup_queries=0, empty_query_count=0, repetitions=3),
    )
    assert all(row["candidate_count"] == 0 for row in report["samples"])
    assert all(
        row["recall"]["tie_aware_recall"] is None for row in report["samples"] if row["recall"]
    )
    assert report["promotion"]["eligible"] is False


def test_failed_comparison_is_saved_as_failed_without_a_complete_report(
    database: Database, tmp_path: Path
) -> None:
    output = tmp_path / "failed"
    with pytest.raises(ValueError, match="unknown benchmark dataset"):
        run_comparison(database, uuid4(), output, BenchmarkConfig())
    status = json.loads((output / "status.json").read_text())
    assert status["status"] == "failed"
    assert status["error_type"] == "ValueError"
    assert not (output / "report.json").exists()


def test_profiles_remain_frozen_when_an_editor_commits_during_preparation(
    database: Database, tmp_path: Path
) -> None:
    seed = SeedConfig(seed=uuid4().int % 2**62, users=2, advertisers=1, ads=4)
    seed_database(database, seed, append=True)
    with ThreadPoolExecutor(max_workers=1) as workers:
        with database.session() as editor:
            editor_pid = editor.scalar(text("SELECT pg_backend_pid()"))
            editor.execute(text("LOCK TABLE users IN ACCESS EXCLUSIVE MODE"))
            pending = workers.submit(
                run_comparison,
                database,
                seed.dataset_id,
                tmp_path / "frozen",
                BenchmarkConfig(
                    query_count=2,
                    empty_query_count=0,
                    warmup_queries=0,
                    repetitions=1,
                    candidate_limit=2,
                ),
            )
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                with database.session() as observer:
                    blocked = observer.scalar(
                        text(
                            "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                            "WHERE :editor = ANY(pg_blocking_pids(pid)))"
                        ),
                        {"editor": editor_pid},
                    )
                if blocked:
                    break
                assert not pending.done()
                time.sleep(0.01)
            else:
                pytest.fail("benchmark did not reach the controlled profile-read wait")
            editor.execute(
                text("UPDATE users SET interests='{}' WHERE dataset_id=:dataset"),
                {"dataset": seed.dataset_id},
            )
            editor.commit()
        report = pending.result(timeout=40)
    assert report["provenance"]["actual_personalized_queries"] == 2
    queries = json.loads((tmp_path / "frozen" / "queries.json").read_text())
    assert all(user["interests"] for user in queries["personalized"])
    with gzip.open(tmp_path / "frozen" / "catalog.jsonl.gz", "rt") as source:
        assert len(source.readlines()) == 4
