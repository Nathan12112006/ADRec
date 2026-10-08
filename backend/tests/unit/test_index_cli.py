import json
import subprocess
import sys
from pathlib import Path
from uuid import UUID

from app.retrieval.snapshots import IndexEntry, build_snapshot
from app.retrieval.vectors import ad_vector


def test_index_cli_describes_offline_build_and_load_without_database_configuration() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "app.retrieval.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0
    assert "build" in result.stdout
    assert "load" in result.stdout


def test_cli_load_searches_real_artifacts_without_database_settings(tmp_path: Path) -> None:
    path = tmp_path / "snapshot"
    built = build_snapshot(
        path,
        [IndexEntry(ad_id=42, vector=ad_vector([], category="technology"))],
        dataset_id=UUID(int=1),
        catalog_version="catalog-1",
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.retrieval.cli",
            "load",
            str(path),
            "--interests",
            "technology",
            "--limit",
            "1",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["hits"] == [{"ad_id": 42, "similarity": 1}]
    assert payload["manifest"]["snapshot_version"] == str(built.manifest.snapshot_version)
    rejected = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.retrieval.cli",
            "load",
            str(path),
            "--expected-catalog-version",
            "wrong-version",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert rejected.returncode == 2
    assert "stale catalog" in rejected.stderr


def test_cli_missing_artifacts_and_invalid_threads_have_safe_failures(tmp_path: Path) -> None:
    for args in [
        ["load", str(tmp_path / "missing")],
        ["load", str(tmp_path / "missing"), "--threads", "0"],
    ]:
        result = subprocess.run(
            [sys.executable, "-m", "app.retrieval.cli", *args],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 2
        assert "Traceback" not in result.stderr
