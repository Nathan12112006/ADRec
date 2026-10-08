"""Ticket 10 manual gate: run against the prepared adflow-ticket10 Compose project.

From the repository root: backend/.venv/Scripts/python.exe
.scratch/adflow-implementation/evidence/phase-one-gate.py
Requires fresh default-seeded data, port 8000, and Docker access. Retains all data.
Stops/restores only this verification project's services and its own local API process.
"""

import json
import os
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
COMPOSE = ["docker", "compose", "-p", "adflow-ticket10"]
API = "http://127.0.0.1:8000"


def compose(*args):
    return subprocess.check_output(COMPOSE + list(args), cwd=ROOT, text=True).strip()


def sql(query):
    return compose(
        "exec", "-T", "postgres", "psql", "-U", "adflow", "-d", "adflow", "-Atc", query
    )


def counts():
    return sql(
        "SELECT (SELECT count(*) FROM users), (SELECT count(*) FROM advertisers), "
        "(SELECT count(*) FROM ads), (SELECT count(*) FROM request_outcomes), "
        "(SELECT count(*) FROM recommendations), (SELECT count(*) FROM events), "
        "(SELECT coalesce(sum(simulated_revenue),0) FROM events)"
    )


def http(path, body=None, key=None, expected=200):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Idempotency-Key"] = key
    request = Request(
        API + path,
        headers=headers,
        data=None if body is None else json.dumps(body).encode(),
    )
    try:
        response = urlopen(request, timeout=10)
    except HTTPError as error:
        response = error
    with response:
        payload = json.loads(response.read())
        assert response.status == expected, (path, response.status, payload)
        return payload


def healthy():
    http("/health/live")
    http("/health/ready")
    assert "/api/v1/recommendations" in http("/openapi.json")["paths"]


def lifecycle(mode):
    healthy()
    key = str(uuid4())
    body = {"user_id": int(sql("SELECT id FROM users ORDER BY id LIMIT 1"))}
    recommendation = http("/api/v1/recommendations", body, key)
    assert recommendation == http("/api/v1/recommendations", body, key)
    assert recommendation["selection"]["predicted_ctr"] is None
    event = {"recommendation_id": recommendation["recommendation_id"]}
    http("/api/v1/events/click", event, expected=409)
    impression = http("/api/v1/events/impression", event)
    assert impression == http("/api/v1/events/impression", event)
    click = http("/api/v1/events/click", event)
    assert click == http("/api/v1/events/click", event)
    assert click["simulated_revenue"] == recommendation["selection"]["bid"]
    aggregate = sql(
        "SELECT event_type, count(*), sum(simulated_revenue) FROM events "
        f"WHERE recommendation_id = '{event['recommendation_id']}' "
        "GROUP BY event_type ORDER BY event_type"
    )
    assert aggregate == "click|1|4.9900\nimpression|1|0.0000", aggregate
    print(
        json.dumps(
            {
                "mode": mode,
                "recommendation_id": event["recommendation_id"],
                "key": key,
                "bid": click["simulated_revenue"],
                "events": aggregate,
                "counts": counts(),
            }
        ),
        flush=True,
    )
    return recommendation, body, key


assert counts() == "100|20|1000|0|0|0|0", counts()
saved, user, saved_key = lifecycle("docker")
assert counts() == "100|20|1000|1|1|2|4.9900", counts()
compose("stop", "postgres")
try:
    http("/health/live")
    http("/health/ready", expected=503)
    http("/api/v1/recommendations", user, str(uuid4()), expected=503)
    print("Database outage: live 200, ready 503, recommendation 503", flush=True)
finally:
    compose("up", "-d", "--wait", "postgres")
healthy()
compose("stop", "backend")
environment = dict(
    os.environ,
    ADFLOW_DATABASE_URL="postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow",
    ADFLOW_TEST_DATABASE_URL="postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_test",
)
try:
    with (ROOT / ".uv-cache/ticket10-local.log").open("w") as log:
        process = subprocess.Popen(
            [
                str(ROOT / "backend/.venv/Scripts/python.exe"),
                "-m",
                "uvicorn",
                "app.main:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            cwd=ROOT / "backend",
            env=environment,
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            deadline = time.monotonic() + 30
            while True:
                try:
                    healthy()
                    break
                except (URLError, AssertionError):
                    assert process.poll() is None and time.monotonic() < deadline
                    time.sleep(0.2)
            assert saved == http("/api/v1/recommendations", user, saved_key)
            lifecycle("local")
        finally:
            process.terminate()
            process.wait(timeout=10)
finally:
    compose("up", "-d", "--wait", "backend")
expected_counts = "100|20|1000|2|2|4|9.9800"
assert counts() == expected_counts, counts()
compose("down")
compose("up", "-d", "--wait")
healthy()
assert saved == http("/api/v1/recommendations", user, saved_key)
assert counts() == expected_counts, counts()
print("Restart/replay durable counts: " + counts(), flush=True)
