from __future__ import annotations

import re

from app.models import (
    CaseContext,
    ChatMessage,
    HandoffPayload,
    ModelDraft,
    ReasoningTrace,
    RecommendedAction,
    Scenario,
)
from app.signals import evaluate_signals


DENIED_AUTHORIZATION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bdid\s*not\s+authorize\b",
        r"\bdidn['’]?t\s+authorize\b",
        r"\bnever\s+authorized\b",
        r"\bnot\s+authorized\b",
        r"\bwasn['’]?t\s+me\b",
        r"\bnot\s+normal\b",
        r"\bdon['’]?t\s+recognize\b",
        r"\bdo\s+not\s+recognize\b",
    ]
]

CUSTOMER_REVIEW_REQUEST_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bescalate\b",
        r"\bhuman\b",
        r"\bspecialist\b",
        r"\brepresentative\b",
        r"\bagent\b",
        r"\breopen\b",
        r"\bopen\s+(?:the\s+)?review\b",
        r"\bopen\s+(?:a\s+)?case\b",
        r"\bfile\s+(?:a\s+)?dispute\b",
        r"\bdispute\s+(?:this\s+)?charge\b",
        r"\bcontinue\s+(?:the\s+)?review\b",
    ]
]

REOPEN_OFFER_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\breopen\s+(?:the\s+)?review\b",
        r"\bwithout\s+escalation\b",
    ]
]

UNAUTHORIZED_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bunauthorized\b",
        r"\bdid\s*not\s+authorize\b",
        r"\bdidn['’]?t\s+authorize\b",
        r"\bwasn['’]?t\s+me\b",
    ]
]


def confidence_from_signals(risk_score: int, legitimacy_score: int) -> float:
    total = min(0.98, 0.52 + (abs(risk_score - legitimacy_score) * 0.08))
    return round(total, 2)


def customer_denied_after_clarification(transcript: list[ChatMessage]) -> bool:
    user_messages = [message.content for message in transcript if message.role.value == "user"]
    if len(user_messages) < 2:
        return False

    combined = " ".join(user_messages[-3:])
    return any(pattern.search(combined) for pattern in DENIED_AUTHORIZATION_PATTERNS)


def customer_requested_review(transcript: list[ChatMessage]) -> bool:
    user_messages = [message.content for message in transcript if message.role.value == "user"]
    if not user_messages:
        return False

    latest_user_message = user_messages[-1]
    if any(pattern.search(latest_user_message) for pattern in CUSTOMER_REVIEW_REQUEST_PATTERNS):
        return True

    assistant_context = " ".join(
        message.content for message in transcript[-4:] if message.role.value == "assistant"
    )
    accepted_reopen_offer = any(pattern.search(latest_user_message) for pattern in UNAUTHORIZED_PATTERNS)
    offered_reopen = any(pattern.search(assistant_context) for pattern in REOPEN_OFFER_PATTERNS)

    return accepted_reopen_offer and offered_reopen


def supervise_decision(
    draft: ModelDraft,
    context: CaseContext,
    transcript: list[ChatMessage],
) -> tuple[Scenario, RecommendedAction, str, ReasoningTrace, HandoffPayload | None]:
    signals = evaluate_signals(context)
    risk_score = sum(signal.weight for signal in signals if signal.weight > 0)
    legitimacy_score = abs(sum(signal.weight for signal in signals if signal.weight < 0))
    signal_by_id = {signal.id: signal for signal in signals}
    overrides: list[str] = []

    scenario = draft.scenario
    action = draft.recommended_action
    reply = draft.customer_reply

    if signal_by_id["lost_or_stolen_card"].fired:
        scenario = Scenario.likely_fraud
        action = RecommendedAction.escalate
        overrides.append("Lost or stolen card report forces human escalation.")
    elif risk_score >= 5 and not signal_by_id["merchant_match"].status == "match":
        scenario = Scenario.likely_fraud
        action = RecommendedAction.escalate
        overrides.append("Multiple explicit transaction risk signals force escalation.")
    elif signal_by_id["merchant_match"].status == "match" and risk_score <= 1:
        scenario = Scenario.straightforward
        action = RecommendedAction.resolve
        if draft.recommended_action != RecommendedAction.resolve:
            overrides.append("Strong legitimate merchant match with no material risk signal allows resolution.")
    elif signal_by_id["merchant_match"].status == "partial" or risk_score < 5:
        scenario = Scenario.ambiguous
        action = RecommendedAction.ask_clarifying_question
        if draft.recommended_action == RecommendedAction.escalate:
            overrides.append("Unfamiliar or partially matched merchant alone is not enough to escalate.")

    if (
        scenario == Scenario.ambiguous
        and signal_by_id["merchant_match"].status == "partial"
        and customer_denied_after_clarification(transcript)
    ):
        scenario = Scenario.likely_fraud
        action = RecommendedAction.escalate
        overrides.append("Customer denied authorizing the changed recurring charge after clarification.")

    if customer_requested_review(transcript):
        scenario = Scenario.likely_fraud
        action = RecommendedAction.escalate
        overrides.append("Customer explicitly requested human review or reopened the dispute.")

    confidence = confidence_from_signals(risk_score, legitimacy_score)

    if action == RecommendedAction.escalate:
        if "Customer explicitly requested human review or reopened the dispute." in overrides:
            reply = (
                "Understood. I am opening the review and sending this dispute to a specialist with the transaction "
                "details, signal checks, and this transcript."
            )
        else:
            reply = (
                "Thanks for clarifying. I am escalating this dispute to a specialist and sending the transaction "
                "details, signal checks, and this transcript with it."
            )
    elif action == RecommendedAction.ask_clarifying_question:
        questions = draft.clarifying_questions or [
            "Do you recognize this merchant by another name, or did anyone else authorized on the account make this purchase?"
        ]
        reply = f"To continue the review, please answer this: {questions[0]}"
    elif action == RecommendedAction.resolve:
        reply = (
            f"This {context.transaction.currency} {context.transaction.amount:.2f} charge from "
            f"{context.transaction.merchant_name} matches your known transaction history, so I can resolve it "
            "without escalation. If you still believe it was unauthorized, I can reopen the review."
        )

    trace = ReasoningTrace(
        decision=scenario,
        recommended_action=action,
        model_scenario=draft.scenario,
        model_recommended_action=draft.recommended_action,
        signal_checks=signals,
        confidence=confidence,
        model_rationale=draft.rationale,
        supervisor_overrides=overrides,
    )

    handoff = None
    if action == RecommendedAction.escalate:
        handoff = HandoffPayload(
            transaction=context.transaction,
            signal_analysis=signals,
            confidence=confidence,
            transcript=transcript,
            summary=(
                f"Escalated {context.transaction.merchant_name} charge for ${context.transaction.amount:.2f}. "
                f"Risk score {risk_score}; legitimacy score {legitimacy_score}. "
                f"Reason: {overrides[-1] if overrides else 'Supervisor selected escalation.'}"
            ),
        )

    return scenario, action, reply, trace, handoff
