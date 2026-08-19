"""
Load the example policy ruleset into Supabase.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.supabase import get_client

POLICIES = [
    {
        "rule_id": "01-block-bulk-delete",
        "tool": "db_delete",
        "condition": "record_count > 100",
        "action": "block",
        "reason": "Bulk delete exceeds safe threshold of 100 records",
    },
    {
        "rule_id": "02-hitl-external-email",
        "tool": "send_email",
        "condition": "to_domain != 'internal.company.com'",
        "action": "require_hitl",
        "reason": "Email leaving the internal domain requires human review",
    },
    {
        "rule_id": "03-log-confidential-read",
        "tool": "read_file",
        "condition": "'confidential' in path",
        "action": "log_and_allow",
        "reason": "Access to a confidential-marked path",
    },
]


def seed() -> None:
    for p in POLICIES:
        get_client().table("policies").upsert(p).execute()
    print(f"Seeded {len(POLICIES)} policies into Supabase")


if __name__ == "__main__":
    seed()
