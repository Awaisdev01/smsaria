# Reddit posts

## r/opensource (primary)

**Title:** I built an open-source alternative to the closed "AI over SMS" services — self-hosted, zero dependencies, works on any phone

**Body:**

There's a wave of services selling AI access over SMS to people in
Africa and South Asia who don't have internet — but they're all closed
platforms. The operator owns the number, sees every question, and
charges per message. I couldn't find a single open-source alternative
(0 results for "SMS LLM gateway" on GitHub), so I built one.

**SMSaria** — MIT, Python stdlib only (zero pip installs):

- Any SMS number becomes an AI service: Twilio, Africa's Talking, or a
  $15 USB GSM modem for zero API fees
- USSD support: users dial *123# and get menus — no internet, no typing
  skill, works on any handset ever made
- Real SMS engineering: GSM-7 vs UCS-2 detection (Urdu/Arabic answers
  drop to 70-char segments — get it wrong and you pay double or send
  garbage), sentence-boundary splitting with n/m prefixes
- Sessions with memory (follow-up questions work), per-number and
  global daily budget caps enforced before the AI is called
- Offline fallback: cached answers served when the provider is down or
  the budget is spent — never dead air
- Any OpenAI-compatible model: Groq free tier works, or llama.cpp on the
  same box for fully offline

Cost for a pilot: $0 (Groq free tier + GSM modem + a $5 VPS or even a
Raspberry Pi).

Repo: https://github.com/awaisdev5765/smsaria — README has rendered
walkthroughs of the farmer flow, USSD menus, and the dashboard. 21 tests
covering the codec, sessions, guardrails, USSD flows, and the offline
fallback lifecycle.

Looking for: people who want to run a pilot (school, clinic, farming
co-op), and anyone with field experience in SMS systems to tell me what
I got wrong.

## r/selfhosted

**Title:** SMSaria: self-host an AI assistant over SMS/USSD for any phone — zero dependencies, any OpenAI-compatible model

**Body:**

Most of us take it for granted that everyone can use ChatGPT. 2.6
billion people can't — no smartphone, no data plan. The commercial
solutions selling AI-over-SMS to them are closed.

SMSaria is a self-hosted gateway (Python stdlib only, no dependencies)
that turns an SMS number into an AI service:

- Webhook adapters for Twilio and Africa's Talking, or bridge a $15 USB
  GSM modem through gammu-smsd and pay nothing but the SIM plan
- USSD menus for feature phones (*123# → numbered options → AI answers)
- Per-sender and global daily token caps, enforced before the model is
  called, with a live usage dashboard
- Answers cached for offline fallback — provider down or budget spent?
  Closest cached answer is served instead of an error
- Point it at Groq (free tier), OpenAI, or llama-server on localhost for
  a fully offline deployment

`python -m smsaria.server` and you're listening on :8080. Repo:
https://github.com/awaisdev5765/smsaria (MIT, 21 tests, README with
screenshots).

## Comment templates for replies

- On "why not WhatsApp?": WhatsApp requires a smartphone + data + Meta's
  Business API terms. SMS/USSD reaches the phones WhatsApp can't — that
 's the entire point. WhatsApp support could be an adapter later.
- On "why SMS in 2026": basic-phone ownership is still billions of
  people; 2G networks remain the only universal reach in many markets.
  National SMS-AI rollouts (e.g. Ghana) show the demand is real.
- On safety: the default system prompt is guidance-only ("see a
  professional" for health/legal); caps stop abuse; you own the data
  because you host the server.
