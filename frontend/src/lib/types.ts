export type Role = "user" | "assistant";

export type Scenario =
  | "scenario_1_straightforward"
  | "scenario_2_ambiguous"
  | "scenario_3_likely_fraud";

export type RecommendedAction = "resolve" | "ask_clarifying_question" | "escalate";

export type ChatMessage = {
  role: Role;
  content: string;
};

export type Transaction = {
  id: string;
  merchant_name: string;
  merchant_category: string;
  amount: number;
  currency: string;
  date: string;
  country: string;
  recurring: boolean;
};

export type KnownMerchant = {
  merchant_name: string;
  aliases: string[];
  typical_amount?: number;
  recurring: boolean;
};

export type RecentCharge = {
  merchant_name: string;
  amount: number;
  currency: string;
  date: string;
  country: string;
};

export type CaseContext = {
  customer_id: string;
  account_currency: string;
  home_country: string;
  transaction: Transaction;
  known_merchants: KnownMerchant[];
  recent_charges: RecentCharge[];
  card_status: {
    lost_or_stolen_reported: boolean;
    reported_at?: string | null;
  };
};

export type SignalCheck = {
  id: string;
  label: string;
  status: "clear" | "match" | "partial" | "risk" | "unknown";
  fired: boolean;
  detail: string;
  weight: number;
};

export type ReasoningTrace = {
  decision: Scenario;
  recommended_action: RecommendedAction;
  model_scenario?: Scenario | null;
  model_recommended_action?: RecommendedAction | null;
  signal_checks: SignalCheck[];
  confidence: number;
  rule_version: string;
  model_rationale: string;
  supervisor_overrides: string[];
};

export type HandoffPayload = {
  transaction: Transaction;
  signal_analysis: SignalCheck[];
  confidence: number;
  transcript: ChatMessage[];
  summary: string;
};

export type DisputeResponse = {
  scenario: Scenario;
  recommended_action: RecommendedAction;
  reply: string;
  reasoning_trace: ReasoningTrace;
  handoff_payload: HandoffPayload | null;
  redactions: string[];
  audit_id?: string | null;
};

export type EvaluationResult = {
  id: string;
  name: string;
  expected_scenario: Scenario;
  actual_scenario: Scenario;
  expected_action: RecommendedAction;
  actual_action: RecommendedAction;
  passed: boolean;
  guardrail_fired: boolean;
  handoff_complete: boolean;
  pii_redacted: boolean;
  supervisor_overrides: string[];
  note: string;
};

export type DemoCase = {
  id: string;
  label: string;
  openingMessage: string;
  context: CaseContext;
};
