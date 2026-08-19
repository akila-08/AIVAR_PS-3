"""
Core rule-matching logic for the Action Guardrail. Deliberately has zero
network dependencies so it can be unit-tested in isolation (see
tests/test_policy_engine.py) — persistence lives in policies_store.py.
"""
from dataclasses import dataclass
from typing import Optional

from .condition_eval import safe_eval_condition, ConditionError

VALID_ACTIONS = {"block", "require_hitl", "log_and_allow"}


@dataclass
class Rule:
    id: str
    tool: str
    condition: Optional[str]  # None means "always matches this tool"
    action: str
    reason: str

    def __post_init__(self):
        if self.action not in VALID_ACTIONS:
            raise ValueError(f"Invalid rule action {self.action!r} on rule {self.id!r}")


@dataclass
class Decision:
    outcome: str
    matched_rule_id: Optional[str]
    reason: str


def evaluate(action: dict, rules: list[Rule]) -> Decision:
    """Evaluate one proposed tool call against an ordered policy ruleset.

    Rules are evaluated in list order; the first matching rule wins.
    If no rule matches, the default is log_and_allow (fail open, but
    always audited) rather than silently dropping ungoverned actions.
    """
    tool = action.get("tool")
    params = action.get("params", {}) or {}

    for rule in rules:
        if rule.tool != tool:
            continue
        if rule.condition:
            try:
                if not safe_eval_condition(rule.condition, params):
                    continue
            except ConditionError:
                # A malformed rule should never crash evaluation of an
                # otherwise-fine action; skip it and keep checking.
                continue
        return Decision(outcome=rule.action, matched_rule_id=rule.id, reason=rule.reason)

    return Decision(
        outcome="log_and_allow",
        matched_rule_id=None,
        reason="No policy rule matched this action; default allow with audit.",
    )
