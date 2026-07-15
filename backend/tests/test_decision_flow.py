from app.models import CardStatus, CaseContext, ChatMessage, KnownMerchant, ModelDraft, RecommendedAction, Role, Scenario, Transaction
from app.redaction import redact_text
from app.supervisor import supervise_decision


def base_context(**overrides):
    data = {
        "transaction": Transaction(
            id="txn_1",
            merchant_name="Netflix",
            merchant_category="streaming",
            amount=15.99,
            currency="USD",
            date="2026-07-06",
            country="US",
            recurring=True,
        ),
        "known_merchants": [
            KnownMerchant(merchant_name="Netflix", aliases=["Netflix.com"], typical_amount=15.99, recurring=True)
        ],
    }
    data.update(overrides)
    return CaseContext(**data)


def draft(action=RecommendedAction.ask_clarifying_question):
    return ModelDraft(
        scenario=Scenario.ambiguous,
        recommended_action=action,
        customer_reply="Let me check that.",
        rationale="Test draft",
    )


def test_redacts_card_and_ssn():
    result = redact_text("My card is 4111 1111 1111 1111 and SSN is 123-45-6789")
    assert "4111" not in result.text
    assert "123-45-6789" not in result.text
    assert set(result.labels) == {"card_number", "ssn"}


def test_strong_known_merchant_resolves_even_if_model_is_unsure():
    scenario, action, _, trace, handoff = supervise_decision(draft(), base_context(), [])
    assert scenario == Scenario.straightforward
    assert action == RecommendedAction.resolve
    assert trace.supervisor_overrides
    assert handoff is None


def test_customer_can_reopen_review_after_known_merchant_resolution():
    transcript = [
        ChatMessage(role=Role.user, content="I do not recognize this Netflix charge."),
        ChatMessage(
            role=Role.assistant,
            content=(
                "This USD 15.99 charge from Netflix matches your known transaction history, so I can resolve it "
                "without escalation. If you still believe it was unauthorized, I can reopen the review."
            ),
        ),
        ChatMessage(role=Role.user, content="yes go ahead and open the review please"),
    ]

    scenario, action, reply, trace, handoff = supervise_decision(draft(), base_context(), transcript)

    assert scenario == Scenario.likely_fraud
    assert action == RecommendedAction.escalate
    assert "opening the review" in reply.lower()
    assert trace.supervisor_overrides[-1] == "Customer explicitly requested human review or reopened the dispute."
    assert handoff is not None


def test_customer_unauthorized_reply_accepts_reopen_offer():
    transcript = [
        ChatMessage(role=Role.user, content="I do not recognize this Netflix charge."),
        ChatMessage(
            role=Role.assistant,
            content=(
                "This USD 15.99 charge from Netflix matches your known transaction history, so I can resolve it "
                "without escalation. If you still believe it was unauthorized, I can reopen the review."
            ),
        ),
        ChatMessage(role=Role.user, content="yes it was unauthorized"),
    ]

    scenario, action, _, trace, handoff = supervise_decision(draft(), base_context(), transcript)

    assert scenario == Scenario.likely_fraud
    assert action == RecommendedAction.escalate
    assert trace.supervisor_overrides[-1] == "Customer explicitly requested human review or reopened the dispute."
    assert handoff is not None


def test_lost_or_stolen_card_forces_escalation():
    context = base_context(card_status=CardStatus(lost_or_stolen_reported=True))
    scenario, action, _, trace, handoff = supervise_decision(draft(RecommendedAction.resolve), context, [])
    assert scenario == Scenario.likely_fraud
    assert action == RecommendedAction.escalate
    assert "lost or stolen" in trace.supervisor_overrides[0].lower()
    assert handoff is not None


def test_partial_merchant_match_is_ambiguous_not_fraud():
    context = base_context(
        transaction=Transaction(
            id="txn_2",
            merchant_name="Netflix",
            merchant_category="streaming",
            amount=29.99,
            currency="USD",
            date="2026-07-06",
            country="US",
            recurring=True,
        )
    )
    scenario, action, _, trace, handoff = supervise_decision(draft(RecommendedAction.escalate), context, [])
    assert scenario == Scenario.ambiguous
    assert action == RecommendedAction.ask_clarifying_question
    assert handoff is None
    assert any(signal.id == "merchant_match" and signal.status == "partial" for signal in trace.signal_checks)


def test_partial_match_escalates_after_customer_denies_authorization():
    context = base_context(
        transaction=Transaction(
            id="txn_3",
            merchant_name="Netflix",
            merchant_category="streaming",
            amount=29.99,
            currency="USD",
            date="2026-07-06",
            country="US",
            recurring=True,
        )
    )
    transcript = [
        ChatMessage(role=Role.user, content="This charge is higher than normal."),
        ChatMessage(role=Role.assistant, content="Can you confirm whether this was a plan change?"),
        ChatMessage(role=Role.user, content="No, I did not authorize the higher charge."),
    ]

    scenario, action, reply, trace, handoff = supervise_decision(draft(), context, transcript)

    assert scenario == Scenario.likely_fraud
    assert action == RecommendedAction.escalate
    assert "one more detail" not in reply.lower()
    assert trace.supervisor_overrides == ["Customer denied authorizing the changed recurring charge after clarification."]
    assert handoff is not None
