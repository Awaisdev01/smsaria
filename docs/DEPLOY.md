# Deploying SMSaria

## 1. Get an SMS number

- **Twilio**: buy a number, set the inbound webhook to `http://YOUR_HOST:8080/sms/twilio`
- **Africa's Talking**: create a shortcode, set the incoming-message callback to
  `http://YOUR_HOST:8080/sms/africastalking`, and the USSD callback to
  `http://YOUR_HOST:8080/ussd/africastalking`. USSD shortcodes require an
  application with your national regulator in most African markets.
- **Free/low-cost**: run `gammu-smsd` against a USB GSM modem (a $15 dongle +
  SIM) and forward received messages to `/sms/raw` with a small shim script.
  This is the zero-API-fee path for community deployments.

## 2. Configure the AI provider

Any OpenAI-compatible endpoint works:

```bash
export SMSARIA_PROVIDER_BASE="https://api.groq.com/openai/v1"
export SMSARIA_PROVIDER_KEY="gsk_..."
export SMSARIA_MODEL="llama-3.1-8b-instant"
```

Groq's free tier is enough for a pilot serving a school or clinic.
For full offline, run llama.cpp's `llama-server` on the same box and point
`SMSARIA_PROVIDER_BASE` at `http://127.0.0.1:8080/v1`.

## 3. Set guardrails

```bash
export SMSARIA_PER_SENDER_DAILY=20   # tokens per number per day
export SMSARIA_GLOBAL_DAILY=2000     # total per day
```

## 4. Run

```bash
python -m smsaria.server          # listens on :8080
```

Keep it alive with systemd:

```ini
[Unit]
Description=SMSaria
After=network.target

[Service]
ExecStart=/usr/bin/python3 -m smsaria.server
Restart=always
Environment=SMSARIA_PROVIDER_BASE=https://api.groq.com/openai/v1
Environment=SMSARIA_PROVIDER_KEY=gsk_...
Environment=SMSARIA_MODEL=llama-3.1-8b-instant

[Install]
WantedBy=multi-user.target
```

## 5. Test from your phone

Text anything to your number. You should get a reply within seconds.

## Safety notes

- Never put the provider key in a public repo; the gateway reads it from env.
- USSD shortcodes are regulated in most countries — apply through your gateway.
- Set conservative caps until you know your traffic; the dashboard (`/`) shows
  token usage in real time.
