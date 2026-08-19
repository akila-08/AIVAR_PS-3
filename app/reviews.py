import time
import uuid

from .supabase import get_client

REVIEW_TTL_SECONDS = 24 * 3600


def create_pending_review(action: dict, reason: str) -> str:
    review_id = str(uuid.uuid4())
    get_client().table("reviews").insert({
        "review_id": review_id,
        "status": "pending",
        "action": action,
        "reason": reason,
        "expires_at": int(time.time()) + REVIEW_TTL_SECONDS,
    }).execute()
    return review_id


def get_review(review_id: str) -> dict | None:
    response = get_client().table("reviews").select("*").eq("review_id", review_id).limit(1).execute()
    return response.data[0] if response.data else None


def resolve_review(review_id: str, approve: bool) -> dict:
    """Transitions a pending review to approved/denied."""
    item = get_review(review_id)
    if item is None:
        raise ValueError(f"Review {review_id} not found")

    new_status = "approved" if approve else "denied"
    response = (get_client().table("reviews").update({"status": new_status}).select("*")
                .eq("review_id", review_id).eq("status", "pending").execute())
    if not response.data:
        raise ValueError(f"Review {review_id} is already resolved (status={item['status']})")

    item["status"] = new_status
    return item
