import { NextRequest, NextResponse } from "next/server";
import { createUIMessageStream, createUIMessageStreamResponse, type UIMessage } from "ai";

import { redactText } from "@/lib/redaction";
import type { CaseContext, ChatMessage, DisputeResponse } from "@/lib/types";

export const runtime = "nodejs";

function textFromMessage(message: UIMessage): string {
  // AI SDK v5 stores message content in parts, so we extract only text parts for our Python API.
  return message.parts
    .filter((part) => part.type === "text")
    .map((part) => part.text)
    .join("");
}

function toBackendHistory(messages: UIMessage[]): ChatMessage[] {
  return messages
    .filter((message) => message.role === "user" || message.role === "assistant")
    .map((message) => ({
      role: message.role as ChatMessage["role"],
      content: textFromMessage(message)
    }))
    .filter((message) => message.content.trim().length > 0);
}

function failClosedResponse(caseContext: CaseContext, transcript: ChatMessage[], reason: string): DisputeResponse {
  return {
    scenario: "scenario_3_likely_fraud",
    recommended_action: "escalate",
    reply:
      "I cannot complete the automated review safely right now. I am escalating this dispute to a specialist with the transaction details and this conversation.",
    reasoning_trace: {
      decision: "scenario_3_likely_fraud",
      recommended_action: "escalate",
      signal_checks: [],
      confidence: 0,
      rule_version: "frontend-fail-closed",
      model_rationale: `Frontend proxy could not complete the backend request: ${reason}`,
      supervisor_overrides: ["Backend failure forced the fail-closed escalation path."]
    },
    handoff_payload: {
      transaction: caseContext.transaction,
      signal_analysis: [],
      confidence: 0,
      transcript,
      summary: `Fail-closed escalation for ${caseContext.transaction.merchant_name}. The backend decision service was unavailable.`
    },
    redactions: [],
    audit_id: null
  };
}

function streamDisputeResponse(payload: DisputeResponse) {
  const stream = createUIMessageStream({
    execute: ({ writer }) => {
      const textId = "approved-reply";

      // The assistant text is the supervisor-approved customer reply.
      writer.write({ type: "start" });
      writer.write({ type: "text-start", id: textId });
      writer.write({ type: "text-delta", id: textId, delta: payload.reply });
      writer.write({ type: "text-end", id: textId });

      // The trace travels as an AI SDK data part so the right rail can update separately from chat text.
      writer.write({ type: "data-trace", data: payload });
      writer.write({ type: "finish", finishReason: "stop" });
    }
  });

  return createUIMessageStreamResponse({ stream });
}

export async function POST(request: NextRequest) {
  const body = await request.json();
  const messages = Array.isArray(body.messages) ? (body.messages as UIMessage[]) : [];
  const caseContext = body.case_context as CaseContext | undefined;
  const latestUserMessage = [...messages].reverse().find((message) => message.role === "user");
  const latestText = latestUserMessage ? textFromMessage(latestUserMessage) : "";
  const messageRedaction = redactText(latestText);
  const history = toBackendHistory(messages.slice(0, -1));
  const redactionLabels = new Set(messageRedaction.labels);

  const safeHistory = history.map((item) => {
    const result = redactText(item.content);
    result.labels.forEach((label) => redactionLabels.add(label));
    return { ...item, content: result.text };
  });
  const latestSafeMessage: ChatMessage = { role: "user", content: messageRedaction.text };
  const safeTranscript: ChatMessage[] = [...safeHistory, latestSafeMessage].filter(
    (message) => message.content.trim().length > 0
  );

  if (!caseContext) {
    return NextResponse.json({ error: "Missing case_context." }, { status: 400 });
  }

  const backendUrl = process.env.BACKEND_URL ?? "http://127.0.0.1:8001";
  let payload: DisputeResponse;

  try {
    const response = await fetch(`${backendUrl}/api/dispute`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        message: messageRedaction.text,
        history: safeHistory,
        case_context: caseContext
      }),
      // This timeout makes backend slowness follow the same fail-closed path as a backend outage.
      signal: AbortSignal.timeout(25000)
    });

    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}`);
    }

    payload = await response.json();
  } catch (caught) {
    const reason = caught instanceof Error ? caught.message : "unknown backend failure";
    payload = failClosedResponse(caseContext, safeTranscript, reason);
  }

  payload.redactions = Array.from(new Set([...(payload.redactions ?? []), ...redactionLabels])).sort();

  return streamDisputeResponse(payload);
}
