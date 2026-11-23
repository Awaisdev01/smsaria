# Show HN — SMSaria

## Title (pick one)
1. Show HN: SMSaria – open-source gateway that gives any phone AI over SMS and USSD
2. Show HN: I built an open-source alternative to the closed SMS-AI services (runs on a $5 VPS)
3. Show HN: SMSaria – AI for the 2.6B people on basic phones, self-hosted, zero dependencies

**Recommended: #1** — says what it is in one line, no hype.

## First comment (post immediately after submitting)

Hi HN! I built SMSaria because of a frustration: AI is starting to reach
people without internet — farmers, students, clinic patients on basic
phones — but only through closed platforms. The operator owns the number,
sees every question, and charges per message. When I looked for an
open-source alternative, there wasn't one (searches for "SMS LLM gateway"
and "USSD LLM" returned nothing but empty repos).

SMSaria is the missing piece: a Python gateway you self-host that turns any
SMS number into an AI service, with USSD support for feature phones.

Architecture decisions worth discussing:

- **Zero dependencies.** Python 3.9+ stdlib only (http.server, sqlite3,
  urllib). The whole point is that an NGO volunteer can deploy it on a $5
  VPS or a Raspberry Pi without auditing a dependency tree. Everything —
  the Twilio/Africa's Talking adapters, the USSD engine, the budget
  guardrails — is small, readable code.

- **SMS is harder than it looks.** A 480-character Urdu answer is not one
  SMS: Urdu/Arabic force UCS-2 encoding, which drops the segment limit from
  160 to 70 chars. SMSaria detects encoding per reply, compresses, and
  splits at sentence boundaries with 1/3, 2/3 prefixes. Get this wrong and
  replies cost double or arrive garbled.

- **USSD is the sleeper feature.** Dialing *123# gives a numbered menu —
  the same interaction model as mobile-money, which hundreds of millions
  of people already know. No typing skill needed, no data at all. The menu
  engine is a JSON tree; the "ask" flow collects a question across screens.

- **Guardrails fire before the model is called.** Per-sender daily cap,
  global daily cap, max reply tokens. One curious user can't burn the
  community's budget.

- **Never dead air.** Successful answers are cached; if the LLM provider is
  down or the daily budget is spent, the closest cached answer is served,
  marked "(offline answer)". This matters for disaster-response use.

- **Any model.** Anything speaking /v1/chat/completions: Groq's free tier
  works for pilots; llama-server on the same box makes it fully offline.

Cost math for a pilot: Groq free tier + a $15 USB GSM modem (via
gammu-smsd) = $0 running cost, just the SIM plan. With Africa's Talking at
~$0.01/SMS, a 100-message day is about a dollar.

Repo: https://github.com/Awaisdev01/smsaria (README has screenshots of
the farmer flow, USSD menus, and the dashboard; 21 tests; MIT).

What I'd love feedback on: the adapter interface (are there gateways I
should support?), the fallback matching threshold, and — most of all —
from anyone who has deployed SMS systems in the field: what breaks first?
