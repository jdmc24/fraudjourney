import sqlite3
import json

from fastapi.testclient import TestClient

from app.main import app
from app.models import RecommendedAction, Scenario


def request_payload():
    return {
        "message": "I do not recognize this Netflix charge.",
        "history": [],
        "case_context": {
            "customer_id": "cust_test",
            "account_currency": "USD",
            "home_country": "US",
            "transaction": {
                "id": "txn_test",
                "merchant_name": "Netflix",
                "merchant_category": "streaming",
                "amount": 15.99,
                "currency": "USD",
                "date": "2026-07-06",
                "country": "US",
                "recurring": True,
            },
            "known_merchants": [
                {
                    "merchant_name": "Netflix",
                    "aliases": ["Netflix.com"],
                    "typical_amount": 15.99,
                    "recurring": True,
                }
            ],
            "recent_charges": [],
            "card_status": {"lost_or_stolen_reported": False},
        },
    }


def test_fail_closed_path_writes_audit_record(monkeypatch, tmp_path):
    audit_path = tmp_path / "audit.sqlite3"
    monkeypatch.setenv("AUDIT_DB_PATH", str(audit_path))

    def broken_model(*_args, **_kwargs):
        raise RuntimeError("simulated model outage")

    # Patch the FastAPI module's imported function so the API path exercises fail-closed behavior.
    monkeypatch.setattr("app.main.propose_decision", broken_model)

    response = TestClient(app).post("/api/dispute", json=request_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["scenario"] == Scenario.likely_fraud.value
    assert body["recommended_action"] == RecommendedAction.escalate.value
    assert body["handoff_payload"] is not None
    assert body["audit_id"].startswith("audit_")

    with sqlite3.connect(audit_path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM audit_records").fetchone()[0]
        response_json = connection.execute("SELECT response_json FROM audit_records").fetchone()[0]

    assert count == 1
    assert json.loads(response_json)["audit_id"] == body["audit_id"]
