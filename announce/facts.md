# SMSaria — verified facts for launch copy

## The product
- Open-source SMS/USSD gateway that turns a phone number into an AI service
- Zero third-party dependencies — Python 3.9+ stdlib only (http.server, sqlite3, urllib)
- MIT license, repo: https://github.com/awaisdev5765/smsaria
- 21/21 tests; end-to-end verified over live HTTP (SMS webhook→AI→reply, USSD menu→ask→answer)

## Capabilities
- Webhook adapters: Twilio, Africa's Talking, raw JSON (bridgeable to gammu-smsd + $15 USB GSM modem)
- GSM-7/UCS-2 aware codec: 160/70-char segments, sentence-boundary splitting, n/m prefixes, compression
- Session engine: per-number history, 10-min TTL, bounded turns — follow-up questions work
- USSD menu engine: JSON menu trees, ask-flows, cancel (00), info cards; works on any handset ever made
- Cost guardrails BEFORE the AI is called: per-sender daily cap, global daily cap, max reply tokens
- Offline fallback: successful answers cached (sqlite, Jaccard ≥0.5 match); served marked "(offline answer)" when provider is down or budget spent — never dead air
- Language hints: Arabic/Urdu script, Devanagari, Swahili keywords → model answers in sender's language
- Live dashboard at /: sessions, counts, token usage vs cap

## Cost math
- Groq free tier + GSM modem = $0 running cost for a pilot
- Africa's Talking ~$0.01/SMS → 100-message day ≈ $1/day
- Any OpenAI-compatible endpoint: Groq, OpenAI, Claude, local llama.cpp (fully offline)

## The market context (why now)
- ~2.6 billion people use basic phones with no data plan (GSMA mobile-gap figures)
- AI services reaching these users are closed/proprietary: operator owns the number, sees every question, charges per message
- National-scale SMS-AI rollouts are starting in Africa (e.g. Ghana) — but no open-source gateway existed
- GitHub searches for "SMS LLM gateway" / "USSD LLM" returned only 0★ repos before smsaria

## Deployment scenarios (README table)
- Farming cooperatives: crop triage, planting calendars, market prices
- Schools: study help in the student's language
- Clinics: medication schedule guidance (guidance-only prompts, not diagnosis)
- Disaster response: offline cache serves answers even when the LLM is unreachable

## Honest limitations (use if asked)
- USSD shortcodes are regulator-approved in most markets — apply through your gateway
- Health/legal answers need conservative prompts (default prompt already says "guidance only, see a professional")
- Sessions are in-memory; multi-process persistence is on the roadmap (SQLite cache exists for fallback)
- Question length capped (~400 chars) for USSD flows
