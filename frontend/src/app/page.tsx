"use client";

import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport, type UIMessage } from "ai";
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  ChevronRight,
  FileText,
  Layers3,
  ListChecks,
  MessageSquare,
  Send,
  ShieldCheck,
  SlidersHorizontal,
  UserRound
} from "lucide-react";
import { FormEvent, KeyboardEvent, useEffect, useMemo, useState } from "react";

import { demoCases } from "@/lib/sampleCases";
import type { DemoCase, DisputeResponse, EvaluationResult, SignalCheck } from "@/lib/types";

type DisputeUIMessage = UIMessage<unknown, { trace: DisputeResponse }>;
type RailTab = "trace" | "policy" | "eval" | "handoff";

const scenarioLabel: Record<string, string> = {
  scenario_1_straightforward: "Straightforward",
  scenario_2_ambiguous: "Ambiguous",
  scenario_3_likely_fraud: "Likely fraud"
};

const actionLabel: Record<string, string> = {
  resolve: "Resolve",
  ask_clarifying_question: "Clarify",
  escalate: "Escalate"
};

const journeyStages = [
  {
    label: "PII boundary",
    detail: "Sensitive identifiers are masked before model input."
  },
  {
    label: "Model proposal",
    detail: "OpenAI drafts a structured scenario, action, and reply."
  },
  {
    label: "Signal checks",
    detail: "Python recomputes transaction evidence for audit."
  },
  {
    label: "Supervisor",
    detail: "Deterministic guardrails can override the draft."
  },
  {
    label: "Journey outcome",
    detail: "Resolve, clarify, or hand off with context."
  }
];

const railTabs: Array<{ id: RailTab; label: string }> = [
  { id: "trace", label: "Trace" },
  { id: "policy", label: "Policy" },
  { id: "eval", label: "Eval" },
  { id: "handoff", label: "Handoff" }
];

function formatMoney(amount: number, currency: string) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency
  }).format(amount);
}

function StatusIcon({ status }: { status: SignalCheck["status"] }) {
  if (status === "risk") return <AlertTriangle size={16} />;
  if (status === "match") return <CheckCircle2 size={16} />;
  return <ChevronRight size={16} />;
}

function SignalRow({ signal }: { signal: SignalCheck }) {
  return (
    <div className={`signal-row status-${signal.status}`}>
      <div className="signal-icon">
        <StatusIcon status={signal.status} />
      </div>
      <div>
        <div className="signal-title">
          <span>{signal.label}</span>
          <strong>{signal.status}</strong>
        </div>
        <p>{signal.detail}</p>
      </div>
    </div>
  );
}

function assistantGreeting(): DisputeUIMessage {
  return {
    id: "assistant-greeting",
    role: "assistant",
    parts: [{ type: "text", text: "I can help review that charge. Tell me what looks unfamiliar." }]
  };
}

function messageText(message: DisputeUIMessage): string {
  // AI SDK messages are built from parts, so the UI renders the text parts and ignores trace data parts.
  return message.parts
    .filter((part) => part.type === "text")
    .map((part) => part.text)
    .join("");
}

export default function Home() {
  const [selectedCase, setSelectedCase] = useState<DemoCase>(demoCases[0]);
  const [input, setInput] = useState(selectedCase.openingMessage);
  const [latest, setLatest] = useState<DisputeResponse | null>(null);
  const [activeRailTab, setActiveRailTab] = useState<RailTab>("trace");
  const [evaluations, setEvaluations] = useState<EvaluationResult[]>([]);
  const [evalLoading, setEvalLoading] = useState(false);
  const [evalError, setEvalError] = useState<string | null>(null);
  const transport = useMemo(() => new DefaultChatTransport({ api: "/api/dispute" }), []);
  const { messages, sendMessage, setMessages, status, error } = useChat<DisputeUIMessage>({
    messages: [assistantGreeting()],
    transport,
    onData: (dataPart) => {
      if (dataPart.type === "data-trace") {
        setLatest(dataPart.data);
      }
    }
  });

  const transaction = selectedCase.context.transaction;
  const loading = status === "submitted" || status === "streaming";
  const customerRequestedReview = latest?.reasoning_trace.supervisor_overrides.some((override) =>
    override.toLowerCase().includes("customer explicitly requested human review")
  );
  const railTitle = loading ? "Reviewing" : customerRequestedReview ? "Human review" : latest ? scenarioLabel[latest.scenario] : "Ready";
  const railAction = loading ? "Active" : latest ? actionLabel[latest.recommended_action] : "No run";
  const railActionClass = loading ? "active" : latest?.recommended_action ?? "idle";
  const cardStatus = selectedCase.context.card_status.lost_or_stolen_reported ? "Reported lost" : "Active";
  const handoffStatus = latest?.handoff_payload ? "Required" : latest ? "Not required" : "Pending run";
  const auditStatus = latest?.audit_id ? "Logged" : "Not written";
  const nextStepStatus = loading
    ? "Reviewing"
    : latest?.recommended_action === "resolve"
      ? "Resolve"
      : latest?.recommended_action === "ask_clarifying_question"
        ? "Ask follow-up"
        : latest?.recommended_action === "escalate"
          ? "Human review"
          : "Pending run";
  const decisionReason =
    latest?.reasoning_trace.supervisor_overrides[0] ??
    latest?.reasoning_trace.model_rationale ??
    "Run a customer message to generate the supervised decision trace.";

  useEffect(() => {
    const tracePart = messages
      .flatMap((message) => message.parts)
      .findLast((part): part is DisputeUIMessage["parts"][number] & { type: "data-trace"; data: DisputeResponse } => {
        return part.type === "data-trace";
      });

    if (tracePart) {
      setLatest(tracePart.data);
    }
  }, [messages]);

  const timeline = useMemo(() => {
    const items = journeyStages.map((item, index) => ({
      ...item,
      active: index === 0 || Boolean(latest)
    }));

    if (latest?.handoff_payload) {
      items.push({
        label: "Human handoff",
        detail: "Escalation payload includes transaction, signals, and transcript.",
        active: true
      });
    }

    return items;
  }, [latest]);

  function switchCase(nextCase: DemoCase) {
    setSelectedCase(nextCase);
    setInput(nextCase.openingMessage);
    setLatest(null);
    setMessages([assistantGreeting()]);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await sendCurrentMessage();
  }

  async function sendCurrentMessage() {
    const trimmed = input.trim();
    if (!trimmed || loading) return;

    setInput("");
    await sendMessage(
      { text: trimmed },
      {
        // The AI SDK manages chat transport, and this body carries the regulated case context.
        body: { case_context: selectedCase.context }
      }
    );
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey) return;

    event.preventDefault();
    void sendCurrentMessage();
  }

  async function runEvalHarness() {
    setEvalLoading(true);
    setEvalError(null);

    try {
      const response = await fetch("/api/evaluations");
      const payload = await response.json();

      if (!response.ok) {
        throw new Error(payload.error ?? "Evaluation harness did not return results.");
      }

      setEvaluations(payload);
    } catch (caught) {
      setEvalError(caught instanceof Error ? caught.message : "Evaluation harness failed.");
    } finally {
      setEvalLoading(false);
    }
  }

  const passedEvaluations = evaluations.filter((result) => result.passed).length;

  return (
    <main className="app-shell">
      <section className="chat-pane">
        <header className="topbar">
          <div className="brand-lockup">
            <div>
              <p className="eyebrow">Fraud Journey</p>
              <h1>Dispute Supervisor</h1>
              <p className="page-subtitle">Customer dispute intake, policy supervision, and handoff trace.</p>
            </div>
          </div>
        </header>

        <div className="case-panel">
          <div className="case-panel-head">
            <div>
              <span>Active case</span>
              <strong>{selectedCase.label}</strong>
            </div>
            <div className={`case-outcome ${railActionClass}`}>{railAction}</div>
          </div>

          <div className="case-strip" aria-label="Demo cases">
            {demoCases.map((item) => (
              <button
                type="button"
                key={item.id}
                className={item.id === selectedCase.id ? "case-tab active" : "case-tab"}
                onClick={() => switchCase(item)}
              >
                {item.label}
              </button>
            ))}
          </div>

          <div className="transaction-band">
            <div>
              <span>Merchant</span>
              <strong>{transaction.merchant_name}</strong>
            </div>
            <div>
              <span>Amount</span>
              <strong>{formatMoney(transaction.amount, transaction.currency)}</strong>
            </div>
            <div>
              <span>Date</span>
              <strong>{transaction.date}</strong>
            </div>
            <div>
              <span>Category</span>
              <strong>{transaction.merchant_category}</strong>
            </div>
            <div>
              <span>Card status</span>
              <strong>{cardStatus}</strong>
            </div>
          </div>
        </div>

        <section className="conversation-shell">
          <div className="section-title">
            <div>
              <span>Customer view</span>
              <strong>Intake transcript</strong>
            </div>
            <p>{messages.length} messages</p>
          </div>

          <div className="conversation" aria-live="polite">
            {messages.map((message, index) => (
              <div key={`${message.role}-${index}`} className={`message ${message.role}`}>
                <div className="avatar" aria-hidden="true">
                  {message.role === "assistant" ? <Bot size={17} /> : <UserRound size={17} />}
                </div>
                <p>{messageText(message)}</p>
              </div>
            ))}
            {loading && (
              <div className="message assistant">
                <div className="avatar" aria-hidden="true">
                  <Bot size={17} />
                </div>
                <p>Reviewing the charge...</p>
              </div>
            )}
          </div>
        </section>

        {error && <div className="error-banner">{error.message}</div>}

        <form className="composer" onSubmit={submit}>
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleComposerKeyDown}
            placeholder="Describe the charge..."
            rows={2}
          />
          <button className="send-button" type="submit" disabled={loading || !input.trim()} aria-label="Send message">
            <Send size={18} />
          </button>
        </form>
      </section>

      <aside className={`trace-pane ${railActionClass}`}>
        <div className="trace-sticky">
          <div className="trace-header">
            <div>
              <p className="eyebrow">Supervisor decision</p>
              <h2>{railTitle}</h2>
            </div>
            <div className={`decision-pill ${railActionClass}`}>{railAction}</div>
          </div>

          <div className={`decision-summary ${railActionClass}`}>
            <span>Next step</span>
            <strong>{nextStepStatus}</strong>
            <p>{decisionReason}</p>
          </div>

          <div className="metric-grid">
            <div>
              <span>Confidence</span>
              <strong>{latest ? `${Math.round(latest.reasoning_trace.confidence * 100)}%` : "--"}</strong>
            </div>
            <div>
              <span>Audit log</span>
              <strong>{auditStatus}</strong>
              {latest?.audit_id && <small>{latest.audit_id}</small>}
            </div>
            <div>
              <span>Handoff</span>
              <strong>{handoffStatus}</strong>
            </div>
          </div>

          <div className="trace-tabs" role="tablist" aria-label="Supervisor rail views">
            {railTabs.map((tab) => (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={activeRailTab === tab.id}
                className={activeRailTab === tab.id ? "trace-tab active" : "trace-tab"}
                onClick={() => setActiveRailTab(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        <div className="tab-panel">
          {activeRailTab === "trace" && (
            <>
              <section className="rail-section first">
                <h3>
                  <Layers3 size={16} />
                  Model vs supervisor
                </h3>
                <div className="decision-compare">
                  <div>
                    <span>Model proposed</span>
                    <strong>
                      {latest?.reasoning_trace.model_recommended_action
                        ? actionLabel[latest.reasoning_trace.model_recommended_action]
                        : "No run"}
                    </strong>
                  </div>
                  <div>
                    <span>Supervisor decided</span>
                    <strong>{latest ? actionLabel[latest.recommended_action] : "No run"}</strong>
                  </div>
                  <div>
                    <span>Reason</span>
                    <p>{decisionReason}</p>
                  </div>
                </div>
              </section>

              <section className="rail-section">
                <h3>
                  <MessageSquare size={16} />
                  Orchestration
                </h3>
                <div className="timeline">
                  {timeline.map((item) => (
                    <div key={item.label} className={item.active ? "timeline-item active" : "timeline-item"}>
                      <span />
                      <div>
                        <strong>{item.label}</strong>
                        <p>{item.detail}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              <section className="rail-section">
                <h3>
                  <ShieldCheck size={16} />
                  Signals
                </h3>
                <div className="signal-list">
                  {latest ? (
                    latest.reasoning_trace.signal_checks.map((signal) => <SignalRow key={signal.id} signal={signal} />)
                  ) : (
                    <p className="muted">Signals appear after the first message is processed.</p>
                  )}
                </div>
              </section>

              {latest && (
                <section className="rail-section">
                  <h3>Policy version</h3>
                  <p className="muted">
                    Versioned supervisor rules make each decision traceable after policies change.
                  </p>
                  <code>{latest.reasoning_trace.rule_version}</code>
                </section>
              )}
            </>
          )}

          {activeRailTab === "policy" && (
            <>
              <section className="rail-section first">
                <h3>
                  <ShieldCheck size={16} />
                  Decision controls
                </h3>
                <div className="policy-list">
                  <div className="policy-row">
                    <span>Decision authority</span>
                    <strong>Rule supervisor</strong>
                    <p>The model proposes an action, while deterministic checks approve, clarify, or escalate.</p>
                  </div>
                  <div className="policy-row">
                    <span>Failure mode</span>
                    <strong>Fail closed</strong>
                    <p>Backend or model failure produces an escalation payload rather than a silent answer.</p>
                  </div>
                  <div className="policy-row">
                    <span>Excluded evidence</span>
                    <strong>Prior disputes</strong>
                    <p>Customer dispute history is visible to operations, but blocked from risk scoring.</p>
                  </div>
                </div>
              </section>

              <section className="rail-section">
                <h3>
                  <SlidersHorizontal size={16} />
                  Guardrail overrides
                </h3>
                {latest?.reasoning_trace.supervisor_overrides.length ? (
                  latest.reasoning_trace.supervisor_overrides.map((item) => (
                    <div className="override" key={item}>
                      {item}
                    </div>
                  ))
                ) : (
                  <p className="muted">No supervisor override yet.</p>
                )}
              </section>
            </>
          )}

          {activeRailTab === "eval" && (
            <section className="rail-section first">
              <div className="section-heading-row">
                <h3>
                  <ListChecks size={16} />
                  Eval harness
                </h3>
                <button className="small-button" type="button" onClick={runEvalHarness} disabled={evalLoading}>
                  {evalLoading ? "Running" : "Run"}
                </button>
              </div>
              {evaluations.length > 0 && (
                <div className="eval-summary">
                  {passedEvaluations}/{evaluations.length} passing
                </div>
              )}
              <p className="muted">
                Run this after a live case to compare the supervisor against controlled dispute scenarios.
              </p>
              {evalError && <p className="muted">{evalError}</p>}
              <div className="eval-list">
                {evaluations.map((result) => (
                  <div className={result.passed ? "eval-row passed" : "eval-row failed"} key={result.id}>
                    <div className="eval-title">
                      <span>{result.name}</span>
                      <strong>{result.passed ? "pass" : "review"}</strong>
                    </div>
                    <p>{result.note}</p>
                    <div className="eval-meta">
                      <span>{actionLabel[result.expected_action]}</span>
                      <span>{result.guardrail_fired ? "override" : "no override"}</span>
                      <span>{result.pii_redacted ? "PII checked" : "PII gap"}</span>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {activeRailTab === "handoff" && (
            <>
              <section className="rail-section first">
                <h3>
                  <FileText size={16} />
                  Escalation payload
                </h3>
                {latest?.handoff_payload ? (
                  <div className="handoff">
                    <strong>{latest.handoff_payload.summary}</strong>
                    <p>{latest.handoff_payload.transcript.length} transcript messages attached.</p>
                  </div>
                ) : (
                  <p className="muted">A payload is generated only when escalation is required.</p>
                )}
              </section>

              <section className="rail-section">
                <h3>
                  <FileText size={16} />
                  Payload fields
                </h3>
                <div className="policy-list">
                  <div className="policy-row">
                    <span>Customer context</span>
                    <strong>Masked transcript</strong>
                    <p>Conversation history is attached with sensitive identifiers removed.</p>
                  </div>
                  <div className="policy-row">
                    <span>Case evidence</span>
                    <strong>Transaction and signals</strong>
                    <p>Amount, merchant, dispute signals, and supervisor overrides travel together.</p>
                  </div>
                </div>
              </section>
            </>
          )}
        </div>
        <p className="creator-mark" aria-label="Created by Jake McCorkle">
          Created by Jake McCorkle
        </p>
      </aside>
    </main>
  );
}
