"""OpenAI-compatible transport. Used only when an API key is configured."""

import json
import os
import urllib.error
import urllib.request


class LlmNotConfigured(RuntimeError):
    pass


def rewriter_from_env():
    from lld_practice.evaluation.pipeline import LlmSuggestionRewriter, NullRewriter

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return NullRewriter()
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"

    def transport(prompt: str) -> str:
        return complete_chat(prompt, api_key=api_key, base_url=base_url, model=model)

    return LlmSuggestionRewriter(transport)


def complete_chat(prompt: str, *, api_key: str, base_url: str, model: str, timeout: float = 20) -> str:
    body = json.dumps(
        {
            "model": model,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "system",
                    "content": "Return a single JSON object. Do not include a score.",
                },
                {"role": "user", "content": prompt},
            ],
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"Language reviewer HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Language reviewer unreachable: {exc.reason}") from exc
    try:
        return payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Language reviewer returned an unexpected payload.") from exc
