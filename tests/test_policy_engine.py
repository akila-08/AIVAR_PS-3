from app.policy_engine import evaluate, Rule

RULES = [
    Rule(
        id="block-bulk-delete",
        tool="db_delete",
        condition="record_count > 100",
        action="block",
        reason="Bulk delete exceeds safe threshold of 100 records",
    ),
    Rule(
        id="hitl-external-email",
        tool="send_email",
        condition="to_domain != 'internal.company.com'",
        action="require_hitl",
        reason="Email leaving the internal domain requires human review",
    ),
    Rule(
        id="log-confidential-read",
        tool="read_file",
        condition="'confidential' in path",
        action="log_and_allow",
        reason="Access to a confidential-marked path",
    ),
]


def test_bulk_delete_of_500_is_blocked():
    d = evaluate({"tool": "db_delete", "params": {"record_count": 500}}, RULES)
    assert d.outcome == "block"
    assert d.matched_rule_id == "block-bulk-delete"


def test_delete_of_5_is_allowed():
    d = evaluate({"tool": "db_delete", "params": {"record_count": 5}}, RULES)
    assert d.outcome == "log_and_allow"
    assert d.matched_rule_id is None  # falls through to default, no rule matched


def test_external_email_requires_hitl():
    d = evaluate({"tool": "send_email", "params": {"to_domain": "partner.com"}}, RULES)
    assert d.outcome == "require_hitl"
    assert d.matched_rule_id == "hitl-external-email"


def test_internal_email_is_allowed():
    d = evaluate(
        {"tool": "send_email", "params": {"to_domain": "internal.company.com"}}, RULES
    )
    assert d.outcome == "log_and_allow"
    assert d.matched_rule_id is None


def test_confidential_path_is_logged_and_allowed():
    d = evaluate(
        {"tool": "read_file", "params": {"path": "/data/confidential/report.pdf"}}, RULES
    )
    assert d.outcome == "log_and_allow"
    assert d.matched_rule_id == "log-confidential-read"


def test_unknown_tool_defaults_to_allow_with_audit():
    d = evaluate({"tool": "noop_tool", "params": {}}, RULES)
    assert d.outcome == "log_and_allow"
    assert d.matched_rule_id is None


def test_malformed_condition_is_skipped_not_crashed():
    bad_rules = [Rule(id="broken", tool="db_delete", condition="record_count >>> 1", action="block", reason="x")]
    d = evaluate({"tool": "db_delete", "params": {"record_count": 500}}, bad_rules)
    assert d.outcome == "log_and_allow"  # broken rule skipped, falls to default
