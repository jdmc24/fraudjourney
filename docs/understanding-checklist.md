# Understanding Checklist

This checklist tracks what the builder should be able to explain before the project is treated as interview-ready. It is written for learning, so each item should be restated in plain English during the build.

## 1. The Problem

- [ ] Explain why fraud disputes are a risky place to use a plain chatbot.
- [ ] Explain why a polite model response is not enough in regulated financial services.
- [ ] Explain the three possible journey outcomes: resolve, clarify, escalate.
- [ ] Explain why an unfamiliar merchant does not automatically mean fraud.
- [ ] Explain why prior dispute behavior should not be used as a transaction risk signal.
- [ ] Explain why human handoff quality matters when automation stops.

## 2. The Solution

- [ ] Explain the split between the Next.js frontend and FastAPI backend.
- [ ] Explain what the OpenAI language layer does.
- [ ] Explain what the Python supervisor does.
- [ ] Explain why the model proposes while the supervisor decides.
- [ ] Explain why the UI shows both the model proposal and the supervisor decision.
- [ ] Explain what a guardrail override is, using one concrete example.
- [ ] Explain why PII is redacted before model processing.
- [ ] Explain what belongs in the reasoning trace.
- [ ] Explain what belongs in the handoff payload.

## 3. Edge Cases

- [ ] Known recurring merchant with normal amount should resolve.
- [ ] Known recurring merchant with changed amount should clarify.
- [ ] Unknown merchant with no other risk signal should clarify.
- [ ] Lost or stolen card report should escalate.
- [ ] Risky merchant category plus other risk signals should escalate.
- [ ] Legal merchant name mismatch should avoid automatic escalation.
- [ ] Mixed charges should be evaluated individually.

## 4. Broader Context

- [ ] Explain how the demo connects to Sierra-style journeys, traces, and guardrails.
- [ ] Explain how the frontend connects to a Vercel-style reference app.
- [ ] Explain why the project uses neutral branding instead of official Sierra or Vercel marks.
- [ ] Explain why the right rail leads with operational decision state instead of decorative dashboard widgets.
- [ ] Explain the main success metrics: auto-resolution rate, escalation accuracy, false escalation rate, guardrail override rate, PII redaction coverage, and handoff completeness.
- [ ] Explain how the evaluation panel strengthens the project.
- [ ] Explain why `fraudjourney.com`, Vercel, Railway, and CORS all need to line up for a working production demo.

## 5. Restatement Prompts

Use these prompts before moving to the next build stage:

1. In your own words, what problem is this system solving?
2. What should the model be allowed to do, and what should policy code decide?
3. When should the system ask a clarifying question instead of escalating?
4. What would make this project credible to a Sierra employee?
5. What would you test before deploying this to Vercel and Railway?
6. In the Netflix case, why is it powerful that the model proposed clarification but the supervisor resolved the case?
