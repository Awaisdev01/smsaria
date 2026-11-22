"""Provider abstraction: any OpenAI-compatible chat endpoint.

Works with Groq (free tier), OpenAI, an on-host llama.cpp server, or any
service speaking /v1/chat/completions. Uses only urllib — no SDKs.

The budget guardrail wraps every call: per-sender daily caps, a global
daily cap, and a per-message token budget via max_tokens.
"""

from __future__ import annotations


import json
import time
import urllib.error
import urllib.request
from typing import Any


class Budget:
    """Daily cost guardrails keyed by sender number."""

    def __init__(
        self,
        per_sender_daily: int = 20,
        global_daily: int = 2000,
        max_reply_tokens: int = 400,
    ):
        self.per_sender_daily = per_sender_daily
        self.global_daily = global_daily
        self.max_reply_tokens = max_reply_tokens
        self._day = self._today()
        self._per_sender: dict[str, int] = {}
        self._global = 0

    @staticmethod
    def _today() -> str:
        return time.strftime("%Y-%m-%d")

    def _roll(self) -> None:
        today = self._today()
        if today != self._day:
            self._day = today
            self._per_sender.clear()
            self._global = 0

    def allow(self, sender: str) -> tuple[bool, str]:
        self._roll()
        used = self._per_sender.get(sender, 0)
        if used >= self.per_sender_daily:
            return False, "Daily limit reached for your number. Try again tomorrow."
        if self._global >= self.global_daily:
            return False, "Service at capacity today. Try again tomorrow."
        return True, ""

    def record(self, sender: str, tokens: int) -> None:
        self._roll()
        self._per_sender[sender] = self._per_sender.get(sender, 0) + tokens
        self._global += tokens


class OpenAICompatibleProvider:
    """Chat provider for any OpenAI-compatible /chat/completions endpoint."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        system_prompt: str,
        budget=None,
        timeout: int = 60,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.system_prompt = system_prompt
        self.budget = budget or Budget()
        self.timeout = timeout

    def chat(
        self,
        sender: str,
        user_text: str,
        history=None,
    ) -> tuple:
        """Return (reply_text, tokens_used). Raises ProviderError on failure."""
        ok, deny_message = self.budget.allow(sender)
        if not ok:
            return deny_message, 0

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt}
        ]
        if history:
            messages.extend(
                {"role": h["role"], "content": h["text"]} for h in history
            )
        messages.append({"role": "user", "content": user_text})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.budget.max_reply_tokens,
            "temperature": 0.4,
        }

        try:
            reply, tokens = self._post(payload)
        except urllib.error.HTTPError as e:
            raise ProviderError(
                f"provider HTTP {e.code}: {e.read().decode(errors='replace')[:200]}"
            ) from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ProviderError(f"provider unreachable: {e}") from e

        self.budget.record(sender, tokens)
        return reply, tokens

    def _post(self, payload: dict[str, Any]) -> tuple:
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode())
        choice = data["choices"][0]["message"]
        usage = data.get("usage", {})
        tokens = usage.get("total_tokens", 0)
        return choice.get("content") or "", tokens


class ProviderError(RuntimeError):
    pass
