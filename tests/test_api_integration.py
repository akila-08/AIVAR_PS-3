"""
End-to-end API tests against a real Supabase project.

Unlike the DynamoDB version, Supabase (hosted Postgres) has no equivalent
to moto's in-memory mock, so these tests run against a REAL Supabase
project's REST API. Point them at a disposable/dev project, never
production — every test below writes real rows.

Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY to be set, and the
three schema.sql tables (policies, audit_log, reviews) to already exist,
seeded with the same policies scripts/seed_policies.py loads.

Run with:
    export SUPABASE_URL=https://xxxx.supabase.co
    export SUPABASE_SERVICE_ROLE_KEY=eyJ...
    python -m pytest tests/test_api_integration.py -v
"""
import datetime
import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SERVICE_ROLE_KEY"),
    reason="SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set — skipping live Supabase integration tests",
)


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.supabase import get_client

    # Make sure the 3 expected policies exist before running (idempotent).
    get_client().table("policies").upsert(
        [
            {"rule_id": "01-block-bulk-delete", "tool": "db_delete", "condition": "record_count > 100", "action": "block", "reason": "Bulk delete exceeds safe threshold"},
            {"rule_id": "02-hitl-external-email", "tool": "send_email", "condition": "to_domain != 'internal.company.com'", "action": "require_hitl", "reason": "External domain requires review"},
            {"rule_id": "03-log-confidential-read", "tool": "read_file", "condition": "'confidential' in path", "action": "log_and_allow", "reason": "Confidential path access"},
        ]
    ).execute()

    return TestClient(app)


def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["supabase"] is True


def test_bulk_delete_blocked_end_to_end(client):
    resp = client.post("/guardrail/evaluate", json={"tool": "db_delete", "params": {"record_count": 500}})
    assert resp.status_code == 200
    body = resp.json()
    assert body["outcome"] == "block"
    assert body["matched_rule_id"] == "01-block-bulk-delete"


def test_small_delete_allowed_end_to_end(client):
    resp = client.post("/guardrail/evaluate", json={"tool": "db_delete", "params": {"record_count": 5}})
    assert resp.json()["outcome"] == "log_and_allow"


def test_external_email_creates_pending_review(client):
    resp = client.post("/guardrail/evaluate", json={"tool": "send_email", "params": {"to_domain": "partner.com"}})
    body = resp.json()
    assert body["outcome"] == "require_hitl"
    assert body["review_id"] is not None

    review_id = body["review_id"]
    approve_resp = client.post(f"/guardrail/reviews/{review_id}/approve")
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"

    # Second approval attempt on the same review must fail (race-safety)
    second_attempt = client.post(f"/guardrail/reviews/{review_id}/approve")
    assert second_attempt.status_code == 404


def test_internal_email_allowed_end_to_end(client):
    resp = client.post("/guardrail/evaluate", json={"tool": "send_email", "params": {"to_domain": "internal.company.com"}})
    assert resp.json()["outcome"] == "log_and_allow"


def test_audit_log_captures_evaluated_actions(client):
    client.post("/guardrail/evaluate", json={"tool": "db_delete", "params": {"record_count": 500}})
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    resp = client.get(f"/guardrail/audit?date={today}")
    assert resp.status_code == 200
    records = resp.json()
    assert len(records) >= 1
    assert records[0]["outcome"] == "block"
    assert records[0]["matched_rule"] == "01-block-bulk-delete"


def test_bad_payload_returns_422_not_500(client):
    resp = client.post("/guardrail/evaluate", json={"params": {"record_count": 500}})  # missing "tool"
    assert resp.status_code == 422

