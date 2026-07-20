# Fraud Dispute Journey Supervisor

This is a reference build for a regulated financial-services dispute agent. The demo shows how a customer-facing agent can use a model for language while keeping final decision authority in deterministic policy code.

The core operating pattern is simple enough to understand quickly, and strict enough to defend in a regulated setting:

```text
LLM proposes.
Supervisor decides.
Trace explains.
Human handoff carries context.
```

## Why This Exists

Fraud disputes are emotionally charged and operationally risky. A regulated workflow needs to prove why a dispute was resolved, clarified, or escalated.

This project is built around the harder question:

> How do you wrap a flexible language model in controls that a financial-services team could inspect, test, and operate?

The demo has three outcomes:

- Resolve a clearly legitimate charge.
- Ask a clarifying question when the evidence is ambiguous.
- Escalate likely fraud with a human handoff payload.

## Architecture

- `frontend/`: Next.js and TypeScript interface for Vercel.
- `backend/`: FastAPI service for Railway.
- `docs/reference-architecture.md`: architecture notes for the supervised dispute workflow.

Runtime flow:

1. Customer sends a message in the Next.js chat UI.
2. Vercel AI SDK `useChat` manages the chat state and request lifecycle.
3. The Next.js API route redacts sensitive identifiers before forwarding the request.
4. FastAPI performs defense-in-depth redaction again.
5. OpenAI proposes a structured draft decision.
6. Python recomputes transaction signals.
7. The supervisor applies guardrails and can override the model.
8. The backend writes a SQLite audit record.
9. The frontend receives an AI SDK UI message stream containing the approved reply and trace data.
10. If escalation is required, the response includes a handoff payload.

The app also includes a controlled evaluation harness. It runs seeded cases where the model draft is intentionally wrong, then checks whether the supervisor produces the expected final outcome.

## Distinguishing Factor

The model drafts the language and scenario proposal. The supervisor owns the regulated decision.

OpenAI handles:

- Parsing messy customer language.
- Drafting a structured scenario proposal.
- Writing a calm customer-facing response.

Python handles:

- PII redaction.
- Transaction signal evaluation.
- Guardrail enforcement.
- Confidence calculation.
- Rule versioning.
- Audit logging.
- Handoff payload generation.

That separation is the main design decision in the project.

## Local Setup

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

Create `backend/.env` for local secrets:

```bash
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4.1-mini
ALLOW_OPENAI_FALLBACK=0
ALLOWED_ORIGINS=http://127.0.0.1:3000,http://localhost:3000
AUDIT_DB_PATH=audit_log.sqlite3
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open the app:

- Frontend: `http://127.0.0.1:3000`
- Backend status: `http://127.0.0.1:8001/`
- Backend docs: `http://127.0.0.1:8001/docs`
- Backend health: `http://127.0.0.1:8001/health`

Keep the backend and frontend running in separate terminal windows during local testing.

## Environment Variables

Backend:

- `OPENAI_API_KEY`: required for live model calls.
- `OPENAI_MODEL`: model used by the primary language layer.
- `ALLOW_OPENAI_FALLBACK`: optional local fallback. Keep `0` for the intended live API path.
- `ALLOWED_ORIGINS`: comma-separated frontend origins allowed by FastAPI CORS.
- `AUDIT_DB_PATH`: SQLite file path for decision audit records.

Frontend:

- `BACKEND_URL`: Railway or local FastAPI URL. Defaults to `http://127.0.0.1:8001` in local development.

Never expose the OpenAI key through a `NEXT_PUBLIC_*` variable.

## Verification

Run backend tests:

```bash
cd backend
.venv/bin/python -m pytest tests
```

Run frontend build:

```bash
cd frontend
npm run build
```

From the UI, use the `Eval harness` panel in the right rail to run the controlled cases.

## Deployment Shape

Backend:

- Deploy `backend/` to Railway.
- Set `OPENAI_API_KEY`, `OPENAI_MODEL`, `ALLOWED_ORIGINS`, and `AUDIT_DB_PATH` as Railway variables.
- Exposes `GET /`, `GET /health`, `GET /docs`, `POST /api/dispute`, and `GET /api/evaluations`.

Frontend:

- Deploy `frontend/` to Vercel.
- Set `BACKEND_URL` to the Railway backend URL.

## Project Summary

This project demonstrates a supervised fraud dispute journey where the LLM handles language and structure, while deterministic policy code recomputes evidence, applies guardrails, records an audit trace, and decides whether the journey should resolve, clarify, or hand off.

The frontend uses Vercel AI SDK `useChat`, the backend writes a SQLite audit record for each completed decision, and the eval harness checks supervisor behavior across controlled edge cases.
