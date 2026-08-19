"""Loads policy rules from Supabase into the pure policy engine."""
from .supabase import get_client
from .policy_engine import Rule


def load_policies() -> list[Rule]:
    items = get_client().table("policies").select("rule_id,tool,condition,action,reason").execute().data or []
    rules = [
        Rule(
            id=item["rule_id"],
            tool=item["tool"],
            condition=item.get("condition") or None,
            action=item["action"],
            reason=item.get("reason", ""),
        )
        for item in items
    ]
    rules.sort(key=lambda r: r.id)
    return rules
