"""Webhook adapters for SMS gateways.

Each adapter normalizes an inbound webhook into:
    {"sender": "+2547...", "text": "...", "meta": {...}}
and knows how to send the reply back through the same gateway's API.

Included:
  - TwilioAdapter      (Twilio Programmable SMS webhooks, form-encoded)
  - AfricasTalkingAdapter (Africa's Talking POST webhook, form-encoded)
  - RawAdapter         (generic JSON: {"sender": ..., "text": ...})

Sending uses each gateway's REST API with urllib. No SDKs.
"""

from __future__ import annotations


import json
import urllib.parse
import urllib.request
from typing import Any, Callable


class AdapterError(RuntimeError):
    pass


def _parse_form(body: bytes) -> dict[str, str]:
    return {
        k: v[0]
        for k, v in urllib.parse.parse_qs(body.decode(errors="replace")).items()
    }


def _send_via_rest(
    url: str,
    api_key: str,
    fields: dict[str, str],
    form: bool = True,
) -> dict[str, Any]:
    data = urllib.parse.urlencode(fields).encode() if form else json.dumps(fields).encode()
    headers = {
        "Content-Type": (
            "application/x-www-form-urlencoded" if form else "application/json"
        )
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}" if not form else f"Basic {api_key}"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


class TwilioAdapter:
    """Twilio Programmable Messaging webhook (form-encoded).

    Webhook: POST with From, Body, To. Replies can be sent inline via
    TwiML <Response><Message>, which is what this adapter does — zero API
    calls needed for the reply.
    """

    name = "twilio"

    def parse_inbound(self, body: bytes) -> dict[str, Any] | None:
        form = _parse_form(body)
        sender = form.get("From", "")
        text = form.get("Body", "")
        if not sender:
            return None
        return {"sender": sender, "text": text, "meta": form}

    def reply(self, original: dict[str, Any], text: str) -> dict[str, Any]:
        """Return TwiML response dict for the HTTP handler to serialize."""
        twiml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response><Message>"
            + text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            + "</Message></Response>"
        )
        return {"status": 200, "content_type": "text/xml", "body": twiml}


class AfricasTalkingAdapter:
    """Africa's Talking SMS webhook (form-encoded) + REST send.

    Webhook: POST with from, text, id, date, to (the shortcode).
    Send: POST https://api.sandbox.africastalking.com/version1/messaging
    with AT-Api-Key header. Recipients comma-separated.
    """

    name = "africastalking"

    def __init__(self, api_key: str, username: str, sandbox: bool = True):
        self.api_key = api_key
        self.username = username
        self.sandbox = sandbox

    def parse_inbound(self, body: bytes) -> dict[str, Any] | None:
        form = _parse_form(body)
        sender = form.get("from", "")
        text = form.get("text", "")
        if not sender:
            return None
        return {"sender": sender, "text": text, "meta": form}

    def reply(self, original: dict[str, Any], text: str) -> dict[str, Any]:
        host = (
            "api.sandbox.africastalking.com"
            if self.sandbox
            else "api.africastalking.com"
        )
        fields = {
            "username": self.username,
            "to": original["sender"],
            "message": text,
            # Use the shortcode the message arrived on, when known.
            "from": original.get("meta", {}).get("to", ""),
        }
        result = _send_via_rest(
            f"https://{host}/version1/messaging",
            self.api_key,
            fields,
            form=True,
        )
        return {"status": 200, "content_type": "application/json", "body": json.dumps({"status": "sent", "result": result.get("SMSMessageData", {}).get("Recipients", [])})}


class RawAdapter:
    """Generic JSON webhook: {"sender": "...", "text": "..."}.

    Reply sending is delegated to a caller-provided function.
    """

    name = "raw"

    def __init__(self, send_fn: Callable[[str, str], dict[str, Any]] | None = None):
        self.send_fn = send_fn

    def parse_inbound(self, body: bytes) -> dict[str, Any] | None:
        data = json.loads(body.decode(errors="replace"))
        sender = data.get("sender", "")
        text = data.get("text", "")
        if not sender:
            return None
        return {"sender": sender, "text": text, "meta": data}

    def reply(self, original: dict[str, Any], text: str) -> dict[str, Any]:
        if self.send_fn:
            return self.send_fn(original["sender"], text)
        return {"status": 200, "content_type": "application/json", "body": json.dumps({"reply": text})}


ADAPTERS: dict[str, Any] = {
    "twilio": TwilioAdapter,
    "africastalking": AfricasTalkingAdapter,
    "raw": RawAdapter,
}
