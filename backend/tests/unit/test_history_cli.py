from pathlib import Path

import pytest

from app.history.cli import main


def test_history_cli_help_needs_no_database_settings(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as stopped:
        main(["--help"])
    assert stopped.value.code == 0
    assert "--impressions" in capsys.readouterr().out


def test_invalid_history_configuration_is_rejected_before_database_access(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        main(
            [
                "--dataset-id",
                "00000000-0000-0000-0000-000000000018",
                "--output",
                str(tmp_path / "invalid"),
                "--impressions",
                "0",
            ]
        )
        == 2
    )
    assert "History rejected" in capsys.readouterr().err
    assert not (tmp_path / "invalid").exists()
