"""Run reproducible single-worker Locust matrices against the isolated benchmark API."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

try:
    import psutil
except ImportError:  # Locust supplies it in the supported Python 3.11+ dev environment.
    psutil = None


def _memory_resources() -> tuple[int | None, int | None]:
    if psutil is not None:
        memory = psutil.virtual_memory()
        return memory.total, memory.available
    if os.name == "nt":

        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_ulong),
                ("memory_load", ctypes.c_ulong),
                ("total_physical", ctypes.c_ulonglong),
                ("available_physical", ctypes.c_ulonglong),
                ("total_page_file", ctypes.c_ulonglong),
                ("available_page_file", ctypes.c_ulonglong),
                ("total_virtual", ctypes.c_ulonglong),
                ("available_virtual", ctypes.c_ulonglong),
                ("available_extended_virtual", ctypes.c_ulonglong),
            ]

        memory_status = MemoryStatus()
        memory_status.length = ctypes.sizeof(memory_status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory_status)):
            return memory_status.total_physical, memory_status.available_physical
    elif hasattr(os, "sysconf"):
        try:
            page_size = os.sysconf("SC_PAGE_SIZE")
            total = os.sysconf("SC_PHYS_PAGES") * page_size
            available = os.sysconf("SC_AVPHYS_PAGES") * page_size
            return total, available
        except (OSError, ValueError):
            pass
    return None, None


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
WORKLOADS = BACKEND_ROOT / "loadtests"
LOCUST_FILE_BY_WORKLOAD = {
    "recommendation_only": WORKLOADS / "benchmark_recommendation_only.py",
    "lifecycle": WORKLOADS / "benchmark_lifecycle.py",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _database_name(url: str) -> str:
    return urlparse(url).path.removeprefix("/")


def _container_details(name: str, expected_database: str) -> dict[str, object]:
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("Docker CLI is required to verify the isolated API container")
    inspected = subprocess.run(
        [docker, "inspect", name], check=True, capture_output=True, text=True
    )
    container = json.loads(inspected.stdout)[0]
    config = container["Config"]
    if container.get("State", {}).get("Status") != "running":
        raise RuntimeError("benchmark API container is not running")
    environment = dict(item.split("=", 1) for item in config.get("Env", []) if "=" in item)
    database_url = environment.get("ADFLOW_DATABASE_URL", "")
    if _database_name(database_url) != expected_database:
        raise RuntimeError("API container is not configured for the declared benchmark database")
    command = [
        *(config.get("Entrypoint") or []),
        *(config.get("Cmd") or []),
    ]
    command_text = " ".join(str(part) for part in command)
    if "uvicorn" not in command_text or "--workers 1" not in command_text:
        raise RuntimeError("benchmark API container must run exactly one explicit Uvicorn worker")

    def artifact_identity(path: str) -> dict[str, object] | None:
        if not path:
            return None
        manifest = subprocess.run(
            [docker, "exec", name, "cat", f"{path.rstrip('/')}/manifest.json"],
            capture_output=True,
            text=True,
            check=False,
        )
        if manifest.returncode != 0:
            return {"path": path, "manifest_available": False}
        try:
            value = json.loads(manifest.stdout)
        except json.JSONDecodeError:
            return {"path": path, "manifest_available": False}
        identity_fields = (
            "artifact_id",
            "dataset_id",
            "catalog_version",
            "count",
            "index_type",
            "hnsw",
            "model_id",
            "model_version",
            "feature_version",
            "snapshot_id",
            "snapshot_version",
            "sha256",
            "index_sha256",
            "mapping_sha256",
        )
        return {
            "path": path,
            "manifest_available": True,
            **{field: value[field] for field in identity_fields if field in value},
        }

    return {
        "container_name": name,
        "image": config.get("Image"),
        "image_id": container.get("Image"),
        "command": command,
        "state": container.get("State", {}).get("Status"),
        "restart_count": container.get("RestartCount"),
        "memory_limit_bytes": container.get("HostConfig", {}).get("Memory"),
        "cpu_quota": container.get("HostConfig", {}).get("CpuQuota"),
        "cpu_period": container.get("HostConfig", {}).get("CpuPeriod"),
        "mounts": [
            {
                "type": item.get("Type"),
                "source": item.get("Source"),
                "destination": item.get("Destination"),
            }
            for item in container.get("Mounts", [])
        ],
        "benchmark_database": expected_database,
        "redis_configured": bool(environment.get("ADFLOW_REDIS_URL")),
        "retrieval_index_path_set": bool(environment.get("ADFLOW_RETRIEVAL_INDEX_PATH")),
        "ctr_model_path_set": bool(environment.get("ADFLOW_CTR_MODEL_PATH")),
        "retrieval_artifact": artifact_identity(environment.get("ADFLOW_RETRIEVAL_INDEX_PATH", "")),
        "ctr_artifact": artifact_identity(environment.get("ADFLOW_CTR_MODEL_PATH", "")),
        "ranking_strategy": environment.get("ADFLOW_RANKING_STRATEGY"),
        "retrieval_candidate_limit": environment.get("ADFLOW_RETRIEVAL_CANDIDATE_LIMIT"),
        "retrieval_search_limit": environment.get("ADFLOW_RETRIEVAL_SEARCH_LIMIT"),
    }


def _host_resources() -> dict[str, object]:
    docker_version: str | None = None
    docker = shutil.which("docker")
    if docker is not None:
        result = subprocess.run(
            [docker, "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            text=True,
            check=False,
        )
        docker_version = result.stdout.strip() if result.returncode == 0 else None
    memory_total, memory_available = _memory_resources()
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "logical_cpus": os.cpu_count(),
        "physical_cpus": psutil.cpu_count(logical=False) if psutil is not None else None,
        "memory_total_bytes": memory_total,
        "memory_available_bytes_at_start": memory_available,
        "docker_server_version": docker_version,
        "load_generator_placement": "host process colocated with Docker engine/API",
    }


def _container_usage(name: str) -> dict[str, str] | None:
    docker = shutil.which("docker")
    if docker is None:
        return None
    result = subprocess.run(
        [docker, "stats", "--no-stream", "--format", "{{json .}}", name],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        value = json.loads(result.stdout.strip().splitlines()[-1])
    except json.JSONDecodeError:
        return None
    return {
        key: str(value[key])
        for key in ("CPUPerc", "MemUsage", "MemPerc", "NetIO", "BlockIO")
        if key in value
    }


def _preflight(host: str) -> dict[str, object]:
    with urlopen(host.rstrip("/") + "/health/ready", timeout=5) as response:
        readiness = json.load(response)
    with urlopen(host.rstrip("/") + "/api/v1/analytics/overview", timeout=5) as response:
        overview = json.load(response)
    if readiness.get("status") != "ready":
        raise RuntimeError("benchmark API readiness check did not return ready")
    dataset_id = overview.get("dataset_id")
    if not dataset_id:
        raise RuntimeError("benchmark database must have a prepared dataset before running")
    return {
        "dataset_id": dataset_id,
        "user_count": overview.get("users"),
        "ad_count": overview.get("ads"),
        "readiness": readiness,
        "cache_enabled": readiness.get("dependencies", {}).get("redis") == "ready",
        "capabilities": readiness.get("capabilities", {}),
    }


def _verify_profile_database(database_url: str, api_dataset_id: str) -> None:
    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
    )
    try:
        with engine.connect() as connection:
            dataset_id = connection.execute(
                text("SELECT id::text FROM datasets ORDER BY created_at DESC, id DESC LIMIT 1")
            ).scalar_one_or_none()
    finally:
        engine.dispose()
    if dataset_id != api_dataset_id:
        raise RuntimeError("profile database and benchmark API do not expose the same dataset")


def _database_counts(database_url: str) -> dict[str, int]:
    tables = (
        "datasets",
        "users",
        "advertisers",
        "ads",
        "recommendations",
        "request_outcomes",
        "events",
    )
    engine = create_engine(database_url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection:
            return {
                table: int(connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one())
                for table in tables
            }
    finally:
        engine.dispose()


def _parse_summary(log_path: Path) -> dict[str, object] | None:
    summary = None
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if '"type": "adflow_locust_summary"' in line:
            try:
                summary = json.loads(line)
            except json.JSONDecodeError:
                continue
    return summary


def _run_command(
    args: argparse.Namespace,
    run_dir: Path,
    user_count: int,
    repetition: int,
    *,
    dataset_id: str,
    cache_enabled: bool,
    locust_image: str | None,
    loadgen_database_url: str | None,
) -> list[str]:
    run_id = str(uuid4())
    csv_prefix = run_dir / "locust"

    def loadgen_path(path: Path) -> str:
        if locust_image:
            return f"/workspace/{path.relative_to(REPOSITORY_ROOT).as_posix()}"
        return str(path)

    locust_command = [
        "-f",
        loadgen_path(LOCUST_FILE_BY_WORKLOAD[args.workload]),
        "--headless",
        "--only-summary",
        "--csv",
        loadgen_path(csv_prefix),
        "--html",
        loadgen_path(run_dir / "locust.html"),
        "--stop-timeout",
        str(args.drain_seconds),
        "--host",
        (args.loadgen_host or args.host).rstrip("/"),
        "--users",
        str(user_count),
        "--spawn-rate",
        str(args.spawn_rate),
        "--adflow-seed",
        str(args.seed + repetition - 1),
        "--adflow-run-id",
        run_id,
        "--adflow-user-selection",
        args.user_selection,
        "--adflow-hot-user-count",
        str(args.hot_user_count),
        "--adflow-max-retries",
        str(args.max_retries),
        "--adflow-request-timeout-seconds",
        str(args.request_timeout_seconds),
        "--adflow-warmup-seconds",
        str(args.warmup_seconds),
        "--adflow-measurement-seconds",
        str(args.measurement_seconds),
        "--adflow-drain-seconds",
        str(args.drain_seconds),
        "--adflow-run-directory",
        loadgen_path(run_dir),
        "--adflow-cache-state",
        args.cache_state,
        "--adflow-cache-container",
        args.cache_container,
        "--adflow-dataset-id",
        dataset_id,
    ]
    command = locust_command
    if cache_enabled:
        command.append("--adflow-cache-enabled")
    if locust_image:
        docker = shutil.which("docker")
        if docker is None:
            raise RuntimeError("Docker CLI is required for the Dockerized Locust generator")
        repo_mount = f"{REPOSITORY_ROOT}:/workspace"
        command = [
            docker,
            "run",
            "--rm",
            "--network",
            f"container:{args.api_container}",
            "--volume",
            repo_mount,
            "--workdir",
            "/workspace/backend",
            "--env",
            f"ADFLOW_DATABASE_URL={loadgen_database_url}",
            "--env",
            "ADFLOW_TEST_DATABASE_URL="
            + make_url(loadgen_database_url or args.profile_database_url)
            .set(database="adflow_test")
            .render_as_string(hide_password=False),
            "--env",
            "ADFLOW_REDIS_URL=redis://redis:6379/0",
            locust_image,
            *locust_command,
        ]

    persisted_command = [
        "ADFLOW_DATABASE_URL=<redacted>" if value.startswith("ADFLOW_DATABASE_URL=") else value
        for value in command
    ]
    persisted_command = [
        "ADFLOW_TEST_DATABASE_URL=<redacted>"
        if value.startswith("ADFLOW_TEST_DATABASE_URL=")
        else value
        for value in persisted_command
    ]
    _json(
        run_dir / "configuration.json",
        {
            "command": persisted_command,
            "workload": args.workload,
            "users": user_count,
            "spawn_rate_users_per_second": args.spawn_rate,
            "repetition": repetition,
            "seed": args.seed + repetition - 1,
            "user_selection": args.user_selection,
            "hot_user_count": args.hot_user_count if args.user_selection == "hot" else 0,
            "warmup_seconds_after_ramp": args.warmup_seconds,
            "measurement_seconds": args.measurement_seconds,
            "drain_timeout_seconds": args.drain_seconds,
            "request_timeout_seconds": args.request_timeout_seconds,
            "cache_state": args.cache_state,
            "run_id": run_id,
        },
    )
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="benchmark API root URL")
    parser.add_argument("--api-container", default="adflow-benchmark-api")
    parser.add_argument("--benchmark-database", default="adflow_benchmark")
    parser.add_argument("--profile-database-url", required=True)
    parser.add_argument(
        "--locust-image",
        help="run Locust in this prebuilt image; useful when the host Python is unsupported",
    )
    parser.add_argument(
        "--loadgen-database-url",
        help=(
            "database URL reachable from the Locust container, usually using the postgres "
            "service name"
        ),
    )
    parser.add_argument(
        "--loadgen-host", help="API URL reachable from the Locust container, such as localhost:8000"
    )
    parser.add_argument("--workload", choices=sorted(LOCUST_FILE_BY_WORKLOAD), required=True)
    parser.add_argument(
        "--users", type=int, nargs="+", choices=(10, 100, 500), default=(10, 100, 500)
    )
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--spawn-rate", type=float, default=10.0)
    parser.add_argument("--warmup-seconds", type=int, default=60)
    parser.add_argument("--measurement-seconds", type=int, default=180)
    parser.add_argument("--drain-seconds", type=int, default=30)
    parser.add_argument("--seed", type=int, default=20261009)
    parser.add_argument("--user-selection", choices=("uniform", "hot"), default="uniform")
    parser.add_argument("--hot-user-count", type=int, default=5)
    parser.add_argument("--max-retries", type=int, default=1)
    parser.add_argument("--request-timeout-seconds", type=float, default=5.0)
    parser.add_argument("--cache-state", choices=("cold", "warm"), default="warm")
    parser.add_argument("--cache-container", default="adflow-redis-1")
    parser.add_argument(
        "--output-root", type=Path, default=REPOSITORY_ROOT / "artifacts" / "benchmarks"
    )
    args = parser.parse_args()
    args.output_root = args.output_root.resolve()

    parsed_host = urlparse(args.host)
    if parsed_host.scheme not in {"http", "https"} or not parsed_host.netloc:
        parser.error("--host must be an HTTP or HTTPS URL")
    if parsed_host.username or parsed_host.password:
        parser.error("credentials are not allowed in --host; use a local benchmark URL")
    if args.benchmark_database != "adflow_benchmark":
        parser.error("--benchmark-database must be exactly adflow_benchmark")
    try:
        profile_database_url = make_url(args.profile_database_url)
    except (TypeError, ValueError):
        parser.error("--profile-database-url must be a valid SQLAlchemy database URL")
    if (
        profile_database_url.drivername != "postgresql+psycopg"
        or profile_database_url.database != args.benchmark_database
        or profile_database_url.query
    ):
        parser.error("--profile-database-url must be a query-free psycopg URL for adflow_benchmark")
    if args.repetitions < 1 or args.spawn_rate <= 0 or args.warmup_seconds < 0:
        parser.error("repetitions/spawn-rate/warm-up settings are invalid")
    if args.measurement_seconds < 1 or args.drain_seconds < 0 or args.hot_user_count < 1:
        parser.error("measurement/drain/hot-user settings are invalid")
    if args.max_retries < 0 or args.max_retries > 8 or args.request_timeout_seconds <= 0:
        parser.error("retry count or request timeout is invalid")
    if bool(args.locust_image) != bool(args.loadgen_database_url) or bool(
        args.locust_image
    ) != bool(args.loadgen_host):
        parser.error(
            "--locust-image, --loadgen-database-url, and --loadgen-host must be supplied together"
        )
    locustfile = LOCUST_FILE_BY_WORKLOAD[args.workload]
    if not locustfile.is_file():
        parser.error(f"missing workload file: {locustfile}")

    args.output_root.mkdir(parents=True, exist_ok=True)
    matrix_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid4()}"
    matrix_dir = args.output_root / matrix_id
    matrix_dir.mkdir(parents=True)
    try:
        container = _container_details(args.api_container, args.benchmark_database)
        api = _preflight(args.host)
        if args.user_selection == "hot" and args.hot_user_count > int(api["user_count"] or 0):
            raise RuntimeError("hot-user count exceeds the prepared benchmark dataset population")
        _verify_profile_database(args.profile_database_url, str(api["dataset_id"]))
    except (
        OSError,
        RuntimeError,
        SQLAlchemyError,
        URLError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as error:
        failure = {
            "matrix_id": matrix_id,
            "created_at": _utc_now(),
            "status": "preflight_failed",
            "failure_type": type(error).__name__,
            "configuration": {
                "host": args.host,
                "benchmark_database": args.benchmark_database,
                "workload": args.workload,
                "users": args.users,
                "repetitions": args.repetitions,
                "warmup_seconds_after_ramp": args.warmup_seconds,
                "measurement_seconds": args.measurement_seconds,
                "drain_timeout_seconds": args.drain_seconds,
                "cache_state": args.cache_state,
                "user_selection": args.user_selection,
                "locust_image": args.locust_image,
            },
        }
        _json(matrix_dir / "matrix.json", failure)
        _json(matrix_dir / "preflight_failure.json", failure)
        parser.error(f"benchmark preflight failed: {type(error).__name__}")

    version_command = (
        ["docker", "run", "--rm", args.locust_image, "--version"]
        if args.locust_image
        else [sys.executable, "-m", "locust", "--version"]
    )
    locust_version = subprocess.run(version_command, capture_output=True, text=True, check=False)
    if locust_version.returncode != 0:
        parser.error("Locust is not installed in the active Python environment")
    if "2.46.7" not in locust_version.stdout:
        parser.error("controlled runs require the pinned Locust 2.46.7 version")
    baseline = {
        "matrix_id": matrix_id,
        "created_at": _utc_now(),
        "git_revision": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        or None,
        "git_worktree_dirty": bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
        ),
        "benchmark_source_sha256": {
            str(path.relative_to(REPOSITORY_ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(
                [*WORKLOADS.glob("*.py"), Path(__file__), REPOSITORY_ROOT / "docker-compose.yml"]
            )
        },
        "locust_version": locust_version.stdout.strip(),
        "host_resources": _host_resources(),
        "api_container": container,
        "api": api,
        "database_counts_at_matrix_start": _database_counts(args.profile_database_url),
        "configuration": {
            "host": args.host,
            "benchmark_database": args.benchmark_database,
            "profile_database_host": profile_database_url.host,
            "profile_database_port": profile_database_url.port,
            "workload": args.workload,
            "users": args.users,
            "repetitions": args.repetitions,
            "spawn_rate_users_per_second": args.spawn_rate,
            "warmup_seconds_after_ramp": args.warmup_seconds,
            "measurement_seconds": args.measurement_seconds,
            "drain_timeout_seconds": args.drain_seconds,
            "seed_base": args.seed,
            "user_selection": args.user_selection,
            "hot_user_count": args.hot_user_count if args.user_selection == "hot" else 0,
            "max_retries": args.max_retries,
            "request_timeout_seconds": args.request_timeout_seconds,
            "cache_state": args.cache_state,
            "locust_image": args.locust_image,
        },
    }
    _json(matrix_dir / "matrix.json", baseline)
    results: list[dict[str, object]] = []
    for user_count in args.users:
        for repetition in range(1, args.repetitions + 1):
            run_dir = matrix_dir / f"{args.workload}-users-{user_count}-rep-{repetition}"
            run_dir.mkdir()
            command = _run_command(
                args,
                run_dir,
                user_count,
                repetition,
                dataset_id=str(api["dataset_id"]),
                cache_enabled=bool(api["cache_enabled"]),
                locust_image=args.locust_image,
                loadgen_database_url=args.loadgen_database_url,
            )
            started_at = _utc_now()
            database_counts_before = _database_counts(args.profile_database_url)
            host_before = _host_resources()
            container_before = _container_usage(args.api_container)
            with (run_dir / "locust.log").open("w", encoding="utf-8") as log:
                locust_environment = os.environ.copy()
                if not args.locust_image:
                    locust_environment["ADFLOW_DATABASE_URL"] = args.profile_database_url
                    locust_environment["ADFLOW_TEST_DATABASE_URL"] = profile_database_url.set(
                        database="adflow_test"
                    ).render_as_string(hide_password=False)
                result = subprocess.run(
                    command,
                    cwd=BACKEND_ROOT,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=False,
                    env=locust_environment,
                )
            summary = _parse_summary(run_dir / "locust.log")
            phases_path = run_dir / "phases.jsonl"
            phases = (
                [json.loads(line) for line in phases_path.read_text(encoding="utf-8").splitlines()]
                if phases_path.exists()
                else []
            )
            required_phases = {
                "ramp_complete",
                "measurement_started",
                "measurement_ended",
                "drain_started",
                "drain_completed",
            }
            observed_phases = {phase.get("event") for phase in phases}
            run_status = (
                "complete"
                if result.returncode == 0
                and summary is not None
                and required_phases.issubset(observed_phases)
                else "incomplete"
            )
            run_manifest = {
                "status": run_status,
                "started_at": started_at,
                "finished_at": _utc_now(),
                "exit_code": result.returncode,
                "database_counts_before": database_counts_before,
                "database_counts_after": _database_counts(args.profile_database_url),
                "host_resources_before": host_before,
                "host_resources_after": _host_resources(),
                "api_container_usage_before": container_before,
                "api_container_usage_after": _container_usage(args.api_container),
                "summary": summary,
                "phases": phases,
                "artifacts": [path.name for path in sorted(run_dir.iterdir()) if path.is_file()],
            }
            _json(run_dir / "run.json", run_manifest)
            results.append({"run": run_dir.name, "status": run_status, "summary": summary})
            _json(
                matrix_dir / "matrix.json", {**baseline, "runs": results, "updated_at": _utc_now()}
            )
    return 0 if results and all(item["status"] == "complete" for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
