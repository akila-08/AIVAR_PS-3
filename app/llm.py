import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import ValidationError

from .models import ActionRequest


SYSTEM_PROMPT = """You are an operations agent. Given a task, respond with ONLY a JSON
object describing the single tool call you would make — no prose, no markdown fences.

Format: {"tool": "db_delete" | "send_email" | "read_file", "params": {...}}
- db_delete params: {"record_count": <int>}
- send_email params: {"to_domain": "<domain>"}
- read_file params: {"path": "<path>"}"""


class LLMConfigurationError(RuntimeError):
    pass


class LLMProposalError(RuntimeError):
    pass


def propose_action(scenario: str) -> ActionRequest:
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise LLMConfigurationError("GEMINI_API_KEY is not configured")

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"{SYSTEM_PROMPT}\n\nTask:\n{scenario}",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0,
                max_output_tokens=512,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        text = (response.text or "").strip()
        if not text:
            raise LLMProposalError("Gemini returned an empty action proposal")
        proposal = json.loads(text)
        return ActionRequest.model_validate(proposal)
    except (json.JSONDecodeError, IndexError, KeyError, TypeError, ValidationError) as exc:
        raise LLMProposalError("Gemini returned an invalid action proposal") from exc
    except Exception as exc:
        raise LLMProposalError("Gemini could not generate an action proposal") from exc