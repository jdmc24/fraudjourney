from __future__ import annotations

import os

from openai import OpenAI

from app.models import CaseContext, ChatMessage, ModelDraft, RecommendedAction, Scenario


SYSTEM_PROMPT = """You are the primary language model layer for a regulated fraud dispute agent.

Your job is to parse the customer's message and propose a scenario decision. A rule-based supervisor will make the final decision after your proposal.

The three scenarios are:
1. scenario_1_straightforward: strong positive match to legitimate transaction context.
2. scenario_2_ambiguous: no strong match either way, so ask a clarifying question.
3. scenario_3_likely_fraud: explicit transaction risk signals suggest escalation.

Important policy:
- Do not use the customer's dispute history or personal behavior as a risk signal.
- Unfamiliar merchant alone is ambiguous, not likely fraud.
- A partial merchant match with a different amount is ambiguous, not likely fraud.
- If there is a lost or stolen card report, propose escalation.
- Keep the customer reply calm, concise, and practical.
"""


def compact_context(context: CaseContext) -> dict:
    return {
        "account_currency": context.account_currency,
        "home_country": context.home_country,
        "transaction": context.transaction.model_dump(),
        "known_merchants": [merchant.model_dump() for merchant in context.known_merchants],
        "recent_charges": [charge.model_dump() for charge in context.recent_charges],
        "card_status": context.card_status.model_dump(),
    }


def fallback_draft(context: CaseContext) -> ModelDraft:
    if context.card_status.lost_or_stolen_reported:
        return ModelDraft(
            scenario=Scenario.likely_fraud,
            recommended_action=RecommendedAction.escalate,
            customer_reply="I am going to get this to a specialist for review.",
            rationale="Fallback draft selected escalation because the card is marked lost or stolen.",
        )

    return ModelDraft(
        scenario=Scenario.ambiguous,
        recommended_action=RecommendedAction.ask_clarifying_question,
        customer_reply="I need one more detail before I can resolve this safely.",
        rationale="Fallback draft used because OpenAI fallback mode is enabled.",
        clarifying_questions=[
            "Do you recognize this merchant by another name, or did anyone else authorized on the account make this purchase?"
        ],
    )


def propose_decision(message: str, history: list[ChatMessage], context: CaseContext) -> ModelDraft:
    if not os.getenv("OPENAI_API_KEY"):
        if os.getenv("ALLOW_OPENAI_FALLBACK", "").lower() in {"1", "true", "yes"}:
            return fallback_draft(context)
        raise RuntimeError("OPENAI_API_KEY is required because this service is configured to call OpenAI directly.")

    client = OpenAI()
    model = os.getenv("OPENAI_MODEL", "gpt-5.5")
    history_text = "\n".join(f"{item.role.value}: {item.content}" for item in history[-8:])

    response = client.responses.parse(
        model=model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Conversation history:\n"
                    f"{history_text or '[none]'}\n\n"
                    "Customer message:\n"
                    f"{message}\n\n"
                    "Case context JSON:\n"
                    f"{compact_context(context)}"
                ),
            },
        ],
        text_format=ModelDraft,
    )

    if response.output_parsed is None:
        raise RuntimeError("OpenAI response did not match the expected decision schema.")

    return response.output_parsed

