from typing import Any, Optional

from pydantic import BaseModel, Field


class ActionRequest(BaseModel):
    tool: str
    params: dict[str, Any] = Field(default_factory=dict)


class DecisionResponse(BaseModel):
    outcome: str  # block | require_hitl | log_and_allow
    matched_rule_id: Optional[str] = None
    reason: str
    review_id: Optional[str] = None


class ReviewResponse(BaseModel):
    review_id: str
    status: str


class HealthResponse(BaseModel):
    status: str
    supabase: bool
    version: str
