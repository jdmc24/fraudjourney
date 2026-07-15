from __future__ import annotations

from dataclasses import dataclass

from app.models import (
    CardStatus,
    CaseContext,
    ChatMessage,
    EvaluationResult,
    KnownMerchant,
    ModelDraft,
    RecommendedAction,
    RecentCharge,
    Role,
    Scenario,
    Transaction,
)
from app.redaction import redact_text
from app.supervisor import supervise_decision


@dataclass(frozen=True)
class EvaluationCase:
    id: str
    name: str
    message: str
    context: CaseContext
    draft: ModelDraft
    expected_scenario: Scenario
    expected_action: RecommendedAction
    note: str


def evaluation_cases() -> list[EvaluationCase]:
    return [
        EvaluationCase(
            id="known_merchant_model_too_cautious",
            name="Known merchant, model too cautious",
            message="I do not recognize this Netflix charge. My card is 4111 1111 1111 1111.",
            context=CaseContext(
                customer_id="eval_known",
                transaction=Transaction(
                    id="eval_txn_known",
                    merchant_name="Netflix",
                    merchant_category="streaming",
                    amount=15.99,
                    date="2026-07-06",
                    recurring=True,
                ),
                known_merchants=[
                    KnownMerchant(
                        merchant_name="Netflix",
                        aliases=["Netflix.com"],
                        typical_amount=15.99,
                        recurring=True,
                    )
                ],
            ),
            draft=ModelDraft(
                scenario=Scenario.ambiguous,
                recommended_action=RecommendedAction.ask_clarifying_question,
                customer_reply="I need one more detail before deciding.",
                rationale="Controlled bad draft for eval.",
            ),
            expected_scenario=Scenario.straightforward,
            expected_action=RecommendedAction.resolve,
            note="Supervisor should override caution because the charge strongly matches legitimate context.",
        ),
        EvaluationCase(
            id="lost_card_model_under_escalates",
            name="Lost card, model under-escalates",
            message="My wallet went missing and I see an ATM charge.",
            context=CaseContext(
                customer_id="eval_lost",
                transaction=Transaction(
                    id="eval_txn_lost",
                    merchant_name="ATM Centro MX",
                    merchant_category="atm",
                    amount=420,
                    currency="MXN",
                    date="2026-07-06",
                    country="MX",
                ),
                known_merchants=[],
                recent_charges=[
                    RecentCharge(merchant_name="ATM Centro MX", amount=420, currency="MXN", date="2026-07-06", country="MX")
                ],
                card_status=CardStatus(lost_or_stolen_reported=True, reported_at="2026-07-06T14:12:00Z"),
            ),
            draft=ModelDraft(
                scenario=Scenario.ambiguous,
                recommended_action=RecommendedAction.ask_clarifying_question,
                customer_reply="Can you confirm whether you made this withdrawal?",
                rationale="Controlled bad draft for eval.",
            ),
            expected_scenario=Scenario.likely_fraud,
            expected_action=RecommendedAction.escalate,
            note="Lost or stolen card report should force escalation.",
        ),
        EvaluationCase(
            id="price_change_model_over_escalates",
            name="Subscription price change",
            message="This FitPlus subscription is higher than usual.",
            context=CaseContext(
                customer_id="eval_price",
                transaction=Transaction(
                    id="eval_txn_price",
                    merchant_name="FitPlus",
                    merchant_category="fitness",
                    amount=29.99,
                    date="2026-07-05",
                    recurring=True,
                ),
                known_merchants=[
                    KnownMerchant(
                        merchant_name="FitPlus",
                        aliases=["FitPlus Monthly"],
                        typical_amount=9.99,
                        recurring=True,
                    )
                ],
            ),
            draft=ModelDraft(
                scenario=Scenario.likely_fraud,
                recommended_action=RecommendedAction.escalate,
                customer_reply="I am escalating this.",
                rationale="Controlled bad draft for eval.",
            ),
            expected_scenario=Scenario.ambiguous,
            expected_action=RecommendedAction.ask_clarifying_question,
            note="Partial legitimate match with changed amount should clarify instead of escalating.",
        ),
        EvaluationCase(
            id="unknown_merchant_no_risk",
            name="Unknown merchant, no risk signal",
            message="I do not recognize this bookstore charge.",
            context=CaseContext(
                customer_id="eval_unknown",
                transaction=Transaction(
                    id="eval_txn_unknown",
                    merchant_name="Northside Books",
                    merchant_category="bookstore",
                    amount=42.1,
                    date="2026-07-06",
                ),
                known_merchants=[],
            ),
            draft=ModelDraft(
                scenario=Scenario.likely_fraud,
                recommended_action=RecommendedAction.escalate,
                customer_reply="I am escalating this.",
                rationale="Controlled bad draft for eval.",
            ),
            expected_scenario=Scenario.ambiguous,
            expected_action=RecommendedAction.ask_clarifying_question,
            note="Novelty alone should produce clarification, not escalation.",
        ),
    ]


def run_evaluations() -> list[EvaluationResult]:
    results: list[EvaluationResult] = []

    for case in evaluation_cases():
        redacted_message = redact_text(case.message)
        transcript = [ChatMessage(role=Role.user, content=redacted_message.text)]
        scenario, action, _, trace, handoff = supervise_decision(case.draft, case.context, transcript)
        passed = scenario == case.expected_scenario and action == case.expected_action

        results.append(
            EvaluationResult(
                id=case.id,
                name=case.name,
                expected_scenario=case.expected_scenario,
                actual_scenario=scenario,
                expected_action=case.expected_action,
                actual_action=action,
                passed=passed,
                guardrail_fired=len(trace.supervisor_overrides) > 0,
                handoff_complete=handoff is None or len(handoff.transcript) > 0,
                pii_redacted="card_number" in redacted_message.labels if case.id == "known_merchant_model_too_cautious" else True,
                supervisor_overrides=trace.supervisor_overrides,
                note=case.note,
            )
        )

    return results
