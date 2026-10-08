import subprocess
import sys


def test_benchmark_cli_explains_dataset_and_report_controls_without_a_database() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "app.retrieval.benchmark_cli", "--help"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0
    assert "--dataset-id" in result.stdout
    assert "--output" in result.stdout
    assert "--repetitions" in result.stdout


def test_invalid_benchmark_configuration_is_rejected_before_database_access() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.retrieval.benchmark_cli",
            "--dataset-id",
            "00000000-0000-0000-0000-000000000001",
            "--output",
            "unused",
            "--queries",
            "0",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 2
    assert "Benchmark rejected" in result.stderr
    assert "Traceback" not in result.stderr
