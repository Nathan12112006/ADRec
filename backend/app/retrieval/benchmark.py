"""Offline, serial component comparisons; never writes serving history."""

import gzip
import hashlib
import json
import os
import platform
import random
import subprocess
from collections.abc import Sequence
from dataclasses import asdict
from datetime import datetime, timezone
from math import ceil
from pathlib import Path
from statistics import fmean
from time import perf_counter
from typing import Any
from uuid import UUID, uuid4

import faiss
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db.catalog import read_catalog
from app.db.session import Database
from app.models.records import Ad, Advertiser, Dataset, User
from app.ranking import BaselineCandidate, select_baseline
from app.retrieval.contracts import RetrievalUser
from app.retrieval.current import CurrentCandidateRetriever
from app.retrieval.evaluation import evaluate_recall, promotion_decision
from app.retrieval.limits import CandidateLimit
from app.retrieval.snapshots import ActiveSnapshot, HnswSettings, build_snapshot, current_runtime
from app.retrieval.vectors import user_vector


class BenchmarkConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_limit: CandidateLimit = 500
    query_count: int = Field(default=100, strict=True, ge=1, le=5000)
    empty_query_count: int = Field(default=5, strict=True, ge=0, le=100)
    query_seed: int = Field(default=1601, strict=True)
    warmup_queries: int = Field(default=10, strict=True, ge=0, le=5000)
    repetitions: int = Field(default=3, strict=True, ge=1, le=20)
    threads: int = Field(default=1, strict=True, ge=1, le=64)
    boundary_tolerance: float = Field(default=1e-6, ge=0, le=0.01, allow_inf_nan=False)
    hnsw: HnswSettings = HnswSettings()


def _distribution(values: Sequence[float]) -> dict[str, float | int | None]:
    ordered = sorted(values)
    return {
        "count": len(ordered),
        "mean": fmean(ordered) if ordered else None,
        "p50": ordered[ceil(0.50 * len(ordered)) - 1] if ordered else None,
        "p95": ordered[ceil(0.95 * len(ordered)) - 1] if ordered else None,
        "p99": ordered[ceil(0.99 * len(ordered)) - 1] if ordered else None,
        "min": ordered[0] if ordered else None,
        "max": ordered[-1] if ordered else None,
    }


def _memory() -> dict[str, Any]:
    """Process-wide observations, not incremental native index allocations."""
    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"Get-Process -Id {os.getpid()} | "
                    "Select-Object WorkingSet64,PeakWorkingSet64 | ConvertTo-Json",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            values = json.loads(result.stdout)
            return {
                "rss_bytes": int(values["WorkingSet64"]),
                "peak_rss_bytes": int(values["PeakWorkingSet64"]),
                "source": "Windows process working set (cumulative peak)",
            }
        except (OSError, subprocess.SubprocessError, ValueError, KeyError):
            pass
    else:
        try:
            values = {}
            for line in Path("/proc/self/status").read_text().splitlines():
                if line.startswith(("VmRSS:", "VmHWM:")):
                    key, amount, _unit = line.split()
                    values[key] = int(amount) * 1024
            return {
                "rss_bytes": values["VmRSS:"],
                "peak_rss_bytes": values["VmHWM:"],
                "source": "Linux proc process RSS (cumulative peak)",
            }
        except (OSError, ValueError, KeyError):
            pass
    return {"rss_bytes": None, "peak_rss_bytes": None, "source": "unavailable"}


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")


def _code_identity() -> dict[str, Any]:
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5, check=True
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        revision = None
    return {
        "git_revision": revision,
        "source_sha256": {
            name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in ("benchmark.py", "evaluation.py", "benchmark_cli.py")
        },
    }


def _winner(user: RetrievalUser, candidates: Sequence[BaselineCandidate]) -> dict[str, Any] | None:
    selected = select_baseline(user.interests, candidates)
    if selected is None:
        return None
    return {
        "ad_id": selected.id,
        "score": len(set(user.interests) & set(selected.interests)),
        "bid": str(selected.bid),
    }


def _measure(
    session: Session,
    user: RetrievalUser,
    path: str,
    active: ActiveSnapshot,
    limit: int,
) -> dict[str, Any]:
    start = perf_counter()
    if path == "full_ad":
        metadata_start = perf_counter()
        candidates = tuple(
            BaselineCandidate(row.id, tuple(row.interests), row.bid)
            for row in session.execute(
                select(Ad.id, Ad.interests, Ad.bid)
                .join(Advertiser)
                .where(
                    Ad.dataset_id == user.dataset_id,
                    Ad.active.is_(True),
                    Advertiser.active.is_(True),
                )
                .execution_options(yield_per=1000)
            )
        )
        metadata_ms = (perf_counter() - metadata_start) * 1000
        details: dict[str, Any] = {
            "mode": "full_ad",
            "retrieval_ms": metadata_ms,
            "vector_ms": 0.0,
            "metadata_ms": metadata_ms,
            "fallback_ms": 0.0,
            "fallback_reason": None,
            "candidate_count": len(candidates),
            "candidate_ids": None,
        }
    else:
        result = CurrentCandidateRetriever(session, active).retrieve(user, limit=limit)
        candidates = tuple(
            BaselineCandidate(ad.id, ad.interests, ad.bid) for ad in result.candidates
        )
        details = {
            "mode": result.mode,
            "retrieval_ms": result.elapsed_ms,
            "vector_ms": result.vector_elapsed_ms,
            "metadata_ms": result.metadata_elapsed_ms,
            "fallback_ms": result.fallback_elapsed_ms,
            "fallback_reason": result.fallback_reason,
            "candidate_count": result.returned_count,
            "candidate_ids": [ad.id for ad in result.candidates],
            "index_version": result.index_version,
            "searched_count": result.searched_count,
            "expansion_count": result.expansion_count,
            "fallback_scanned_count": result.fallback_scanned_count,
        }
    ranking_start = perf_counter()
    winner = _winner(user, candidates)
    ranking_ms = (perf_counter() - ranking_start) * 1000
    return {
        **details,
        "path": path,
        "winner": winner,
        "ranking_ms": ranking_ms,
        "component_total_ms": (perf_counter() - start) * 1000,
    }


def _summaries(samples: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for population in ("personalized", "empty_interests"):
        summary[population] = {}
        for path in ("full_ad", "flat", "hnsw"):
            rows = [
                row for row in samples if row["population"] == population and row["path"] == path
            ]
            summary[population][path] = {
                "count": len(rows),
                "timings_ms": {
                    name: _distribution([row[name] for row in rows])
                    for name in (
                        "retrieval_ms",
                        "vector_ms",
                        "metadata_ms",
                        "fallback_ms",
                        "ranking_ms",
                        "component_total_ms",
                    )
                },
                "component_operations_per_second": 1000
                * len(rows)
                / sum(row["component_total_ms"] for row in rows)
                if rows
                else None,
                "fallback_rate": sum(row["fallback_reason"] is not None for row in rows) / len(rows)
                if rows
                else None,
                "ordinary_recall": _distribution(
                    [
                        row["recall"]["ordinary_recall"]
                        for row in rows
                        if row["recall"] and row["recall"]["ordinary_recall"] is not None
                    ]
                ),
                "tie_aware_recall": _distribution(
                    [
                        row["recall"]["tie_aware_recall"]
                        for row in rows
                        if row["recall"] and row["recall"]["tie_aware_recall"] is not None
                    ]
                ),
                "winner_disagreements_with_full_ad": sum(
                    not row["same_winner_as_full_ad"] for row in rows
                ),
                "missed_superior_count": sum(
                    row["recall"]["missed_superior_count"] or 0 for row in rows if row["recall"]
                ),
            }
    return summary


def run_comparison(
    database: Database,
    dataset_id: UUID,
    output: Path,
    config: BenchmarkConfig,
) -> dict[str, Any]:
    """Freeze repeatable-read inventory/profiles, save inputs/artifacts, compare serially.

    A new output directory is mandatory. A failed run retains an incomplete manifest.
    This is a component experiment, not HTTP latency or a durable recommendation.
    """
    output.mkdir(parents=True, exist_ok=False)
    started_at = datetime.now(timezone.utc).isoformat()
    run_id = str(uuid4())
    _write_json(
        output / "status.json", {"status": "incomplete", "run_id": run_id, "started_at": started_at}
    )
    previous_threads = faiss.omp_get_max_threads()
    faiss.omp_set_num_threads(config.threads)
    try:
        with database.session() as session, session.begin():
            session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
            # Offline builds can exceed the serving session's idle timeout.
            session.execute(text("SET LOCAL idle_in_transaction_session_timeout = 0"))
            dataset = session.get(Dataset, dataset_id)
            if dataset is None:
                raise ValueError("unknown benchmark dataset")
            catalog = read_catalog(session, dataset_id)
            users = tuple(
                RetrievalUser(
                    id=profile.id, dataset_id=dataset_id, interests=tuple(profile.interests)
                )
                for profile in session.execute(
                    select(User.id, User.interests)
                    .where(User.dataset_id == dataset_id)
                    .order_by(User.id)
                )
            )
            if not users:
                raise ValueError("benchmark requires at least one synthetic user")
            rng = random.Random(config.query_seed)
            nonempty = [user for user in users if user.interests]
            queries = rng.sample(nonempty, min(config.query_count, len(nonempty)))
            empties = [
                users[index % len(users)].model_copy(update={"interests": ()})
                for index in range(config.empty_query_count)
            ]
            query_payload = {
                "personalized": [user.model_dump(mode="json") for user in queries],
                "empty_interests": [user.model_dump(mode="json") for user in empties],
            }
            _write_json(output / "queries.json", query_payload)
            # Full payload export enables replay of the actual metadata/eligibility snapshot.
            catalog_digest = hashlib.sha256()
            with gzip.open(output / "catalog.jsonl.gz", "wt", encoding="utf-8") as stream:
                for exported in session.execute(
                    select(*Ad.__table__.columns, Advertiser.active.label("advertiser_active"))
                    .join(Advertiser)
                    .where(Ad.dataset_id == dataset_id)
                    .order_by(Ad.id)
                    .execution_options(yield_per=1000)
                ).mappings():
                    payload = dict(exported)
                    payload["dataset_id"] = str(payload["dataset_id"])
                    payload["bid"] = str(payload["bid"])
                    line = json.dumps(payload, sort_keys=True) + "\n"
                    catalog_digest.update(line.encode("utf-8"))
                    stream.write(line)
            counts = {
                name: session.scalar(
                    select(func.count()).select_from(model).where(model.dataset_id == dataset_id)
                )
                for name, model in (("users", User), ("advertisers", Advertiser), ("ads", Ad))
            }
            before_memory = _memory()
            indexes: dict[str, Any] = {}
            active: dict[str, ActiveSnapshot] = {"full_ad": ActiveSnapshot()}
            for path in ("flat", "hnsw"):
                build_start = perf_counter()
                built = build_snapshot(
                    output / path,
                    catalog.entries,
                    dataset_id=dataset_id,
                    catalog_version=catalog.version,
                    hnsw=config.hnsw if path == "hnsw" else None,
                )
                build_ms = (perf_counter() - build_start) * 1000
                active[path] = ActiveSnapshot()
                load_start = perf_counter()
                active[path].reload(output / path)
                load_ms = (perf_counter() - load_start) * 1000
                indexes[path] = {
                    "manifest": built.manifest.model_dump(mode="json"),
                    "build_ms": build_ms,
                    "reload_ms": load_ms,
                    "index_bytes": (output / path / "index.faiss").stat().st_size,
                    "artifact_bytes": sum(
                        item.stat().st_size for item in (output / path).iterdir()
                    ),
                    "process_memory": _memory(),
                }
            references: dict[int, tuple[dict[int, float], list[int]]] = {}
            for user in queries:
                vector = user_vector(user.interests)
                assert vector is not None
                scores = {entry.ad_id: vector.similarity(entry.vector) for entry in catalog.entries}
                reference = CurrentCandidateRetriever(session, active["flat"]).retrieve(
                    user, config.candidate_limit
                )
                references[user.id] = (scores, [ad.id for ad in reference.candidates])
            paths = ("full_ad", "flat", "hnsw")
            all_queries = queries + empties
            if not all_queries:
                raise ValueError("no requested query population is available")
            for index in range(config.warmup_queries):
                for path in paths:
                    _measure(
                        session,
                        all_queries[index % len(all_queries)],
                        path,
                        active[path],
                        config.candidate_limit,
                    )
            samples: list[dict[str, Any]] = []
            measured_at = datetime.now(timezone.utc).isoformat()
            cpu_start = os.times()
            for repetition in range(config.repetitions):
                for population, population_queries in (
                    ("personalized", queries),
                    ("empty_interests", empties),
                ):
                    for query_index, user in enumerate(population_queries):
                        order = list(paths)
                        rng.shuffle(
                            order
                        )  # deterministic interleaving avoids a fixed path-order advantage
                        rows = {
                            path: _measure(
                                session, user, path, active[path], config.candidate_limit
                            )
                            for path in order
                        }
                        full_winner = rows["full_ad"]["winner"]
                        for path, row in rows.items():
                            quality = None
                            if population == "personalized" and path != "full_ad":
                                scores, reference_ids = references[user.id]
                                quality = asdict(
                                    evaluate_recall(
                                        scores,
                                        reference_ids,
                                        row["candidate_ids"],
                                        limit=config.candidate_limit,
                                        tolerance=config.boundary_tolerance,
                                    )
                                )
                            row.update(
                                population=population,
                                query_index=query_index,
                                user_id=user.id,
                                repetition=repetition + 1,
                                recall=quality,
                                same_winner_as_full_ad=(row["winner"] or {}).get("ad_id")
                                == (full_winner or {}).get("ad_id"),
                                overlap_score_difference=(row["winner"] or {}).get("score", 0)
                                - (full_winner or {}).get("score", 0),
                            )
                            samples.append(row)
            cpu_end = os.times()
            summary = _summaries(samples)
            paired = {
                path: [
                    row
                    for row in samples
                    if row["population"] == "personalized" and row["path"] == path
                ]
                for path in ("flat", "hnsw")
            }
            decision = promotion_decision(
                [row["retrieval_ms"] for row in paired["flat"]],
                [row["retrieval_ms"] for row in paired["hnsw"]],
                [row["recall"]["tie_aware_recall"] for row in paired["hnsw"]],
                repetitions=config.repetitions,
                fallback_count=sum(
                    row["fallback_reason"] is not None for rows in paired.values() for row in rows
                ),
            )
            report: dict[str, Any] = {
                "schema_version": 1,
                "status": "complete",
                "run_id": run_id,
                "started_at": started_at,
                "measurement_started_at": measured_at,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "scope": "serial offline components; no HTTP, durable selection, or capacity claim",
                "config": config.model_dump(mode="json"),
                "provenance": {
                    "dataset_id": str(dataset_id),
                    "dataset_manifest": dataset.configuration,
                    "generator_version": dataset.generator_version,
                    "dataset_seed": dataset.seed,
                    "code_identity": _code_identity(),
                    "catalog_version": catalog.version,
                    "catalog_content_sha256": catalog_digest.hexdigest(),
                    "counts": counts,
                    "eligible_ads": len(catalog.entries),
                    "actual_personalized_queries": len(queries),
                    "actual_empty_queries": len(empties),
                    "query_sha256": hashlib.sha256(
                        (output / "queries.json").read_bytes()
                    ).hexdigest(),
                    "catalog_sha256": hashlib.sha256(
                        (output / "catalog.jsonl.gz").read_bytes()
                    ).hexdigest(),
                    "runtime": current_runtime().model_dump(),
                    "hardware": dict(platform.uname()._asdict()),
                    "logical_cpus": os.cpu_count(),
                    "processor": platform.processor(),
                    "database_location": {
                        "host": database.engine.url.host,
                        "port": database.engine.url.port,
                        "database": database.engine.url.database,
                    },
                    "postgres_version": session.scalar(text("SELECT version()")),
                    "ranking_strategy": "interest-overlap/baseline-v1",
                    "concurrency": 1,
                    "percentiles": "nearest rank from raw samples; never mean of percentiles",
                    "quality_aggregation": "query/repetition distribution; gate: minimum >= 0.95",
                    "query_policy": (
                        "seeded nonempty profile sample without replacement; "
                        "not used in index builds; empty-interest clones separate"
                    ),
                    "freeze": (
                        "repeatable-read transaction with shared catalog revision lock; "
                        "local idle timeout disabled during offline work"
                    ),
                    "memory_before_build": before_memory,
                    "memory_after_measurement": _memory(),
                    "measurement_process_cpu_seconds": (cpu_end.user + cpu_end.system)
                    - (cpu_start.user + cpu_start.system),
                },
                "indexes": indexes,
                "samples": samples,
                "summary": summary,
                "repetitions": {
                    str(rep): _summaries([row for row in samples if row["repetition"] == rep])
                    for rep in range(1, config.repetitions + 1)
                },
                "promotion": decision,
            }
        _write_json(output / "report.json", report)
        _write_json(output / "status.json", {"status": "complete", "run_id": run_id})
        return report
    except BaseException as error:
        _write_json(
            output / "status.json",
            {
                "status": "failed",
                "run_id": run_id,
                "error_type": type(error).__name__,
                "finished_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        raise
    finally:
        faiss.omp_set_num_threads(previous_threads)
