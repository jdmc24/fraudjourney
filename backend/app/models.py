from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


RULE_VERSION = "fraud-dispute-rules-2026-07-07.1"


class Role(str, Enum):
    user = "user"
    assistant = "assistant"


class Scenario(str, Enum):
    straightforward = "scenario_1_straightforward"
    ambiguous = "scenario_2_ambiguous"
    likely_fraud = "scenario_3_likely_fraud"


class RecommendedAction(str, Enum):
    resolve = "resolve"
    ask_clarifying_question = "ask_clarifying_question"
    escalate = "escalate"


class ChatMessage(BaseModel):
    role: Role
    content: str


class Transaction(BaseModel):
    id: str
    merchant_name: str
    merchant_category: str
    amount: float
    currency: str = "USD"
    date: str
    country: str = "US"
    recurring: bool = False


class KnownMerchant(BaseModel):
    merchant_name: str
    aliases: list[str] = Field(default_factory=list)
    typical_amount: float | None = None
    recurring: bool = False


class RecentCharge(BaseModel):
    merchant_name: str
    amount: float
    currency: str = "USD"
    date: str
    country: str = "US"


class CardStatus(BaseModel):
    lost_or_stolen_reported: bool = False
    reported_at: str | None = None


class CaseContext(BaseModel):
    customer_id: str = "demo-customer"
    account_currency: str = "USD"
    home_country: str = "US"
    transaction: Transaction
    known_merchants: list[KnownMerchant] = Field(default_factory=list)
    recent_charges: list[RecentCharge] = Field(default_factory=list)
    card_status: CardStatus = Field(default_factory=CardStatus)


class DisputeRequest(BaseModel):
    message: str
    history: list[ChatMessage] = Field(default_factory=list)
    case_context: CaseContext


class SignalCheck(BaseModel):
    id: str
    label: str
    status: Literal["clear", "match", "partial", "risk", "unknown"]
    fired: bool
    detail: str
    weight: int = 0


class ModelDraft(BaseModel):
    scenario: Scenario
    recommended_action: RecommendedAction
    customer_reply: str
    rationale: str
    clarifying_questions: list[str] = Field(default_factory=list)


class ReasoningTrace(BaseModel):
    decision: Scenario
    recommended_action: RecommendedAction
    model_scenario: Scenario | None = None
    model_recommended_action: RecommendedAction | None = None
    signal_checks: list[SignalCheck]
    confidence: float
    rule_version: str = RULE_VERSION
    model_rationale: str
    supervisor_overrides: list[str] = Field(default_factory=list)


class HandoffPayload(BaseModel):
    transaction: Transaction
    signal_analysis: list[SignalCheck]
    confidence: float
    transcript: list[ChatMessage]
    summary: str


class DisputeResponse(BaseModel):
    scenario: Scenario
    recommended_action: RecommendedAction
    reply: str
    reasoning_trace: ReasoningTrace
    handoff_payload: HandoffPayload | None = None
    redactions: list[str] = Field(default_factory=list)
    audit_id: str | None = None


class EvaluationResult(BaseModel):
    id: str
    name: str
    expected_scenario: Scenario
    actual_scenario: Scenario
    expected_action: RecommendedAction
    actual_action: RecommendedAction
    passed: bool
    guardrail_fired: bool
    handoff_complete: bool
    pii_redacted: bool
    supervisor_overrides: list[str] = Field(default_factory=list)
    note: str
