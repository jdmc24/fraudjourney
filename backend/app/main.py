from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent import propose_decision
from app.audit import write_audit_record
from app.evaluations import run_evaluations
from app.models import (
    ChatMessage,
    DisputeRequest,
    DisputeResponse,
    EvaluationResult,
    HandoffPayload,
    ReasoningTrace,
    RecommendedAction,
    Scenario,
)
from app.redaction import redact_dispute_request
from app.signals import evaluate_signals
from app.supervisor import supervise_decision


load_dotenv()

app = FastAPI(title="Fraud Dispute Agent", version="0.1.0")


def allowed_origins() -> list[str]:
    raw_origins = os.getenv("ALLOWED_ORIGINS", "http://127.0.0.1:3000,http://localhost:3000")
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> dict[str, object]:
    return {
        "service": "Fraud Dispute Agent API",
        "status": "ok",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "dispute": "/api/dispute",
            "evaluations": "/api/evaluations",
        },
    }


@app.get("/api/evaluations", response_model=list[EvaluationResult])
def evaluations() -> list[EvaluationResult]:
    return run_evaluations()


def fail_closed_response(
    request: DisputeRequest,
    transcript: list[ChatMessage],
    redactions: list[str],
    reason: str,
) -> DisputeResponse:
    signals = evaluate_signals(request.case_context)
    trace = ReasoningTrace(
        decision=Scenario.likely_fraud,
        recommended_action=RecommendedAction.escalate,
        signal_checks=signals,
        confidence=0.0,
        model_rationale=f"Model layer did not return a usable proposal: {reason}",
        supervisor_overrides=["Model or backend failure forced the fail-closed escalation path."],
    )
    handoff = HandoffPayload(
        transaction=request.case_context.transaction,
        signal_analysis=signals,
        confidence=0.0,
        transcript=transcript,
        summary=(
            f"Fail-closed escalation for {request.case_context.transaction.merchant_name}. "
            "The automated decision path did not complete, so the case requires human review."
        ),
    )
    return DisputeResponse(
        scenario=Scenario.likely_fraud,
        recommended_action=RecommendedAction.escalate,
        reply=(
            "I cannot complete the automated review safely right now. "
            "I am escalating this dispute to a specialist with the transaction details and this conversation."
        ),
        reasoning_trace=trace,
        handoff_payload=handoff,
        redactions=redactions,
    )


@app.post("/api/dispute", response_model=DisputeResponse)
def dispute(request: DisputeRequest) -> DisputeResponse:
    redacted = redact_dispute_request(request)
    safe_request = redacted.request

    try:
        draft = propose_decision(
            safe_request.message,
            safe_request.history,
            safe_request.case_context,
        )
    except Exception as exc:
        response = fail_closed_response(
            request=safe_request,
            transcript=redacted.transcript,
            redactions=redacted.labels,
            reason=str(exc),
        )
        write_audit_record(safe_request, response, draft=None)
        return response

    scenario, action, reply, trace, handoff = supervise_decision(
        draft=draft,
        context=safe_request.case_context,
        transcript=redacted.transcript,
    )

    response = DisputeResponse(
        scenario=scenario,
        recommended_action=action,
        reply=reply,
        reasoning_trace=trace,
        handoff_payload=handoff,
        redactions=redacted.labels,
    )
    write_audit_record(safe_request, response, draft=draft)
    return response
