"""Stream a saved history and verify hashes, source references and all labels."""

import argparse
import hashlib
import json
from datetime import datetime
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
clicks = 0
count = 0
last = None
with (args.directory / "exposures.jsonl").open() as stream:
    for count, line in enumerate(stream, start=1):
        row = json.loads(line)
        assert row["impression_id"] == count - 1
        assert row["user_id"] in users and row["ad_id"] in ads
        assert type(row["clicked"]) is int and row["clicked"] in (0, 1)
        when = datetime.fromisoformat(row["impressed_at"])
        assert last is None or when > last
        last = when
        assert (row["clicked_at"] is not None) == bool(row["clicked"])
        if row["clicked"]:
            assert datetime.fromisoformat(row["clicked_at"]) >= when
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
