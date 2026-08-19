import uuid
from datetime import datetime, timezone

from .policy_engine import Decision
from .supabase import get_client


def write_audit_record(action: dict, decision: Decision, executed: bool) -> str:
    now = datetime.now(timezone.utc)
    action_id = str(uuid.uuid4())

    get_client().table("audit_log").insert({
        "action_id": action_id,
        "created_at": now.isoformat(),
        "tool": action.get("tool"),
        "params": action.get("params", {}),
        "outcome": decision.outcome,
        "matched_rule": decision.matched_rule_id,
        "reason": decision.reason,
        "executed": executed,
        "module": "guardrail",
    }).execute()
    return action_id


def get_audit_log(date: str, limit: int = 50) -> list[dict]:
    start = f"{date}T00:00:00+00:00"
    end = f"{date}T23:59:59.999999+00:00"
    response = (get_client().table("audit_log").select("*")
                .gte("created_at", start).lte("created_at", end)
                .order("created_at", desc=True).limit(limit).execute())
    return response.data or []
