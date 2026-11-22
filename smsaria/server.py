"""SMSaria gateway server — stdlib HTTP, no frameworks.

Endpoints:
  POST /sms/<adapter>       inbound SMS webhook (twilio|africastalking|raw)
  POST /ussd/<adapter>      inbound USSD callback (africastalking style)
  GET  /health              liveness + stats
  GET  /                    tiny dashboard (usage, caps, sessions)

Configuration via environment:
  SMSARIA_PROVIDER_BASE   e.g. https://api.groq.com/openai/v1
  SMSARIA_PROVIDER_KEY    API key
  SMSARIA_MODEL           model name
  SMSARIA_SYSTEM_PROMPT   system prompt (use {language_hint} for autolang)
  SMSARIA_PER_SENDER_DAILY daily token cap per number (default 20)
  SMSARIA_GLOBAL_DAILY    global daily token cap (default 2000)
  SMSARIA_ADAPTERS        comma list of enabled adapters (default: raw)
  SMSARIA_AT_API_KEY      Africa's Talking key (if enabled)
  SMSARIA_AT_USERNAME     Africa's Talking username
  SMSARIA_AT_SANDBOX      "1" to use the sandbox host

Run:  python -m smsaria.server
"""

from __future__ import annotations


import json
import os
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .adapters.webhooks import ADAPTERS, AfricasTalkingAdapter, RawAdapter
from .gateway.sessions import SessionStore
from .gateway.sms import compress, split_sms
from .providers.openai_compat import Budget, OpenAICompatibleProvider, ProviderError
from .ussd.engine import USSDEngine

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful assistant answering over SMS for people on basic "
    "phones with no internet access. Be concrete and practical. Prefer "
    "short sentences and numbered steps. Answer in the same language the "
    "person used ({language_hint}). Keep answers under 480 characters; "
    "the gateway will split longer answers across messages."
)


def detect_language_hint(text: str) -> str:
    """Cheap script-based language hint for the system prompt.

    Not a detector — a hint. The model does the actual language matching.
    """
    arabic = any("\u0600" <= ch <= "\u06ff" for ch in text)
    devanagari = any("\u0900" <= ch <= "\u097f" for ch in text)
    swahili_words = {"habari", "asante", "karibu", "nini", "kwa", "nini", "sasa"}
    if arabic:
        return "likely Arabic or Urdu"
    if devanagari:
        return "likely Hindi"
    if any(w in text.lower() for w in swahili_words):
        return "likely Swahili"
    return "the person's language"


class Gateway:
    def __init__(self, config: dict[str, str] | None = None):
        cfg = config or dict(os.environ)
        self.cfg = cfg
        base = cfg.get("SMSARIA_PROVIDER_BASE", "https://api.groq.com/openai/v1")
        key = cfg.get("SMSARIA_PROVIDER_KEY", "")
        model = cfg.get("SMSARIA_MODEL", "llama-3.1-8b-instant")
        self.budget = Budget(
            per_sender_daily=int(cfg.get("SMSARIA_PER_SENDER_DAILY", "20")),
            global_daily=int(cfg.get("SMSARIA_GLOBAL_DAILY", "2000")),
        )
        self.provider = OpenAICompatibleProvider(
            base_url=base,
            api_key=key,
            model=model,
            system_prompt=cfg.get("SMSARIA_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT),
            budget=self.budget,
        )
        self.sessions = SessionStore()
        self.adapter_names = [
            a.strip() for a in cfg.get("SMSARIA_ADAPTERS", "raw").split(",") if a.strip()
        ]
        self.adapters = {}
        for name in self.adapter_names:
            if name == "africastalking":
                self.adapters[name] = AfricasTalkingAdapter(
                    api_key=cfg.get("SMSARIA_AT_API_KEY", ""),
                    username=cfg.get("SMSARIA_AT_USERNAME", ""),
                    sandbox=cfg.get("SMSARIA_AT_SANDBOX", "1") == "1",
                )
            else:
                self.adapters[name] = ADAPTERS[name]()
        self.ussd_engine = USSDEngine(self._load_ussd_menus())
        self.stats = {"inbound": 0, "replies": 0, "errors": 0, "denied": 0}
        self.ussd_state: dict[str, dict] = {}
        self.lock = threading.Lock()

    # ── USSD menu loading ────────────────────────────────────────────────
    @staticmethod
    def _load_ussd_menus() -> dict:
        return {
            "root": {
                "title": "Welcome to AI Help",
                "options": {
                    "1": ("Ask a question", "ask"),
                    "2": ("Daily tips", "info:daily"),
                },
            }
        }

    # ── SMS pipeline ─────────────────────────────────────────────────────
    def handle_sms(self, adapter_name: str, body: bytes) -> dict:
        adapter = self.adapters.get(adapter_name)
        if adapter is None:
            return {"status": 404, "content_type": "text/plain", "body": "unknown adapter"}
        try:
            inbound = adapter.parse_inbound(body)
        except Exception:
            with self.lock:
                self.stats["errors"] += 1
            return {"status": 400, "content_type": "text/plain", "body": "bad request"}
        if not inbound:
            with self.lock:
                self.stats["errors"] += 1
            return {"status": 400, "content_type": "text/plain", "body": "bad request"}

        sender, text = inbound["sender"], inbound["text"]
        with self.lock:
            self.stats["inbound"] += 1

        sess = self.sessions.get(sender) or self.sessions.start(sender)
        hint = detect_language_hint(text)
        self.provider.system_prompt = self.provider.system_prompt.replace(
            "{language_hint}", hint
        )
        try:
            reply, _tokens = self.provider.chat(
                sender, text, history=sess["history"]
            )
        except ProviderError as e:
            with self.lock:
                self.stats["errors"] += 1
            reply = "Service error, please try again shortly."

        self.sessions.append_history(sender, sess, "user", text)
        self.sessions.append_history(sender, sess, "assistant", reply)

        # Compress + split into segments; first part goes as the immediate
        # reply, remaining parts as follow-up sends via the adapter.
        reply = compress(reply)
        parts = split_sms(reply)
        with self.lock:
            self.stats["replies"] += len(parts)

        first = parts[0] if parts else "…"
        response = adapter.reply(inbound, first)
        # Send remaining parts as separate messages where the adapter can
        for extra in parts[1:]:
            try:
                adapter.reply(inbound, extra)
            except Exception:
                break
        return response

    # ── USSD pipeline ────────────────────────────────────────────────────
    def handle_ussd(self, adapter_name: str, body: bytes) -> dict:
        # Africa's Talking sends form-encoded: sessionId, serviceCode,
        # phoneNumber, text, networkCode
        try:
            form = urllib.parse.parse_qs(body.decode(errors="replace"))
            flat = {k: v[0] for k, v in form.items()}
        except Exception:
            return {"status": 400, "content_type": "text/plain", "body": "bad request"}

        sender = flat.get("phoneNumber", "")
        user_input = flat.get("text", "")
        session_id = flat.get("sessionId", "")

        state = self.ussd_state.get(session_id) or {
            "screen": "root",
            "flow": None,
            "buffer": "",
            "sender": sender,
        }
        self.ussd_state[session_id] = state

        def ask_fn(s: str, q: str) -> str:
            sess = self.sessions.get(s) or self.sessions.start(s)
            try:
                reply, _ = self.provider.chat(s, q, history=sess["history"])
            except ProviderError:
                reply = "Service error, please try again."
            self.sessions.append_history(s, sess, "user", q)
            self.sessions.append_history(s, sess, "assistant", reply)
            return compress(reply)

        response_text = self.ussd_engine.handle(state, user_input, ask_fn)
        # Africa's Talking expects a plain text body ending the session with
        # END, or continuing with CON.
        return {"status": 200, "content_type": "text/plain", "body": response_text}

    # ── Dashboard ────────────────────────────────────────────────────────
    def dashboard(self) -> str:
        with self.lock:
            s = dict(self.stats)
        active = self.sessions.active_count()
        budget = self.budget
        return (
            "<!doctype html><meta charset=utf-8><title>SMSaria</title>"
            "<style>body{font-family:system-ui;background:#0d1117;color:#e6edf3;"
            "padding:2rem}h1{color:#58a6ff}.n{color:#3fb950;font-weight:700;"
            "font-size:2rem}</style>"
            "<h1> SMSaria</h1><p>AI for any phone, over SMS and USSD.</p>"
            f"<p>Active sessions: <span class=n>{active}</span></p>"
            f"<p>Inbound: <span class=n>{s['inbound']}</span> &middot; "
            f"Replies: <span class=n>{s['replies']}</span> &middot; "
            f"Errors: <span class=n>{s['errors']}</span> &middot; "
            f"Denied: <span class=n>{s['denied']}</span></p>"
            f"<p>Global tokens today: <span class=n>{budget._global}</span> / "
            f"{budget.global_daily}</p>"
        )


def make_handler(gateway: Gateway) -> type:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # quiet default access log
            pass

        def _send(self, status: int, content_type: str, body: str) -> None:
            data = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):  # noqa: N802
            if self.path == "/health":
                with gateway.lock:
                    stats = dict(gateway.stats)
                self._send(200, "application/json", json.dumps({"ok": True, **stats}))
            elif self.path == "/":
                self._send(200, "text/html", gateway.dashboard())
            else:
                self._send(404, "text/plain", "not found")

        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", 0) or 0)
            body = self.rfile.read(length)
            parts = self.path.strip("/").split("/")
            if len(parts) == 2 and parts[0] == "sms":
                result = gateway.handle_sms(parts[1], body)
            elif len(parts) == 2 and parts[0] == "ussd":
                result = gateway.handle_ussd(parts[1], body)
            else:
                result = {"status": 404, "content_type": "text/plain", "body": "not found"}
            self._send(result["status"], result["content_type"], result["body"])

    return Handler


def main() -> None:
    port = int(os.environ.get("SMSARIA_PORT", "8080"))
    gateway = Gateway()
    server = ThreadingHTTPServer(("0.0.0.0", port), make_handler(gateway))
    print(f"SMSaria listening on :{port} — AI for any phone.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
