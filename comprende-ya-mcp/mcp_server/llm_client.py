"""HTTP client for the LLM judge (llama-server OpenAI-compatible API)."""

from __future__ import annotations

import os

from openai import AsyncOpenAI, APIError

JUDGE_LLM_BASE_URL = os.environ.get("JUDGE_LLM_BASE_URL", "http://localhost:8082/v1")
JUDGE_LLM_MODEL = os.environ.get(
    "JUDGE_LLM_MODEL", "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"
)
JUDGE_LLM_TIMEOUT = float(os.environ.get("JUDGE_LLM_TIMEOUT", "60.0"))

_client = AsyncOpenAI(
    base_url=JUDGE_LLM_BASE_URL,
    api_key="not-needed",
    timeout=JUDGE_LLM_TIMEOUT,
)


class LLMClientError(Exception):
    """Raised when the LLM judge request fails."""


async def call_judge(system_prompt: str, user_prompt: str) -> str:
    """Send a chat completion request to the judge LLM.

    Returns the raw content string from the first choice.
    """
    try:
        response = await _client.chat.completions.create(
            model=JUDGE_LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
    except APIError as e:
        raise LLMClientError(f"Judge LLM returned error: {e}") from e
    except Exception as e:
        raise LLMClientError(f"Judge LLM request failed: {e}") from e

    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError) as e:
        raise LLMClientError(f"Unexpected response structure: {response}") from e
    if content is None:
        raise LLMClientError("Judge LLM returned empty content")
    return content
