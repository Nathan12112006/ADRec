"""Compare fixed ranking strategies on identical frozen pools; no database writes."""

import hashlib
import json
import platform
import sys
from decimal import Decimal
from pathlib import Path
from random import Random

from app.ctr.serving import CTRModel
from app.history.outcomes import (
    OutcomeAd,
    OutcomeConfig,
    OutcomeGenerator,
    OutcomeUser,
    stream_seed,
)
from app.ranking.strategies import ExpectedValue, InterestOverlap


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


history = Path(sys.argv[1]).resolve()
bundle = Path(sys.argv[2]).resolve()
output = Path(sys.argv[3]).resolve()
inputs = [history / name for name in ("manifest.json", "users.jsonl", "ads.jsonl")]
inputs.extend(sorted(path for path in bundle.iterdir() if path.is_file()))
before = {str(path): checksum(path) for path in inputs}
manifest = json.loads((history / "manifest.json").read_bytes())
for filename in ("users.jsonl", "ads.jsonl"):
    assert checksum(history / filename) == manifest["files"][filename]
users = sorted(
    (json.loads(line) for line in (history / "users.jsonl").read_text().splitlines()),
    key=lambda row: row["id"],
)
ads = sorted(
    (json.loads(line) for line in (history / "ads.jsonl").read_text().splitlines()),
    key=lambda row: row["id"],
)
assert all(ad["active"] and ad["advertiser_active"] for ad in ads)
selected_users = Random(stream_seed(26, "ranking-gate/users")).sample(users, 200)
model = CTRModel.load(bundle)
world = OutcomeGenerator(
    OutcomeConfig.model_validate(manifest["configuration"]["outcome"]),
    seed=manifest["configuration"]["seed"],
)
totals = {name: {"clicks": 0, "simulated_revenue": Decimal(0)} for name in ("v1", "v2")}
rows = []
for user in selected_users:
    candidates = Random(
        stream_seed(26, f"ranking-gate/candidates/{user['id']}")
    ).sample(ads, 500)
    candidate_hash = fingerprint(candidates)
    context = {key: user[key] for key in ("id", "interests", "device", "age_group")}
    ranked = {
        "v1": InterestOverlap().rank(context, candidates),
        "v2": ExpectedValue(model).rank(context, candidates),
    }
    assert fingerprint(candidates) == candidate_hash
    assert all(
        {ad.ad_id for ad in result.candidates} == {ad["id"] for ad in candidates}
        for result in ranked.values()
    )
    outcome_user = OutcomeUser(**{key: user[key] for key in OutcomeUser.model_fields})
    by_id = {ad["id"]: ad for ad in candidates}
    decisions = {}
    for name, result in ranked.items():
        winner = result.candidates[0]
        ad = by_id[winner.ad_id]
        outcome_ad = OutcomeAd(**{key: ad[key] for key in OutcomeAd.model_fields})
        clicks = sum(
            world.sample(
                outcome_user, outcome_ad, opportunity=f"ticket26/{user['id']}/{index}"
            )
            for index in range(100)
        )
        revenue = winner.bid * clicks
        totals[name]["clicks"] += clicks
        totals[name]["simulated_revenue"] += revenue
        decisions[name] = {
            "winner": winner.model_dump(mode="json"),
            "strategy": result.strategy,
            "strategy_version": result.strategy_version,
            "score_meaning": result.score_meaning,
            "model_id": result.model_id,
            "model_version": result.model_version,
            "feature_version": result.feature_version,
            "sampled_impressions": 100,
            "sampled_clicks": clicks,
            "sampled_simulated_revenue": str(revenue),
        }
    rows.append(
        {
            "user_id": user["id"],
            "candidate_ids_in_input_order": [ad["id"] for ad in candidates],
            "candidate_context_sha256": candidate_hash,
            "decisions": decisions,
        }
    )
assert {str(path): checksum(path) for path in inputs} == before
summary = {}
for name, values in totals.items():
    summary[name] = {
        "sampled_impressions": 20000,
        "sampled_clicks": values["clicks"],
        "sampled_observed_ctr": values["clicks"] / 20000,
        "sampled_simulated_revenue": str(values["simulated_revenue"]),
        "sampled_simulated_revenue_per_impression": str(
            values["simulated_revenue"] / 20000
        ),
    }
report = {
    "passed": True,
    "python": platform.python_version(),
    "dataset_id": manifest["dataset_id"],
    "history_id": manifest["history_id"],
    "inputs_sha256": before,
    "inputs_unchanged": True,
    "model_id": rows[0]["decisions"]["v2"]["model_id"],
    "configuration": {
        "candidate_selection": "seeded uniform sample without replacement of 500 frozen eligible ads per user",
        "retrieval": "declared offline candidate pools; no FAISS or live retrieval invoked",
        "selection_seed": 26,
        "users": 200,
        "opportunities_per_user": 100,
        "outcome_version": "click-world-v1",
        "outcome_seed": manifest["configuration"]["seed"],
        "outcome_configuration": world.config.model_dump(mode="json"),
        "paired_draws": "same ticket26/user/opportunity uniform draw for both selected ads",
    },
    "same_selected_ad_users": sum(
        row["decisions"]["v1"]["winner"]["ad_id"]
        == row["decisions"]["v2"]["winner"]["ad_id"]
        for row in rows
    ),
    "summary": summary,
    "rows": rows,
    "limitations": [
        "Offline sampled synthetic outcomes, not live HTTP events or a randomized experiment.",
        "Repeated opportunities reuse each user's selected ad and are not independent users.",
        "Same frozen entity population and outcome assumptions as training; no unseen-population claim.",
        "No final-test tuning, raw-score averaging, causal lift, real-user revenue or performance claim.",
    ],
}
with output.open("x", encoding="utf-8") as stream:
    metadata = {key: value for key, value in report.items() if key != "rows"}
    prefix = json.dumps(metadata, sort_keys=True, indent=2, allow_nan=False)[
        :-1
    ].rstrip()
    stream.write(prefix + ',\n  "rows": [\n')
    stream.write(
        ",\n".join(
            "    " + json.dumps(row, sort_keys=True, allow_nan=False) for row in rows
        )
    )
    stream.write("\n  ]\n}\n")
print(
    json.dumps(
        {
            "passed": True,
            "same_selected_ad_users": report["same_selected_ad_users"],
            "summary": summary,
        }
    )
)
