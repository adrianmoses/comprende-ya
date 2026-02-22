"""HTTP client for the LLM judge (vLLM OpenAI-compatible API)."""

from __future__ import annotations

import os

import httpx

JUDGE_LLM_BASE_URL = os.environ.get("JUDGE_LLM_BASE_URL", "http://localhost:8002/v1")
JUDGE_LLM_MODEL = os.environ.get(
    "JUDGE_LLM_MODEL", "meta-llama/Llama-3.2-3B-Instruct"
)
JUDGE_LLM_TIMEOUT = float(os.environ.get("JUDGE_LLM_TIMEOUT", "30.0"))


class LLMClientError(Exception):
    """Raised when the LLM judge request fails."""


async def call_judge(system_prompt: str, user_prompt: str) -> str:
    """Send a chat completion request to the judge LLM.

    Returns the raw content string from the first choice.
    """
    url = f"{JUDGE_LLM_BASE_URL}/chat/completions"
    payload = {
        "model": JUDGE_LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
    }

    try:
        async with httpx.AsyncClient(timeout=JUDGE_LLM_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise LLMClientError(
            f"Judge LLM returned {e.response.status_code}: {e.response.text}"
        ) from e
    except httpx.RequestError as e:
        raise LLMClientError(f"Judge LLM request failed: {e}") from e

    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise LLMClientError(f"Unexpected response structure: {data}") from e
