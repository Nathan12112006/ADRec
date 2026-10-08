"""Candidate retrieval against current PostgreSQL inventory."""

from collections.abc import Iterator
from heapq import nsmallest
from time import perf_counter
from typing import Literal

from pydantic import TypeAdapter
from sqlalchemy import BigInteger, any_, cast, select
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errors import WorkflowError
from app.db.catalog import catalog_version
from app.models.records import Ad, Advertiser
from app.retrieval.contracts import RetrievalCandidate, RetrievalResult, RetrievalUser
from app.retrieval.limits import MAX_SEARCH_LIMIT, CandidateLimit
from app.retrieval.snapshots import ActiveSnapshot
from app.retrieval.vectors import ad_vector, user_vector


class CurrentCandidateRetriever:
    def __init__(
        self,
        session: Session,
        snapshots: ActiveSnapshot,
        *,
        search_limit: int = 4000,
        ef_search: int | None = None,
    ) -> None:
        if type(search_limit) is not int or not 1 <= search_limit <= MAX_SEARCH_LIMIT:
            raise ValueError("search limit must be a positive integer within the expansion bound")
        self._session = session
        self._snapshots = snapshots
        self._search_limit = search_limit
        if ef_search is not None and (
            type(ef_search) is not int or not 1 <= ef_search <= MAX_SEARCH_LIMIT
        ):
            raise ValueError("ef_search must be a positive integer within the search bound")
        self._ef_search = ef_search

    def retrieve(self, user: RetrievalUser, limit: int = 500) -> RetrievalResult:
        start = perf_counter()
        TypeAdapter(CandidateLimit).validate_python(limit)
        if limit > self._search_limit:
            raise ValueError("search limit must cover the candidate limit")
        state = self._snapshots.status()
        if (
            self._ef_search is not None
            and state.failure_reason is None
            and state.snapshot is not None
            and state.snapshot.manifest.hnsw is None
        ):
            raise ValueError("ef_search applies only to HNSW snapshots")
        statement = (
            select(*Ad.__table__.columns, Advertiser.active.label("advertiser_active"))
            .join(Advertiser, Ad.advertiser_id == Advertiser.id)
            .where(
                Ad.dataset_id == user.dataset_id, Ad.active.is_(True), Advertiser.active.is_(True)
            )
        )
        query = user_vector(user.interests)
        reason = "empty_interests" if query is None else "missing_index"
        index_version = None
        indexed_mode: Literal["exact", "hnsw"] = "exact"
        hnsw_ef_search = None
        vector_ms = 0.0
        fallback_ms = 0.0
        searched_count = 0
        expansion_count = 0
        fallback_scanned_count = 0
        try:
            version = catalog_version(self._session, user.dataset_id)
            if query is None:
                fallback_start = perf_counter()
                candidates = tuple(
                    RetrievalCandidate.model_validate(dict(row) | {"similarity": None})
                    for row in self._session.execute(
                        statement.order_by(Ad.bid.desc(), Ad.id).limit(limit)
                    ).mappings()
                )
                fallback_ms = (perf_counter() - fallback_start) * 1000
            else:
                snapshot = state.snapshot
                if state.failure_reason is not None:
                    reason = state.failure_reason
                    snapshot = None
                candidates = ()
                if snapshot is not None:
                    if (
                        snapshot.manifest.dataset_id != user.dataset_id
                        or snapshot.manifest.catalog_version != version
                    ):
                        reason = "stale_index"
                    else:
                        count = limit
                        while True:
                            vector_start = perf_counter()
                            hits = snapshot.search(query, limit=count, ef_search=self._ef_search)
                            vector_ms += (perf_counter() - vector_start) * 1000
                            searched_count += len(hits)
                            scores = {hit.ad_id: hit.similarity for hit in hits}
                            candidates = tuple(
                                sorted(
                                    (
                                        RetrievalCandidate.model_validate(
                                            dict(row) | {"similarity": scores[row["id"]]}
                                        )
                                        for row in self._session.execute(
                                            statement.where(
                                                Ad.id == any_(cast(list(scores), ARRAY(BigInteger)))
                                            )
                                        ).mappings()
                                    ),
                                    key=lambda ad: (-(ad.similarity or 0), ad.id),
                                )
                            )[:limit]
                            if len(candidates) >= limit or count >= min(
                                self._search_limit, snapshot.manifest.count
                            ):
                                break
                            count = min(count * 2, self._search_limit, snapshot.manifest.count)
                            expansion_count += 1
                        if catalog_version(self._session, user.dataset_id) != version:
                            reason = "stale_index"
                        elif len(candidates) == limit:
                            index_version = str(snapshot.manifest.snapshot_version)
                            if snapshot.manifest.hnsw is not None:
                                indexed_mode = "hnsw"
                                hnsw_ef_search = (
                                    self._ef_search
                                    if self._ef_search is not None
                                    else snapshot.manifest.hnsw.ef_search
                                )
                        else:
                            reason = "insufficient_candidates"
                if index_version is None:
                    fallback_start = perf_counter()
                    with self._session.execute(statement.execution_options(yield_per=1000)) as rows:

                        def scored_candidates() -> Iterator[RetrievalCandidate]:
                            nonlocal fallback_scanned_count
                            for row in rows.mappings():
                                fallback_scanned_count += 1
                                score = query.similarity(
                                    ad_vector(row["interests"], category=row["category"])
                                )
                                yield RetrievalCandidate.model_validate(
                                    dict(row) | {"similarity": score}
                                )

                        candidates = tuple(
                            nsmallest(
                                limit,
                                scored_candidates(),
                                key=lambda ad: (-(ad.similarity or 0), ad.id),
                            )
                        )
                    fallback_ms = (perf_counter() - fallback_start) * 1000
        except (SQLAlchemyError, ValueError):
            raise WorkflowError(
                503, "retrieval_unavailable", "Current inventory is unavailable"
            ) from None
        elapsed_ms = (perf_counter() - start) * 1000
        return RetrievalResult(
            candidates=candidates,
            mode="nonpersonalized"
            if query is None
            else (indexed_mode if index_version else "exact_fallback"),
            index_version=index_version,
            hnsw_ef_search=hnsw_ef_search,
            requested_count=limit,
            elapsed_ms=elapsed_ms,
            vector_elapsed_ms=vector_ms,
            metadata_elapsed_ms=max(0, elapsed_ms - vector_ms - fallback_ms),
            fallback_elapsed_ms=fallback_ms,
            searched_count=searched_count,
            expansion_count=expansion_count,
            fallback_scanned_count=fallback_scanned_count,
            fallback_reason=None if index_version else reason,
        )
