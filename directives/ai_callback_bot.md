# AI Callback Bot — Setup & Operations

## Goal
Give OneVision Marketing (and its clients) an AI voice bot that calls new leads within 60 seconds of form submission, qualifies them, and books them into a calendar — automatically.

**Why this matters:** Responding to a lead within 60 seconds increases conversion by **391%** vs. responding in an hour. Most agencies never call leads back at all.

**Also resellable:** This system can be white-labeled and sold to real estate, restaurant, contractor, and salon clients as a $200-500/mo AI receptionist add-on.

---

## Files
- `execution/ai_callback_bot.py` — Main script (CLI + webhook server)
- `execution/ai_callback_prompts.py` — Prompt library for each industry/use case
- `directives/ai_callback_bot.md` — This file

## Prompts Currently Available
- `onevision_marketing` — Own agency lead qualifier (books strategy calls)
- `akira_buyer` — Real estate buyer lead qualifier
- `akira_seller` — Real estate seller / home valuation callback
- `restaurant` — Reservation / event inquiry callback
- `contractor` — Quote request qualifier + estimate booking
- `salon` — Simple appointment booking

Run `python execution/ai_callback_bot.py --list-prompts` to see all.

---

## Step 1 — Sign Up for Bland.ai (5 min)

Bland.ai is the recommended provider — cheapest, easiest, most reliable.

1. Go to **https://www.bland.ai**
2. Sign up (they give free credits to start)
3. Get your API key from the dashboard
4. Add to `.env`:
   ```
   BLAND_API_KEY=your_key_here
   ```

**Cost:** ~$0.09/minute. A 3-min qualifying call = $0.27. A 30-second voicemail = $0.05.

**Voice options:** Bland has 20+ voices. Default is "maya" (warm professional female). Others:
- `nat` (natural male)
- `paige` (young professional female)
- `evelyn` (mature warm female)

Change with `BLAND_VOICE_ID=nat` in `.env`.

---

## Step 2 — Install Dependencies

```bash
pip install flask requests
```

---

## Step 3 — Test a One-Off Call

Call yourself right now to test it:

```bash
python execution/ai_callback_bot.py \
  --phone "+15551234567" \
  --name "Isaiah" \
  --prompt onevision_marketing
```

Your phone should ring within 15-30 seconds with the AI agent on the line.

---

## Step 4 — Run as Webhook Server

For real production use, run it as a webhook server that any form submission can trigger:

```bash
python execution/ai_callback_bot.py --serve --port 5000
```

Endpoints:
- `POST /webhook/lead` — trigger a callback (called by your forms)
- `POST /webhook/lead-result` — receives call results from Bland
- `GET /health` — status check
- `GET /test` — HTML test page

---

## Step 5 — Deploy It (So It's Always Running)

**Option A: Same server as your CRM (Render/Railway/etc.)**
Add this as a second service alongside your leadgen app. Uses the same repo.

**Option B: Standalone deploy**
- Push repo to GitHub
- Deploy to **Render** (free tier works) or **Railway** ($5/mo)
- Set env var `BLAND_API_KEY`
- Set start command: `python execution/ai_callback_bot.py --serve --port $PORT`

**Option C: Local + ngrok (for testing)**
```bash
python execution/ai_callback_bot.py --serve --port 5000
ngrok http 5000
```
Use the ngrok URL as your webhook endpoint temporarily.

---

## Step 6 — Connect to Your Lead Sources

### From your website form
POST JSON to `https://your-server.com/webhook/lead`:

```json
{
  "name": "Jane Smith",
  "phone": "+15551234567",
  "email": "jane@example.com",
  "prompt": "onevision_marketing"
}
```

HTML form example:
```html
<form onsubmit="submitLead(event)">
  <input name="name" required>
  <input name="phone" required>
  <input name="email" type="email" required>
  <button>Get Free Audit</button>
</form>
<script>
async function submitLead(e) {
  e.preventDefault();
  const fd = new FormData(e.target);
  const body = {prompt: "onevision_marketing"};
  fd.forEach((v,k) => body[k] = v);
  await fetch("https://your-server.com/webhook/lead", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body)
  });
  alert("Thanks! We'll call you in the next 60 seconds.");
}
</script>
```

### From Facebook Lead Ads
1. Sign up for **Zapier** (free tier works) or **Make.com**
2. Trigger: New Facebook Lead
3. Action: Webhook POST to `https://your-server.com/webhook/lead`
4. Map: full_name → name, phone_number → phone

### From GoHighLevel
1. In GHL, go to Automations → Create workflow
2. Trigger: Form Submitted
3. Action: Webhook → POST to your callback URL
4. Map GHL fields to the webhook payload

### From Google Business Profile / other
Any tool that supports webhooks (Zapier, Make, Pabbly) can pipe leads in.

---

## Step 7 — Configure Result Webhook (Optional but Recommended)

So you know what happened on each call, tell Bland.ai to POST results back:

1. Go to Bland dashboard → Webhooks
2. Add: `https://your-server.com/webhook/lead-result`
3. Enable "Call Completed" events

Results are saved to `clients/aventisai/callback_results.json` with:
- Full transcript
- Call duration
- Summary
- Whether they booked

---

## Reselling to Clients

Once you have this working for OneVision, sell it as an add-on to your marketing clients:

### Pricing Suggestions
| Client Type | Positioning | Price |
|-------------|-------------|-------|
| Real Estate Agent | "AI receptionist — never miss a buyer or seller lead" | $299/mo |
| Restaurant | "AI hostess for reservations and events" | $199/mo |
| Contractor | "AI estimator that qualifies quote requests 24/7" | $299/mo |
| Salon/Barber | "AI booking assistant that never sleeps" | $149/mo |
| General SMB | "AI SDR — instant callback for every form submission" | $250-500/mo |

**Your cost per client:** ~$20-50/mo in Bland credits (they don't need many calls to break even).

**Margin:** 80-95%.

### How to Sell It
1. Show the client the demo (call them from your test setup)
2. Frame it as "We give you an AI receptionist for less than a part-time employee"
3. Bundle with your marketing services — it makes ads convert 3-5x better
4. Onboard by adding their prompt to `ai_callback_prompts.py` and their webhook URL

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `BLAND_API_KEY not set` | Add key to `.env` or export it |
| Phone number rejected | Must be E.164 (`+1XXXXXXXXXX`) or US 10-digit |
| Call never happens | Check Bland dashboard for account balance / errors |
| AI sounds robotic | Try a different voice (`BLAND_VOICE_ID=paige`) |
| Bot cuts off mid-sentence | Increase `max_duration` in prompt config |
| Bot doesn't book | Update the system prompt to be more explicit about booking |

---

## Metrics to Track

Log everything and review weekly:
- **Callback rate:** % of leads that answered
- **Qualification rate:** % of answered calls that qualified as good leads
- **Booking rate:** % of qualified leads that booked a call
- **Cost per booking:** Total Bland cost / bookings created

Target benchmarks:
- Answer rate: 40-60%
- Qualification rate: 60-80%
- Booking rate: 40-60% of qualified
- Cost per booking: $2-8

At OneVision Marketing pricing (~$500-$1,200/mo clients), a $5 booking cost that closes at 20-30% = **$100-500 ROI per lead**.

---

## Next Steps

1. Sign up for Bland.ai
2. Test a call to yourself
3. Deploy the webhook server
4. Connect ONE lead source (start with your website form)
5. Monitor the first 20 calls, refine the prompt
6. Roll out to Facebook Lead Ads
7. Sell it as a service to Akira and other clients
