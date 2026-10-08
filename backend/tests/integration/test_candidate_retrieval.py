import json
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import SecretStr
from sqlalchemy import delete, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import WorkflowError
from app.db.catalog import read_catalog
from app.db.session import Database
from app.models.records import Ad, Advertiser, Dataset
from app.retrieval.contracts import RetrievalUser
from app.retrieval.current import CurrentCandidateRetriever
from app.retrieval.snapshots import ActiveSnapshot, HnswSettings, IndexEntry, build_snapshot
from app.retrieval.vectors import ad_vector


@pytest.fixture
def inventory(database: Database) -> Iterator[tuple[Session, UUID, list[Ad]]]:
    with database.session() as session:
        dataset = Dataset(seed=13, generator_version="retrieval-test", configuration={})
        session.add(dataset)
        session.flush()
        advertiser = Advertiser(dataset_id=dataset.id, name="Synthetic advertiser", active=True)
        session.add(advertiser)
        session.flush()
        ads = [
            Ad(
                dataset_id=dataset.id,
                advertiser_id=advertiser.id,
                title=f"Ad {number}",
                description="Fixture",
                target_url="https://example.test",
                category=category,
                interests=[category],
                bid=Decimal(bid),
                active=True,
            )
            for number, (category, bid) in enumerate(
                [("technology", "1.25"), ("gaming", "3.00"), ("music", "3.00")]
            )
        ]
        session.add_all(ads)
        session.flush()
        yield session, dataset.id, ads


def test_empty_interests_use_current_bid_then_id_without_cosine(
    inventory: tuple[Session, UUID, list[Ad]],
) -> None:
    session, dataset_id, ads = inventory
    result = CurrentCandidateRetriever(session, ActiveSnapshot()).retrieve(
        RetrievalUser(id=1, dataset_id=dataset_id, interests=()), limit=2
    )
    assert [ad.id for ad in result.candidates] == [ads[1].id, ads[2].id]
    assert [ad.similarity for ad in result.candidates] == [None, None]
    assert result.mode == "nonpersonalized"
    assert result.fallback_reason == "empty_interests"
    assert result.index_version is None
    assert result.elapsed_ms >= 0


def test_missing_index_scores_current_inventory_and_preserves_small_counts(
    inventory: tuple[Session, UUID, list[Ad]],
) -> None:
    session, dataset_id, ads = inventory
    ads[2].active = False
    session.flush()
    result = CurrentCandidateRetriever(session, ActiveSnapshot()).retrieve(
        RetrievalUser(id=1, dataset_id=dataset_id, interests=("technology",))
    )
    assert [ad.id for ad in result.candidates] == [ads[0].id, ads[1].id]
    assert [ad.similarity for ad in result.candidates] == [1, 0]
    assert result.mode == "exact_fallback"
    assert result.fallback_reason == "missing_index"
    assert result.requested_count == 500
    assert result.returned_count == 2


@pytest.mark.parametrize("hnsw", [None, HnswSettings(m=16, ef_construction=80, ef_search=64)])
def test_current_snapshot_uses_index_but_catalog_edits_force_visible_exact_fallback(
    inventory: tuple[Session, UUID, list[Ad]], tmp_path: Path, hnsw: HnswSettings | None
) -> None:
    session, dataset_id, ads = inventory
    catalog = read_catalog(session, dataset_id)
    build_snapshot(
        tmp_path / "index",
        catalog.entries,
        dataset_id=dataset_id,
        catalog_version=catalog.version,
        hnsw=hnsw,
    )
    active = ActiveSnapshot()
    snapshot = active.reload(tmp_path / "index")
    retriever = CurrentCandidateRetriever(session, active)
    user = RetrievalUser(id=1, dataset_id=dataset_id, interests=("technology",))
    indexed = retriever.retrieve(user, limit=2)
    assert indexed.mode == ("hnsw" if hnsw is not None else "exact")
    assert indexed.hnsw_ef_search == (64 if hnsw is not None else None)
    assert indexed.index_version == str(snapshot.manifest.snapshot_version)
    assert [ad.id for ad in indexed.candidates] == [ads[0].id, ads[1].id]
    ads[0].active = False
    session.flush()
    fallback = retriever.retrieve(user, limit=2)
    assert fallback.mode == "exact_fallback"
    assert fallback.fallback_reason == "stale_index"
    assert fallback.index_version is None
    assert [ad.id for ad in fallback.candidates] == [ads[1].id, ads[2].id]


@pytest.mark.parametrize("failure", ["missing_index", "corrupt_index", "incompatible_index"])
@pytest.mark.parametrize("hnsw", [None, HnswSettings()])
def test_failed_reload_keeps_old_reference_but_retrieval_reports_degraded_operation(
    inventory: tuple[Session, UUID, list[Ad]],
    tmp_path: Path,
    failure: str,
    hnsw: HnswSettings | None,
) -> None:
    session, dataset_id, ads = inventory
    catalog = read_catalog(session, dataset_id)
    path = tmp_path / "index"
    build_snapshot(
        path, catalog.entries, dataset_id=dataset_id, catalog_version=catalog.version, hnsw=hnsw
    )
    active = ActiveSnapshot()
    old = active.reload(path)
    if failure == "missing_index":
        (path / "ids.json").unlink()
    elif failure == "corrupt_index":
        (path / "index.faiss").write_bytes(b"broken")
    else:
        manifest = json.loads((path / "manifest.json").read_text())
        manifest["runtime"]["faiss_version"] = "incompatible"
        (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        active.reload(path)
    assert active.acquire() is old
    result = CurrentCandidateRetriever(session, active).retrieve(
        RetrievalUser(id=1, dataset_id=dataset_id, interests=("technology",)), limit=1
    )
    assert result.mode == "exact_fallback"
    assert result.fallback_reason == failure
    assert result.candidates[0].id == ads[0].id


@pytest.mark.parametrize(
    "search_limit,mode,expansions,searched", [(4, "exact", 2, 7), (2, "exact_fallback", 1, 3)]
)
@pytest.mark.parametrize("hnsw", [None, HnswSettings()])
def test_missing_index_ids_expand_to_bound_then_use_marked_current_inventory_fallback(
    inventory: tuple[Session, UUID, list[Ad]],
    tmp_path: Path,
    search_limit: int,
    mode: str,
    expansions: int,
    searched: int,
    hnsw: HnswSettings | None,
) -> None:
    session, dataset_id, ads = inventory
    ads[0].interests = ["gaming"]
    session.flush()
    catalog = read_catalog(session, dataset_id)
    # Missing IDs rank strictly ahead of all real entries; no boundary-tie assumption.
    missing = [
        IndexEntry(ad_id=2**63 - offset, vector=ad_vector([], category="technology"))
        for offset in (1, 2)
    ]
    build_snapshot(
        tmp_path / "sparse",
        (*catalog.entries, *missing),
        dataset_id=dataset_id,
        catalog_version=catalog.version,
        hnsw=hnsw,
    )
    active = ActiveSnapshot()
    active.reload(tmp_path / "sparse")
    result = CurrentCandidateRetriever(session, active, search_limit=search_limit).retrieve(
        RetrievalUser(id=1, dataset_id=dataset_id, interests=("technology",)), limit=1
    )
    assert result.candidates[0].id == ads[0].id
    assert result.candidates[0].similarity == pytest.approx(0.70710678)
    assert result.mode == ("hnsw" if mode == "exact" and hnsw is not None else mode)
    assert result.expansion_count == expansions
    assert result.searched_count == searched
    assert result.fallback_scanned_count == (3 if mode == "exact_fallback" else 0)
    assert result.fallback_reason == (
        "insufficient_candidates" if mode == "exact_fallback" else None
    )
    assert result.elapsed_ms >= result.vector_elapsed_ms + result.fallback_elapsed_ms


@pytest.mark.parametrize(
    "change", ["advertiser_off", "delete", "insert", "activate", "topics", "bid", "title"]
)
@pytest.mark.parametrize("hnsw", [None, HnswSettings()])
def test_catalog_changes_use_current_metadata_and_cannot_silently_omit_inventory(
    inventory: tuple[Session, UUID, list[Ad]],
    tmp_path: Path,
    change: str,
    hnsw: HnswSettings | None,
) -> None:
    session, dataset_id, ads = inventory
    if change == "activate":
        ads[0].active = False
        session.flush()
    catalog = read_catalog(session, dataset_id)
    path = tmp_path / "index"
    build_snapshot(
        path, catalog.entries, dataset_id=dataset_id, catalog_version=catalog.version, hnsw=hnsw
    )
    active = ActiveSnapshot()
    active.reload(path)
    expected_id: int | None = ads[0].id
    if change == "advertiser_off":
        session.execute(
            update(Advertiser).where(Advertiser.id == ads[0].advertiser_id).values(active=False)
        )
        expected_id = None
    elif change == "delete":
        session.execute(delete(Ad).where(Ad.id == ads[0].id))
        expected_id = ads[1].id
    elif change == "insert":
        new = Ad(
            dataset_id=dataset_id,
            advertiser_id=ads[0].advertiser_id,
            title="New",
            description="Fixture",
            target_url="https://example.test",
            category="technology",
            interests=[],
            bid=Decimal("9"),
            active=True,
        )
        session.add(new)
    elif change == "activate":
        ads[0].active = True
    elif change == "topics":
        ads[1].category = "technology"
        ads[1].interests = []
    elif change == "bid":
        ads[0].bid = Decimal("4.50")
    else:
        ads[0].title = "Edited title"
    session.flush()
    result = CurrentCandidateRetriever(session, active).retrieve(
        RetrievalUser(id=1, dataset_id=dataset_id, interests=("technology",)), limit=3
    )
    assert result.fallback_reason == "stale_index"
    assert result.mode == "exact_fallback"
    assert (result.candidates[0].id if result.candidates else None) == expected_id
    if change == "insert":
        assert new.id in {ad.id for ad in result.candidates}
    elif change == "topics":
        assert result.candidates[1].similarity == 1
        assert result.candidates[1].category == "technology"
    elif change == "bid":
        assert result.candidates[0].bid == Decimal("4.50")
    elif change == "title":
        assert result.candidates[0].title == "Edited title"


@pytest.mark.parametrize("interests", [(), ("technology",)])
def test_empty_inventory_is_a_successful_empty_retrieval(
    inventory: tuple[Session, UUID, list[Ad]], interests: tuple[str, ...]
) -> None:
    session, dataset_id, ads = inventory
    session.execute(
        update(Advertiser).where(Advertiser.id == ads[0].advertiser_id).values(active=False)
    )
    result = CurrentCandidateRetriever(session, ActiveSnapshot()).retrieve(
        RetrievalUser(id=1, dataset_id=dataset_id, interests=interests)
    )
    assert result.candidates == ()
    assert result.returned_count == 0
    assert result.requested_count == 500


def test_database_connection_failure_is_503_instead_of_no_inventory(
    database_settings: Settings,
) -> None:
    unavailable = make_url(database_settings.test_database_url.get_secret_value()).set(port=1)
    settings = database_settings.model_copy(
        update={
            "test_database_url": SecretStr(unavailable.render_as_string(hide_password=False)),
            "db_connect_timeout_seconds": 1,
        }
    )
    database = Database(settings, use_test_database=True)
    try:
        with database.session() as session, pytest.raises(WorkflowError) as caught:
            CurrentCandidateRetriever(session, ActiveSnapshot()).retrieve(
                RetrievalUser(id=1, dataset_id=UUID(int=0), interests=("technology",))
            )
        assert caught.value.status_code == 503
        assert caught.value.code == "retrieval_unavailable"
    finally:
        database.dispose()


@pytest.mark.parametrize("limit", [0, -1, 501, True, 1.5])
def test_invalid_limits_are_rejected_before_database_work(
    inventory: tuple[Session, UUID, list[Ad]], limit: int
) -> None:
    session, dataset_id, _ = inventory
    with pytest.raises(ValueError):
        CurrentCandidateRetriever(session, ActiveSnapshot()).retrieve(
            RetrievalUser(id=1, dataset_id=dataset_id, interests=("technology",)), limit=limit
        )


def test_candidate_cap_is_500_even_when_inventory_is_larger(
    inventory: tuple[Session, UUID, list[Ad]],
) -> None:
    session, dataset_id, ads = inventory
    session.add_all(
        [
            Ad(
                dataset_id=dataset_id,
                advertiser_id=ads[0].advertiser_id,
                title=f"Extra {number}",
                description="Fixture",
                target_url="https://example.test",
                category="technology",
                interests=[],
                bid=Decimal("1"),
                active=True,
            )
            for number in range(500)
        ]
    )
    session.flush()
    result = CurrentCandidateRetriever(session, ActiveSnapshot()).retrieve(
        RetrievalUser(id=1, dataset_id=dataset_id, interests=("technology",))
    )
    assert result.returned_count == 500
    assert len({ad.id for ad in result.candidates}) == 500
    assert result.fallback_scanned_count == 503


def test_committed_catalog_change_is_visible_to_a_reused_retriever_session(
    inventory: tuple[Session, UUID, list[Ad]], database: Database, tmp_path: Path
) -> None:
    session, dataset_id, ads = inventory
    catalog = read_catalog(session, dataset_id)
    build_snapshot(
        tmp_path / "index", catalog.entries, dataset_id=dataset_id, catalog_version=catalog.version
    )
    session.commit()  # Release the offline builder's revision lock before concurrent edits.
    active = ActiveSnapshot()
    active.reload(tmp_path / "index")
    retriever = CurrentCandidateRetriever(session, active)
    user = RetrievalUser(id=1, dataset_id=dataset_id, interests=("technology",))
    assert retriever.retrieve(user, limit=1).mode == "exact"
    with database.transaction() as editor:
        editor.execute(update(Ad).where(Ad.id == ads[0].id).values(active=False))
    changed = retriever.retrieve(user, limit=1)
    assert changed.fallback_reason == "stale_index"
    assert changed.candidates[0].id == ads[1].id


def test_rolled_back_catalog_edit_does_not_invalidate_snapshot(
    inventory: tuple[Session, UUID, list[Ad]], tmp_path: Path
) -> None:
    session, dataset_id, ads = inventory
    catalog = read_catalog(session, dataset_id)
    build_snapshot(
        tmp_path / "index", catalog.entries, dataset_id=dataset_id, catalog_version=catalog.version
    )
    active = ActiveSnapshot()
    active.reload(tmp_path / "index")
    savepoint = session.begin_nested()
    session.execute(update(Ad).where(Ad.id == ads[0].id).values(active=False))
    savepoint.rollback()
    result = CurrentCandidateRetriever(session, active).retrieve(
        RetrievalUser(id=1, dataset_id=dataset_id, interests=("technology",)), limit=1
    )
    assert result.mode == "exact"
    assert result.candidates[0].id == ads[0].id


def test_rebuilding_and_successful_reload_clear_degraded_state(
    inventory: tuple[Session, UUID, list[Ad]], tmp_path: Path
) -> None:
    session, dataset_id, ads = inventory
    active = ActiveSnapshot()
    with pytest.raises(ValueError):
        active.reload(tmp_path / "missing")
    catalog = read_catalog(session, dataset_id)
    build_snapshot(
        tmp_path / "replacement",
        catalog.entries,
        dataset_id=dataset_id,
        catalog_version=catalog.version,
    )
    active.reload(tmp_path / "replacement")
    result = CurrentCandidateRetriever(session, active).retrieve(
        RetrievalUser(id=1, dataset_id=dataset_id, interests=("technology",)), limit=1
    )
    assert result.mode == "exact"
    assert result.fallback_reason is None
    assert result.candidates[0].id == ads[0].id


@pytest.mark.parametrize("interests", [(), ("technology",)])
def test_invalid_current_topics_are_a_data_error_not_empty_inventory(
    inventory: tuple[Session, UUID, list[Ad]], interests: tuple[str, ...]
) -> None:
    session, dataset_id, ads = inventory
    ads[0].category = "unknown"
    session.flush()
    with pytest.raises(WorkflowError) as caught:
        CurrentCandidateRetriever(session, ActiveSnapshot()).retrieve(
            RetrievalUser(id=1, dataset_id=dataset_id, interests=interests)
        )
    assert caught.value.status_code == 503


def test_wrong_dataset_snapshot_is_marked_stale(
    inventory: tuple[Session, UUID, list[Ad]], tmp_path: Path
) -> None:
    session, dataset_id, ads = inventory
    catalog = read_catalog(session, dataset_id)
    build_snapshot(
        tmp_path / "wrong", catalog.entries, dataset_id=UUID(int=0), catalog_version=catalog.version
    )
    active = ActiveSnapshot()
    active.reload(tmp_path / "wrong")
    result = CurrentCandidateRetriever(session, active).retrieve(
        RetrievalUser(id=1, dataset_id=dataset_id, interests=("technology",)), limit=1
    )
    assert result.fallback_reason == "stale_index"
    assert result.candidates[0].id == ads[0].id


def test_large_configured_expansion_can_batch_metadata_beyond_postgres_parameter_limit(
    inventory: tuple[Session, UUID, list[Ad]], tmp_path: Path
) -> None:
    session, dataset_id, ads = inventory
    ads[0].interests = ["gaming"]
    session.flush()
    catalog = read_catalog(session, dataset_id)
    vector = ad_vector([], category="technology")
    missing = [IndexEntry(ad_id=2**63 - offset, vector=vector) for offset in range(1, 65536)]
    build_snapshot(
        tmp_path / "large",
        (*catalog.entries, *missing),
        dataset_id=dataset_id,
        catalog_version=catalog.version,
    )
    active = ActiveSnapshot()
    active.reload(tmp_path / "large")
    result = CurrentCandidateRetriever(session, active, search_limit=65536).retrieve(
        RetrievalUser(id=1, dataset_id=dataset_id, interests=("technology",)), limit=1
    )
    assert result.mode == "exact"
    assert result.candidates[0].id == ads[0].id
    assert result.expansion_count == 16


def test_hnsw_retriever_reports_query_depth_override_and_preserves_build_settings(
    inventory: tuple[Session, UUID, list[Ad]], tmp_path: Path
) -> None:
    session, dataset_id, ads = inventory
    catalog = read_catalog(session, dataset_id)
    path = tmp_path / "hnsw"
    build_snapshot(
        path,
        catalog.entries,
        dataset_id=dataset_id,
        catalog_version=catalog.version,
        hnsw=HnswSettings(),
    )
    active = ActiveSnapshot()
    snapshot = active.reload(path)
    result = CurrentCandidateRetriever(session, active, ef_search=32).retrieve(
        RetrievalUser(id=1, dataset_id=dataset_id, interests=("technology",)), limit=1
    )
    assert result.mode == "hnsw"
    assert result.hnsw_ef_search == 32
    assert result.candidates[0].id == ads[0].id
    assert snapshot.manifest.hnsw == HnswSettings()


@pytest.mark.parametrize("hnsw", [None, HnswSettings(m=16, ef_construction=80, ef_search=1024)])
def test_index_families_share_tied_candidate_cap_nonpersonalized_and_small_inventory_contracts(
    inventory: tuple[Session, UUID, list[Ad]], tmp_path: Path, hnsw: HnswSettings | None
) -> None:
    session, dataset_id, ads = inventory
    for ad in ads:
        ad.category = "technology"
        ad.interests = []
    extra = [
        Ad(
            dataset_id=dataset_id,
            advertiser_id=ads[0].advertiser_id,
            title=f"Tie {number}",
            description="Fixture",
            target_url="https://example.test",
            category="technology",
            interests=[],
            bid=Decimal("1"),
            active=True,
        )
        for number in range(500)
    ]
    session.add_all(extra)
    session.flush()
    catalog = read_catalog(session, dataset_id)
    path = tmp_path / "index"
    build_snapshot(
        path, catalog.entries, dataset_id=dataset_id, catalog_version=catalog.version, hnsw=hnsw
    )
    active = ActiveSnapshot()
    active.reload(path)
    retriever = CurrentCandidateRetriever(session, active)
    user = RetrievalUser(id=1, dataset_id=dataset_id, interests=("technology",))
    result = retriever.retrieve(user)
    ids = [ad.id for ad in result.candidates]
    if hnsw is None:
        assert result.mode == "exact"
    else:
        assert result.mode in ("hnsw", "exact_fallback")
        if result.mode == "exact_fallback":
            assert result.fallback_reason == "insufficient_candidates"
            assert result.fallback_scanned_count == 503
    assert len(ids) == len(set(ids)) == 500
    assert set(ids) <= {ad.id for ad in [*ads, *extra]}
    assert ids == sorted(ids)
    assert all(ad.similarity == pytest.approx(1) for ad in result.candidates)
    nonpersonalized = retriever.retrieve(user.model_copy(update={"interests": ()}), limit=2)
    assert nonpersonalized.mode == "nonpersonalized"
    assert [ad.id for ad in nonpersonalized.candidates] == [ads[1].id, ads[2].id]
    assert all(ad.similarity is None for ad in nonpersonalized.candidates)
    session.execute(
        update(Ad).where(Ad.dataset_id == dataset_id, Ad.id != ads[0].id).values(active=False)
    )
    limited = retriever.retrieve(user)
    assert limited.returned_count == 1
    assert limited.candidates[0].id == ads[0].id
    assert limited.fallback_reason == "stale_index"
    session.execute(
        update(Advertiser).where(Advertiser.id == ads[0].advertiser_id).values(active=False)
    )
    assert retriever.retrieve(user).candidates == ()
