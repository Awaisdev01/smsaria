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
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .adapters.webhooks import ADAPTERS, AfricasTalkingAdapter, RawAdapter
from .gateway.sessions import SessionStore
from .gateway.sms import compress, split_sms
from .providers.fallback import AnswerCache
from .providers.openai_compat import (
    Budget,
    BudgetDenied,
    OpenAICompatibleProvider,
    ProviderError,
)
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
        self.cache = AnswerCache(cfg.get("SMSARIA_CACHE_DB", "smsaria_cache.db"))
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
        self.stats = {
            "inbound": 0, "replies": 0, "errors": 0, "denied": 0,
            "offline": 0,
        }
        self.recent = []      # last queries for the dashboard
        self.languages = {}   # hint -> count
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
        hint = detect_language_hint(text)
        with self.lock:
            self.stats["inbound"] += 1
            self.languages[hint] = self.languages.get(hint, 0) + 1
            self.recent.insert(
                0,
                {
                    "time": time.strftime("%H:%M:%S"),
                    "sender": sender[:6] + "…" + sender[-4:] if len(sender) > 12 else sender,
                    "text": text[:60],
                    "lang": hint,
                },
            )
            del self.recent[10:]
        sess = self.sessions.get(sender) or self.sessions.start(sender)
        # Per-message prompt: fill the {language_hint} slot without mutating
        # the template stored on the provider.
        prompt_template = self.provider.system_prompt
        self.provider.system_prompt = prompt_template.replace(
            "{language_hint}", hint
        )
        try:
            reply, tokens = self.provider.chat(
                sender, text, history=sess["history"]
            )
            # Success: seed the offline fallback cache with this answer.
            if tokens > 0:
                self.cache.record(text, reply)
        except BudgetDenied as e:
            with self.lock:
                self.stats["denied"] += 1
                if self._fallback(text):
                    self.stats["offline"] += 1
            reply = self._fallback(text) or str(e)
        except ProviderError as e:
            with self.lock:
                self.stats["errors"] += 1
                if self._fallback(text):
                    self.stats["offline"] += 1
            reply = self._fallback(text) or "Service error, please try again shortly."
        finally:
            self.provider.system_prompt = prompt_template

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

    # ── Offline fallback ─────────────────────────────────────────────────
    def _fallback(self, question: str):
        """Closest cached answer for this question, marked as offline."""
        cached = self.cache.find(question)
        if cached is None:
            return None
        return "(offline answer) " + cached

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
            recent = list(self.recent)
            langs = dict(self.languages)
        active = self.sessions.active_count()
        budget = self.budget
        pct = min(100, int(budget._global * 100 / max(1, budget.global_daily)))

        def esc(t: str) -> str:
            return (t.replace("&", "&amp;").replace("<", "&lt;")
                     .replace(">", "&gt;").replace('"', "&quot;"))

        rows = "".join(
            f"<tr><td class=m>{esc(r['time'])}</td><td class=m>{esc(r['sender'])}</td>"
            f"<td>{esc(r['text'])}</td><td class=m>{esc(r['lang'])}</td></tr>"
            for r in recent
        ) or '<tr><td colspan=4 class=m>No messages yet — text your number.</td></tr>'
        lang_chips = " ".join(
            f'<span class=chip>{esc(k)}: {v}</span>' for k, v in langs.items()
        ) or '<span class=chip>muted: none yet</span>'

        return f'''<!doctype html><meta charset=utf-8>
<title>SMSaria</title>
<style>
body{{font-family:system-ui,sans-serif;background:#0d1117;color:#e6edf3;
  margin:0;padding:2rem;max-width:860px}}
h1{{color:#58a6ff;font-size:1.6rem;margin:0 0 .2rem}}
.sub{{color:#8b949e;margin:0 0 1.5rem;font-size:.95rem}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));
  gap:.8rem;margin-bottom:1.5rem}}
.card{{background:#161b22;border:1px solid #30363d;border-radius:10px;
  padding:.9rem 1rem}}
.card .n{{color:#3fb950;font-weight:700;font-size:1.9rem}}
.card .warn .n{{color:#f0883e}}
.card .err .n{{color:#f85149}}
.card .lbl{{color:#8b949e;font-size:.8rem;margin-top:.2rem}}
.bar{{background:#161b22;border:1px solid #30363d;border-radius:10px;
  padding:1rem;margin-bottom:1.5rem}}
.track{{background:#21262d;border-radius:6px;height:10px;overflow:hidden;
  margin-top:.5rem}}
.fill{{background:linear-gradient(90deg,#2f81f7,#3fb950);height:100%;width:{pct}%}}
.chips{{margin:0 0 1.5rem}}
.chip{{display:inline-block;background:#161b22;border:1px solid #30363d;
  border-radius:99px;padding:.25rem .8rem;font-size:.8rem;margin:0 .4rem .4rem 0;
  color:#79c0ff}}
table{{width:100%;border-collapse:collapse;background:#161b22;
  border:1px solid #30363d;border-radius:10px;overflow:hidden}}
th{{text-align:left;color:#8b949e;font-size:.75rem;text-transform:uppercase;
  letter-spacing:.05em;padding:.6rem .9rem;border-bottom:1px solid #30363d}}
td{{padding:.55rem .9rem;border-bottom:1px solid #21262d;font-size:.85rem}}
td.m{{color:#8b949e;font-family:ui-monospace,monospace;font-size:.78rem;
  white-space:nowrap}}
tr:last-child td{{border-bottom:none}}
</style>
<h1>📡 SMSaria</h1>
<p class=sub>AI for any phone, over SMS and USSD — live usage</p>
<div class=cards>
<div class=card><div class=n>{active}</div><div class=lbl>active sessions</div></div>
<div class=card><div class=n>{s['inbound']}</div><div class=lbl>inbound messages</div></div>
<div class=card><div class=n>{s['replies']}</div><div class=lbl>reply segments sent</div></div>
<div class="card warn"><div class=n>{s['offline']}</div><div class=lbl>offline cache hits</div></div>
<div class="card err"><div class=n>{s['errors']}</div><div class=lbl>provider errors</div></div>
<div class="card err"><div class=n>{s['denied']}</div><div class=lbl>cap denials</div></div>
</div>
<div class=bar><b>Daily token budget</b>
{budget._global:,} / {budget.global_daily:,} ({pct}%)
<div class=track><div class=fill></div></div></div>
<p class=chips><b style="color:#8b949e;font-size:.8rem">LANGUAGES SEEN:</b> {lang_chips}</p>
<table>
<tr><th>time</th><th>sender</th><th>question</th><th>language</th></tr>
{rows}
</table>'''


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
