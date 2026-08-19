import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from mangum import Mangum

from .audit import get_audit_log, write_audit_record
from .supabase import get_client
from .logging_config import configure_logging
from .models import ActionRequest, DecisionResponse, HealthResponse, ReviewResponse
from .policies_store import load_policies
from .policy_engine import evaluate
from .reviews import create_pending_review, resolve_review

configure_logging()
logger = logging.getLogger("guardrail")

app = FastAPI(
    title="Guardrails Platform — Action Guardrail (PS-3.1)",
    version="1.0.0",
)

FRONTEND = Path(__file__).parent / "static" / "index.html"
app.mount("/static", StaticFiles(directory=FRONTEND.parent), name="static")


@app.get("/", include_in_schema=False)
def frontend() -> FileResponse:
    return FileResponse(FRONTEND)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Checks Supabase reachability so a broken deployment fails loudly,
    not silently, at the load balancer / uptime-check level."""
    try:
        get_client().table("policies").select("rule_id").limit(1).execute()
        db_ok = True
    except Exception:
        logger.exception("health check: Supabase unreachable")
        db_ok = False
    return HealthResponse(status="ok" if db_ok else "degraded", supabase=db_ok, version="1.0.0")


@app.post("/guardrail/evaluate", response_model=DecisionResponse)
def evaluate_action(action: ActionRequest) -> DecisionResponse:
    try:
        rules = load_policies()
    except Exception:
        logger.exception("failed to load policies from Supabase")
        raise HTTPException(status_code=503, detail="policy store unavailable")

    decision = evaluate(action.model_dump(), rules)

    review_id = None
    if decision.outcome == "require_hitl":
        try:
            review_id = create_pending_review(action.model_dump(), decision.reason)
        except Exception:
            logger.exception("failed to create pending review")
            raise HTTPException(status_code=500, detail="failed to register human review")

    executed = decision.outcome == "log_and_allow"
    try:
        write_audit_record(action.model_dump(), decision, executed=executed)
    except Exception:
        # Never let an audit-log failure block the security decision itself,
        # but always log it loudly — a silent gap in the audit trail is a
        # compliance problem, not just an availability blip.
        logger.exception(
            "audit record write failed", extra={"tool": action.tool, "outcome": decision.outcome}
        )

    logger.info(
        "action evaluated",
        extra={"tool": action.tool, "outcome": decision.outcome, "review_id": review_id},
    )

    return DecisionResponse(
        outcome=decision.outcome,
        matched_rule_id=decision.matched_rule_id,
        reason=decision.reason,
        review_id=review_id,
    )


@app.post("/guardrail/reviews/{review_id}/approve", response_model=ReviewResponse)
def approve_review(review_id: str) -> ReviewResponse:
    try:
        item = resolve_review(review_id, approve=True)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return ReviewResponse(review_id=review_id, status=item["status"])


@app.post("/guardrail/reviews/{review_id}/deny", response_model=ReviewResponse)
def deny_review(review_id: str) -> ReviewResponse:
    try:
        item = resolve_review(review_id, approve=False)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return ReviewResponse(review_id=review_id, status=item["status"])


@app.get("/guardrail/audit")
def audit(date: str = Query(..., description="YYYY-MM-DD"), limit: int = 50) -> list[dict]:
    try:
        return get_audit_log(date, limit)
    except Exception:
        logger.exception("failed to read audit log")
        raise HTTPException(status_code=503, detail="audit store unavailable")


# Lambda entrypoint (referenced as app.main.handler in template.yaml)
handler = Mangum(app)
