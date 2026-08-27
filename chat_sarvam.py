"""Single Sarvam LLM client, reused by every text agent.

Sarvam's /v1/chat/completions is OpenAI-compatible, so langchain-openai's
ChatOpenAI works if we point base_url at Sarvam and pass the two auth headers.
The API key is read from the environment ONLY (never hard-coded, never sent to client).

Notes / robustness:
- Sarvam-105B intermittently returns an empty `content` (free-tier throttling /
  capacity). chat() retries with a short backoff, and if still empty, falls back to
  `fallback_messages` (a source-free prompt) so the agent always returns something useful.
"""
import os, time
from langchain_openai import ChatOpenAI


def _build(temperature: float, max_tokens: int) -> ChatOpenAI:
    key = os.environ["SARVAM_API_KEY"]
    return ChatOpenAI(
        model="sarvam-105b",
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=key,
        base_url="https://api.sarvam.ai/v1",
        default_headers={
            "api-subscription-key": key,
            "Authorization": f"Bearer {key}",
        },
    )


def get_sarvam_chat(temperature: float = 0.0, max_tokens: int = 1500) -> ChatOpenAI:
    """Return a ChatOpenAI bound to Sarvam. Callers use .invoke([...]).content."""
    return _build(temperature, max_tokens)


def chat(messages, temperature: float = 0.0, max_tokens: int = 1500,
         fallback_messages=None, retries: int = 5) -> str:
    """Invoke Sarvam and return the text, retrying (with backoff) on empty responses.

    fallback_messages: if primary still empty after retries, try this once
    (e.g. a source-free version) so the caller never gets a blank string.
    """
    llm = _build(temperature, max_tokens)
    last = ""
    for attempt in range(retries):
        try:
            out = llm.invoke(messages)
            text = (out.content or "").strip()
            if text:
                return text
            last = text
        except Exception as e:
            last = f"(error: {e})"
        # progressive backoff: Sarvam free tier throttles bursts with empty completions
        time.sleep(2.0 * (attempt + 1))
    if fallback_messages:
        for attempt in range(2):
            try:
                out = llm.invoke(fallback_messages)
                text = (out.content or "").strip()
                if text:
                    return text
            except Exception:
                pass
            time.sleep(3.0)
    return last
