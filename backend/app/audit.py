from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.models import DisputeRequest, DisputeResponse, ModelDraft


def audit_db_path() -> Path:
    # Railway can point this at a mounted volume later. Local dev uses a file in backend/.
    return Path(os.getenv("AUDIT_DB_PATH", "audit_log.sqlite3"))


def connect() -> sqlite3.Connection:
    path = audit_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_records (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            transaction_id TEXT NOT NULL,
            model_scenario TEXT,
            model_action TEXT,
            final_scenario TEXT NOT NULL,
            final_action TEXT NOT NULL,
            confidence REAL NOT NULL,
            rule_version TEXT NOT NULL,
            supervisor_overrides_json TEXT NOT NULL,
            signal_checks_json TEXT NOT NULL,
            redactions_json TEXT NOT NULL,
            request_json TEXT NOT NULL,
            response_json TEXT NOT NULL
        )
        """
    )
    return connection


def write_audit_record(
    request: DisputeRequest,
    response: DisputeResponse,
    draft: ModelDraft | None,
) -> str:
    audit_id = f"audit_{uuid.uuid4().hex[:12]}"
    response.audit_id = audit_id

    # Store JSON snapshots so a reviewer can reconstruct the exact decision record.
    request_json = request.model_dump_json()
    response_json = response.model_dump_json()
    signals_json = json.dumps([signal.model_dump() for signal in response.reasoning_trace.signal_checks])
    overrides_json = json.dumps(response.reasoning_trace.supervisor_overrides)
    redactions_json = json.dumps(response.redactions)

    with connect() as connection:
        connection.execute(
            """
            INSERT INTO audit_records (
                id,
                created_at,
                customer_id,
                transaction_id,
                model_scenario,
                model_action,
                final_scenario,
                final_action,
                confidence,
                rule_version,
                supervisor_overrides_json,
                signal_checks_json,
                redactions_json,
                request_json,
                response_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                audit_id,
                datetime.now(UTC).isoformat(),
                request.case_context.customer_id,
                request.case_context.transaction.id,
                draft.scenario.value if draft else None,
                draft.recommended_action.value if draft else None,
                response.scenario.value,
                response.recommended_action.value,
                response.reasoning_trace.confidence,
                response.reasoning_trace.rule_version,
                overrides_json,
                signals_json,
                redactions_json,
                request_json,
                response_json,
            ),
        )

    return audit_id
