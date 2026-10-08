import subprocess
import sys


def test_cli_explains_seed_controls_without_database_configuration() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "app.seeding.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "--users" in result.stdout
    assert "--append" in result.stdout


def test_cli_rejects_ads_without_advertisers_before_opening_database() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "app.seeding.cli", "--advertisers", "0"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert "ads require at least one advertiser" in result.stderr
