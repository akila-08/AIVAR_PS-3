# Guardrails Platform — PS-3.1 Action Guardrail

Pre-execution policy enforcement for agent tool calls. Every proposed tool
call is evaluated against a declarative ruleset **before** it executes,
resolving to `block`, `require_hitl`, or `log_and_allow`. Deployed serverless
on Render with Supabase — not a localhost script.

## Architecture

```
Client / Agent
     │
     ▼
Render Web Service  ─────────────────►  Render Logs
     │
     ▼
FastAPI app in a Render Web Service
     ├── POST /guardrail/evaluate
     ├── POST /guardrail/reviews/{id}/approve | /deny
     ├── GET  /guardrail/audit?date=YYYY-MM-DD
     └── GET  /health
     │
     ▼
Supabase Postgres (policies, audit log, pending reviews)
```

## Local development & tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
uvicorn app.main:app --reload
```

## Supabase setup

```bash
Create a Supabase project, open SQL Editor, and run [`supabase/schema.sql`](supabase/schema.sql).
Set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`, then seed the policies:

```bash
python scripts/seed_policies.py
```

Use the service-role key only on the server. Never expose it in frontend code.

## Deploy to Render

Create a Render **Web Service** from this repository. Render detects the Dockerfile.
Set these environment variables:

```text
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<server-only-service-role-key>
```

Use this start command so Render's assigned port is honored:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Run the real-LLM demo agent

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export GUARDRAIL_API_URL=https://<your-render-service>.onrender.com
python agent/demo_agent.py
```

Claude decides the tool call for each scenario; that real model output is
submitted to the deployed guardrail for a live decision.

## Success criteria → proof

| Success criterion | Proof |
|---|---|
| All three outcomes fire correctly | `tests/test_policy_engine.py` + `agent/demo_agent.py` output |
| Bulk delete (500) blocked, delete of 5 allowed | `test_bulk_delete_of_500_is_blocked`, `test_delete_of_5_is_allowed` |
| External email → HITL, internal email → allowed | `test_external_email_requires_hitl`, `test_internal_email_is_allowed` |
| Audit log captures every evaluated action | `GET /guardrail/audit?date=...`, `test_audit_log_captures_evaluated_actions` |
| Deployed on Render | Dockerfile → Render Web Service + Supabase |
| Concurrent requests handled safely | `resolve_review` updates only rows still in `pending` state |
| Logging, error handling, health check | `logging_config.py` (structured JSON → CloudWatch), try/except + proper HTTP codes in `main.py`, `GET /health` |
| Real LLM provider, not mocked | `agent/demo_agent.py` calls the Anthropic API directly |

## Example requests

```bash
BASE=https://<your-render-service>.onrender.com

curl -X POST $BASE/guardrail/evaluate \
  -H "Content-Type: application/json" \
  -d '{"tool":"db_delete","params":{"record_count":500}}'
# -> {"outcome":"block", "matched_rule_id":"01-block-bulk-delete", ...}

curl -X POST $BASE/guardrail/evaluate \
  -H "Content-Type: application/json" \
  -d '{"tool":"send_email","params":{"to_domain":"partner.com"}}'
# -> {"outcome":"require_hitl", "review_id":"<uuid>", ...}

curl -X POST $BASE/guardrail/reviews/<uuid>/approve

curl "$BASE/guardrail/audit?date=$(date -u +%Y-%m-%d)"

curl $BASE/health
```

## Known limitations (1-day scope, documented not hidden)

- No auth on the Render endpoint yet — add application authentication or
  usage-plan API key before this handles anything beyond demo/eval traffic.
- `dry_run` mode and the bonus "simulation harness" from the original
  problem statement are not yet implemented — next on the list.
- Policy rules are seeded via a script, not an admin API — fine for a demo,
  would need a `POST /guardrail/policies` endpoint for real rule management.
