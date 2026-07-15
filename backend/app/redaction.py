from __future__ import annotations

import re
from dataclasses import dataclass

from app.models import ChatMessage, DisputeRequest, Role


@dataclass(frozen=True)
class RedactionResult:
    text: str
    labels: list[str]


@dataclass(frozen=True)
class RedactedDisputeRequest:
    request: DisputeRequest
    labels: list[str]
    transcript: list[ChatMessage]


PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("card_number", re.compile(r"\b(?:\d[ -]*?){13,19}\b")),
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("account_number", re.compile(r"\b(?:acct|account)\s*#?\s*\d{6,17}\b", re.IGNORECASE)),
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("phone", re.compile(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b")),
]


def redact_text(text: str) -> RedactionResult:
    labels: list[str] = []
    redacted = text

    for label, pattern in PATTERNS:
        if pattern.search(redacted):
            labels.append(label)
            redacted = pattern.sub(f"[REDACTED_{label.upper()}]", redacted)

    return RedactionResult(text=redacted, labels=labels)


def redact_dispute_request(request: DisputeRequest) -> RedactedDisputeRequest:
    redacted_message = redact_text(request.message)
    labels = set(redacted_message.labels)
    redacted_history: list[ChatMessage] = []

    for item in request.history:
        result = redact_text(item.content)
        labels.update(result.labels)
        redacted_history.append(ChatMessage(role=item.role, content=result.text))

    safe_request = DisputeRequest(
        message=redacted_message.text,
        history=redacted_history,
        case_context=request.case_context,
    )
    transcript = [
        *safe_request.history,
        ChatMessage(role=Role.user, content=safe_request.message),
    ]

    return RedactedDisputeRequest(
        request=safe_request,
        labels=sorted(labels),
        transcript=transcript,
    )
