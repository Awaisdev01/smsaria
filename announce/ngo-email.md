# NGO / digital-inclusion outreach email

## Subject options
1. Open-source AI over SMS for your programs — self-hosted, no platform lock-in
2. Give your community AI access on basic phones (open source, MIT)

## Body

Hi [Name],

I'm reaching out because [org] works in [region/access-to-information],
and there's a gap I've been working to close.

Across the programs I've read about, the communities you serve include
people on basic phones — no smartphone, no data plan. AI services are
starting to reach these users over SMS, but the existing platforms are
closed: the vendor owns the phone number, every question flows through
their cloud, and every message is billed through them.

I've open-sourced the alternative: **SMSaria** (MIT license,
github.com/awaisdev5765/smsaria) — a small Python gateway that any
organization can self-host to give its community AI over SMS and USSD:

- **Works on any phone.** SMS for texting; USSD menus (*123#) for
  feature-phone users — no app, no data, no account.
- **You own it.** The number, the data, the guardrails. Nothing flows
  through a vendor's cloud.
- **Cheap to run.** Groq's free AI tier + a $15 USB GSM modem ≈ $0/month
  for a pilot. Or Africa's Talking at roughly $0.01 per message.
- **Guardrails built in.** Per-person and service-wide daily limits are
  enforced before the AI is ever called, with a live usage dashboard.
- **Never dead air.** If the AI provider is unreachable, previously
  cached answers are served so the service keeps working.

Programs it's designed for: farming cooperatives (crop triage, market
prices), schools (study help in students' own languages), clinics
(medication schedule guidance with guidance-only prompts), and
emergency information.

The README has a 5-minute setup guide and screenshots of exactly what
users see. I'd be glad to help your team run a pilot in one program
area — including the USSD shortcode application process, which I know
is the slow part in most markets.

Would a 20-minute call next week be useful?

Best,
[Your name]
[GitHub: awaisdev5765]

## P.S. for health programs
The default system prompt is guidance-only ("see a professional for
diagnosis") and can be tightened further per program.
