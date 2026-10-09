from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import ConfigurationError, Settings, load_settings

APP_URL = "postgresql+psycopg://demo:private-password@localhost:5432/adflow"
TEST_URL = "postgresql+psycopg://demo:private-password@localhost:5432/adflow_test"


@pytest.mark.parametrize(
    "name,value",
    [
        ("RETRIEVAL_CANDIDATE_LIMIT", "0"),
        ("RETRIEVAL_CANDIDATE_LIMIT", "501"),
        ("RETRIEVAL_SEARCH_LIMIT", "0"),
        ("RETRIEVAL_SEARCH_LIMIT", "1000001"),
    ],
)
def test_retrieval_environment_limits_are_positive_and_bounded(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
) -> None:
    monkeypatch.setenv("ADFLOW_DATABASE_URL", APP_URL)
    monkeypatch.setenv("ADFLOW_TEST_DATABASE_URL", TEST_URL)
    monkeypatch.setenv(f"ADFLOW_{name}", value)
    with pytest.raises(ConfigurationError):
        load_settings(env_file=None)


def test_search_expansion_bound_cannot_be_smaller_than_candidate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ADFLOW_DATABASE_URL", APP_URL)
    monkeypatch.setenv("ADFLOW_TEST_DATABASE_URL", TEST_URL)
    monkeypatch.setenv("ADFLOW_RETRIEVAL_CANDIDATE_LIMIT", "500")
    monkeypatch.setenv("ADFLOW_RETRIEVAL_SEARCH_LIMIT", "499")
    with pytest.raises(ConfigurationError):
        load_settings(env_file=None)


def test_retrieval_limits_load_from_environment_without_changing_their_meaning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ADFLOW_DATABASE_URL", APP_URL)
    monkeypatch.setenv("ADFLOW_TEST_DATABASE_URL", TEST_URL)
    monkeypatch.setenv("ADFLOW_RETRIEVAL_CANDIDATE_LIMIT", "25")
    monkeypatch.setenv("ADFLOW_RETRIEVAL_SEARCH_LIMIT", "250")
    settings = load_settings(env_file=None)
    assert settings.retrieval_candidate_limit == 25
    assert settings.retrieval_search_limit == 250


def test_empty_redis_environment_disables_the_optional_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ADFLOW_DATABASE_URL", APP_URL)
    monkeypatch.setenv("ADFLOW_TEST_DATABASE_URL", TEST_URL)
    monkeypatch.setenv("ADFLOW_REDIS_URL", "")

    settings = load_settings(env_file=None)

    assert settings.redis_url is None


def test_disabled_redis_environment_sentinel_disables_the_optional_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ADFLOW_DATABASE_URL", APP_URL)
    monkeypatch.setenv("ADFLOW_TEST_DATABASE_URL", TEST_URL)
    monkeypatch.setenv("ADFLOW_REDIS_URL", "disabled")

    settings = load_settings(env_file=None)

    assert settings.redis_url is None


def test_missing_database_settings_are_reported_without_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ADFLOW_DATABASE_URL", raising=False)
    monkeypatch.delenv("ADFLOW_TEST_DATABASE_URL", raising=False)
    with pytest.raises(ConfigurationError) as error:
        load_settings(env_file=None)
    assert "database_url" in str(error.value)
    assert "test_database_url" in str(error.value)


@pytest.mark.parametrize(
    "test_url",
    [APP_URL, APP_URL.replace("localhost", "127.0.0.1"), APP_URL.replace("adflow", "%61dflow")],
)
def test_database_names_must_be_distinct_even_with_aliases(test_url: str) -> None:
    with pytest.raises(ValueError, match="distinct database names"):
        Settings(database_url=APP_URL, test_database_url=test_url)


@pytest.mark.parametrize(
    "url",
    [
        "not-a-url-private-password",
        "sqlite:///private-password",
        "postgresql+asyncpg://demo:private-password@localhost/adflow",
        "postgresql+psycopg://demo:private-password@localhost",
        APP_URL + "?connect_timeout=0",
        APP_URL.replace(":5432", ":invalid"),
    ],
)
def test_invalid_database_diagnostics_hide_credentials(url: str) -> None:
    with pytest.raises(ValidationError) as error:
        Settings(database_url=url, test_database_url=TEST_URL)
    assert "private-password" not in str(error.value)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("LOG_LEVEL", "private-password"),
        ("DB_CONNECT_TIMEOUT_SECONDS", "0"),
        ("DB_CONNECT_TIMEOUT_SECONDS", "31"),
        ("DB_POOL_TIMEOUT_SECONDS", "0"),
        ("DB_STATEMENT_TIMEOUT_SECONDS", "0"),
        ("DB_STATEMENT_TIMEOUT_SECONDS", "31"),
        ("DB_LOCK_TIMEOUT_SECONDS", "0"),
        ("DB_LOCK_TIMEOUT_SECONDS", "31"),
        ("DB_POOL_SIZE", "21"),
        ("DB_MAX_OVERFLOW", "-1"),
    ],
)
def test_invalid_environment_settings_have_safe_errors(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv("ADFLOW_DATABASE_URL", APP_URL)
    monkeypatch.setenv("ADFLOW_TEST_DATABASE_URL", TEST_URL)
    monkeypatch.setenv(f"ADFLOW_{name}", value)
    with pytest.raises(ConfigurationError) as error:
        load_settings(env_file=None)
    assert name.lower() in str(error.value)
    assert "private-password" not in str(error.value)


def test_environment_overrides_dotenv_and_settings_repr_hides_credentials(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"ADFLOW_DATABASE_URL={APP_URL}\nADFLOW_TEST_DATABASE_URL={TEST_URL}\n"
        "ADFLOW_LOG_LEVEL=ERROR\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("ADFLOW_DATABASE_URL", raising=False)
    monkeypatch.delenv("ADFLOW_TEST_DATABASE_URL", raising=False)
    monkeypatch.setenv("ADFLOW_LOG_LEVEL", "DEBUG")
    settings = load_settings(env_file=env_file)
    assert settings.log_level == "DEBUG"
    assert settings.database_url.get_secret_value() == APP_URL
    assert settings.test_database_url.get_secret_value() == TEST_URL
    assert "private-password" not in repr(settings)
