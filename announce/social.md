# X / LinkedIn copy

## X thread (post Tue–Thu, 8–10am ET)

**Tweet 1 (hook):**
AI services are starting to reach farmers, students, and clinic patients
on basic phones across Africa and South Asia — but they're all closed
platforms. The operator owns the number, sees every question, charges
per message.

So I built the open-source alternative. 🧵

**Tweet 2 (the reveal):**
SMSaria: a self-hosted Python gateway that turns any phone number into an
AI service.

Zero dependencies. Runs on a $5 VPS or Raspberry Pi. MIT.

github.com/Awaisdev01/smsaria

**Tweet 3 (how it works):**
A farmer texts "my maize leaves have yellow spots" on a $15 keypad phone.
SMSaria:
→ receives it via Twilio / Africa's Talking / a USB GSM modem
→ asks any OpenAI-compatible model (Groq free tier works)
→ replies in the farmer's language, split into clean SMS segments

**Tweet 4 (USSD):**
And for phones without even texting skills: dial *123# → numbered menu →
type a question → AI answer. Same interaction as mobile-money, no data
connection at all. Works on every handset ever made.

**Tweet 5 (the hard part):**
SMS engineering nobody tells you about: Urdu/Arabic answers force UCS-2
encoding, dropping the segment limit from 160 to 70 chars. SMSaria
detects encoding, compresses, and splits at sentence boundaries with n/m
prefixes. Get this wrong → double cost or garbled text.

**Tweet 6 (guardrails + offline):**
Serving a community? One curious user can burn your whole API budget.
Per-sender daily caps + global caps, enforced BEFORE the model is called.

Provider down? Budget spent? Closest cached answer served — never dead
air.

**Tweet 7 (cost + CTA):**
Pilot cost: $0. Groq free tier + a $15 GSM dongle + the SIM plan you
already have.

If you work with an NGO, school, or clinic that could use this — the
README has a 5-minute setup:
github.com/Awaisdev01/smsaria

⭐ PRs welcome, especially new gateway adapters.

## LinkedIn post

**2.6 billion people can't use ChatGPT. The services "solving" this are
closed platforms. I built the open-source alternative.**

This week I open-sourced SMSaria: a Python gateway that gives any phone —
including $15 feature phones with no internet — access to AI over SMS
and USSD.

Why it matters: national-scale SMS-AI rollouts are starting across
Africa, but every existing platform is proprietary. The operator owns
the number, sees every question, and charges per message. Communities
deserve the option to own their own.

What it does:
- Any SMS number → AI service (Twilio, Africa's Talking, or a $15 GSM
  modem — the zero-API-fee path)
- USSD menus for feature phones: *123# → menu → AI answer, no data needed
- Cost guardrails enforced before the AI is called (per-sender + global
  daily caps)
- Offline fallback: cached answers when the provider is down
- Any OpenAI-compatible model — Groq free tier works, or llama.cpp for
  fully offline

Zero dependencies (Python stdlib only), MIT, 21 tests, deploys on a $5
VPS or Raspberry Pi.

If you work in digital inclusion, ICT4D, or education access — I'd
genuinely like to hear what deployment would help your community. Repo
and full docs in the comments.

#opensource #digitalinclusion #ICT4D #AI #SMS

## Short-form (comment replies / groups)

- "Built an open-source alternative to the closed AI-over-SMS services:
  self-hosted, zero deps, works on any phone. MIT. github.com/Awaisdev01/smsaria"
- "The GSM-7/UCS-2 segment math in non-Latin scripts is the part everyone
  gets wrong — I wrote the codec so NGOs don't have to."
