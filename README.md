# 📡 SMSaria

**AI for any phone — an open-source gateway that turns a phone number into an AI service.**

2.6 billion people still use basic phones with no data plan. Across Africa,
South Asia, and rural America, SMS works where the internet doesn't — and AI
services are starting to reach those users only through **closed,
proprietary platforms**.

SMSaria is the missing open-source piece: a **zero-dependency Python
gateway** that any NGO, school, clinic, or developer can run to give their
community AI over **SMS and USSD** — on a $5 VPS, a Raspberry Pi, or even
fully offline with llama.cpp.

```
$ python -m smsaria.server
SMSaria listening on :8080 — AI for any phone.

# A farmer texts: "my maize leaves have yellow spots"
# → AI answers in their language, split over SMS segments:
1/2 Yellow spots on maize leaves usually mean leaf rust or
maize streak virus. Check these two signs: 1) powdery brown
2/2 pustules wipe off = rust, treat with fungicide; 2) yellow
stripes stunting growth = streak virus, remove infected plants.
```

## Why SMSaria

| | Closed services | SMSaria |
|---|---|---|
| Who owns the number | The vendor | **You** |
| Data flows through | Their cloud | **Your server** |
| Cost | Per-message fees | **Your provider's rates** (Groq free tier works) |
| Model | Fixed | **Any OpenAI-compatible** (Groq, Claude, local llama.cpp) |
| Customization | None | **Menus, prompts, languages, guardrails** |
| Deployment | Sign-up + approval | **`python -m smsaria.server`** |

## What's inside

- **Webhook adapters** — Twilio, Africa's Talking, and a raw JSON adapter
  (bridgeable to `gammu-smsd` + a $15 USB GSM modem for the zero-API-fee path)
- **SMS codec** — GSM-7/UCS-2 aware splitting (160/70-char limits), sentence-
  boundary cuts, compression that keeps text readable on a 2G screen
- **Session engine** — per-number rolling history with TTL, so follow-up
  questions like "and for children?" work
- **USSD engine** — menu-tree DSL for interactive sessions on feature phones
  (`*123#` → menus → AI questions), no data connection needed at all
- **Cost guardrails** — per-sender daily caps + global daily cap + max tokens
  per reply, with a real-time usage dashboard
- **Language handling** — script-based hints (Arabic/Urdu, Hindi, Swahili)
  steer the model to answer in the sender's language

Zero third-party dependencies. Python 3.9+ standard library only.

## Quick start

```bash
git clone https://github.com/awaisdev5765/smsaria.git
cd smsaria

export SMSARIA_PROVIDER_BASE="https://api.groq.com/openai/v1"
export SMSARIA_PROVIDER_KEY="gsk_..."          # Groq free tier is fine
export SMSARIA_MODEL="llama-3.1-8b-instant"

python -m smsaria.server                        # :8080
```

Point your gateway's inbound webhook at `http://YOUR_HOST:8080/sms/twilio`
(or `/sms/africastalking`, or `/sms/raw` for custom bridges) and text your
number. Full deployment guide: [docs/DEPLOY.md](docs/DEPLOY.md).

## USSD on feature phones

SMS needs the user to compose a message; USSD gives them a **menu**:

```
*123# →  Welcome to AI Help
        1. Ask any question
        2. Farming tips
        3. Health basics
```

Menus are plain dicts/JSON — see `smsaria/ussd/engine.py`. The `ask` flow
collects the question across USSD screens and returns the AI answer. USSD
works on every handset ever made, with no data at all.

## Architecture

```
Feature phone ──SMS/USSD──▶ Gateway (Twilio / Africa's Talking / GSM modem)
                                 │
                                 ▼
                        SMSaria (this server)
                        ├─ adapter: normalize webhook
                        ├─ sessions: history, TTL, language
                        ├─ budget: per-number + global caps
                        ├─ provider: any OpenAI-compatible endpoint
                        └─ sms codec: compress + split at word/sentence bounds
                                 │
                                 ▼
                        Reply segments back to the phone
```

## Real-world use cases

- **Farmers**: crop disease triage, planting calendars, market prices
- **Students**: study help on exam curricula, in their language
- **Clinics**: medication scheduling reminders and basic health guidance
  (with conservative prompts — not a diagnosis tool)
- **Disaster response**: offline knowledge cards served without AI when the
  LLM is unreachable — the gateway degrades to cached info, never dead air

## Tested

19 tests cover the SMS codec (GSM-7 vs UCS-2 splitting, word boundaries,
prefixes), sessions (TTL, bounded history), budget guardrails (per-sender,
global, daily roll), and the full USSD flow (menus, ask flow, cancel,
invalid options, info cards). End-to-end: webhook → AI → reply, and the
complete USSD menu→ask→answer cycle, verified over live HTTP.

## Safety

- The gateway is a conduit: screen prompts for medical/legal topics, set
  caps, and log usage via the dashboard.
- USSD shortcodes are regulated in most markets — apply through your
  gateway provider.
- Never commit provider keys; config is env-only.

## License

MIT — see [LICENSE](LICENSE).
