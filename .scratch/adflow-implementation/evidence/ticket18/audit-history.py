"""Stream a saved history and verify hashes, source references and all labels."""

import argparse
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("directory", type=Path)
args = parser.parse_args()
manifest = json.loads((args.directory / "manifest.json").read_text())
for filename, expected in manifest["files"].items():
    digest = hashlib.sha256()
    with (args.directory / filename).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    assert digest.hexdigest() == expected
users = {
    row["id"]
    for row in map(
        json.loads, (args.directory / "users.jsonl").read_text().splitlines()
    )
}
ads = {
    row["id"]
    for row in map(json.loads, (args.directory / "ads.jsonl").read_text().splitlines())
}
with (args.directory / "ads.jsonl").open() as stream:
    for line in stream:
        ad = json.loads(line)
        assert ad["active"] and ad["advertiser_active"]
        assert ad["dataset_id"] == manifest["dataset_id"]
clicks = 0
count = 0
last = None
start = datetime.fromisoformat(
    manifest["configuration"]["start"].replace("Z", "+00:00")
)
with (args.directory / "exposures.jsonl").open() as stream:
    for count, line in enumerate(stream, start=1):
        row = json.loads(line)
        assert row["impression_id"] == count - 1
        assert row["user_id"] in users and row["ad_id"] in ads
        assert type(row["clicked"]) is int and row["clicked"] in (0, 1)
        when = datetime.fromisoformat(row["impressed_at"])
        assert when == start + timedelta(
            seconds=(count - 1) * manifest["configuration"]["interval_seconds"]
        )
        assert last is None or when > last
        last = when
        assert (row["clicked_at"] is not None) == bool(row["clicked"])
        if row["clicked"]:
            delay = (datetime.fromisoformat(row["clicked_at"]) - when).total_seconds()
            assert 1 <= delay <= manifest["configuration"]["max_click_delay_seconds"]
        assert set(row) == {
            "impression_id",
            "user_id",
            "ad_id",
            "impressed_at",
            "clicked",
            "clicked_at",
        }
        clicks += row["clicked"]
assert count == manifest["counts"]["impressions"]
assert clicks == manifest["counts"]["clicks"]
assert len(users) == manifest["counts"]["users"]
assert len(ads) == manifest["counts"]["eligible_ads"]
print(
    json.dumps(
        {
            "directory": str(args.directory),
            "history_id": manifest["history_id"],
            "impressions": count,
            "clicks": clicks,
            "hashes_and_all_rows_valid": True,
        },
        indent=2,
    )
)
