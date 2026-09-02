# GHL Workflow AI — Build Prompt: Voice-Only Voicemail Drop

**One Vision Marketing Agency · Isaiah Wright**
Companion to `voicemail-drop-campaign.md` → *Voice-Only Build*.

Paste **Prompt A** into GoHighLevel's Workflow AI Assistant. Then verify the
result against the **Build Spec** below, because the AI reliably gets two or
three things wrong every time.

**The AI cannot upload your audio.** Recording and attaching the three MP3s is
always manual, no matter how good the prompt is. Everything else it can build.

---

## Before you paste

Have these ready or the build stalls halfway:

| Item | Value |
|---|---|
| Audio files | 4 × MP3 or WAV, **64 kbps**, 22–30 sec each |
| File names | `VM-Drop-1.mp3` … `VM-Drop-4.mp3` |
| Phone number | Connected under Settings → Phone Numbers |
| Entry tag | `vm-drop` |
| Completion tag | `vm-drop-complete` |
| Responder tag | `warm-lead` |

**Cadence:** Day 1 → Day 8 → Day 18 → Day 32. Roughly five weeks end to end.
Spacing this wide is deliberate — a voicemail every three days from the same
company reads as pressure, and the close-out only lands if enough time has
passed that it feels like a real decision rather than a tactic.

Upload the audio first: **Marketing → Voicemails** (or Media Library, depending
on your version). Naming them exactly as above lets you select them by name
instead of hunting through a list.

---

## PROMPT A — paste this into Workflow AI

```
Create a workflow named: VM Drop — Callback

PURPOSE
Send four pre-recorded ringless voicemail drops to a list of leads across
roughly five weeks. This is a voice-only campaign. Do NOT add any SMS actions,
email actions, or internal messages to the contact. Voicemail is the only
outbound channel.

TRIGGER
Type: Contact Tag
Condition: Tag Added
Tag: vm-drop
No additional filters.

ACTIONS — build in exactly this order:

Step 1 — Voicemail
  Audio file: VM-Drop-1
  First touch. Fires immediately on entry. (Day 1)

Step 2 — Wait
  Duration: 7 days

Step 3 — Voicemail
  Audio file: VM-Drop-2
  (Day 8)

Step 4 — Wait
  Duration: 10 days

Step 5 — Voicemail
  Audio file: VM-Drop-3
  (Day 18)

Step 6 — Wait
  Duration: 14 days

Step 7 — Voicemail
  Audio file: VM-Drop-4
  Final touch — the close-out. (Day 32)

Step 8 — Wait
  Duration: 2 days

Step 9 — Remove Contact Tag
  Tag: vm-drop

Step 10 — Add Contact Tag
  Tag: vm-drop-complete

WORKFLOW SETTINGS
Allow Re-Entry: OFF
Stop on Response: ON — enable for every available channel, including
  inbound call and inbound SMS
Sending Window: 9:00 AM to 7:00 PM
Timezone: Contact's timezone (not account timezone)
Excluded days: Sunday

DO NOT ADD
- No SMS actions of any kind
- No email actions
- No "if/else" branches
- No AI or conversation actions
- No appointment or calendar actions

Keep the workflow linear: trigger, then the ten steps above in order. Do not
shorten the wait durations — the long gaps are intentional.
```

---

## Build Spec — verify the AI's output against this

Open the generated workflow and check every row. Fix anything that does not
match.

### Trigger

| Field | Must be |
|---|---|
| Trigger type | Contact Tag |
| Event | Tag Added |
| Tag | `vm-drop` |
| Filters | none |

### Action sequence

| # | Action | Config | Day | Common AI error |
|---|---|---|---|---|
| 1 | Voicemail | `VM-Drop-1` | 1 | Substitutes a Call action — replace it |
| 2 | Wait | **7 days** | | Shortens it, or sets hours instead of days |
| 3 | Voicemail | `VM-Drop-2` | 8 | Reuses Drop 1's file |
| 4 | Wait | **10 days** | | Shortens it |
| 5 | Voicemail | `VM-Drop-3` | 18 | Reuses Drop 1's file |
| 6 | Wait | **14 days** | | Shortens it |
| 7 | Voicemail | `VM-Drop-4` | 32 | Drops the fourth step entirely |
| 8 | Wait | 2 days | | — |
| 9 | Remove Tag | `vm-drop` | | Removes the wrong tag |
| 10 | Add Tag | `vm-drop-complete` | | Skipped entirely |

**Check the wait durations specifically.** The assistant compresses long gaps
toward a "typical" 2–3 day cadence unless you correct it. Every wait above is
deliberate.

### Settings tab

| Setting | Must be | Why it matters |
|---|---|---|
| Allow Re-Entry | **Off** | A re-imported contact gets the whole sequence twice |
| Stop on Response | **On, all channels** | This is your exit condition |
| Sending Window | 9:00 AM – 7:00 PM | A 2am voicemail reads as spam |
| Timezone | **Contact's timezone** | Defaults to account timezone — always fix this |
| Excluded days | Sunday | — |

---

## The three things the AI gets wrong most often

**1. It builds a Call action instead of a Voicemail action.**
These are different. A Call action dials and rings the phone. Voicemail deposits
without ringing. If your workflow shows "Call," delete the node, click **+**,
and scroll *past* the common actions to find **Voicemail** near the bottom of
the list.

**2. Timezone defaults to the account, not the contact.**
Nearly every generated workflow has this wrong. With a MA/RI-only list the
practical difference is zero, but it silently breaks the send window the moment
you add a lead outside Eastern.

**3. Stop on Response is left off.**
This is your entire exit condition. Without it, a lead who calls you back on
day 2 still receives the "last one from me" close-out on day 9 — after you have
already spoken. That single miss undoes more deals than a weak script does.

---

## If Workflow AI cannot find the Voicemail action

Some sub-accounts do not expose Voicemail to the AI builder. Build it by hand —
it is a six-minute job:

1. **Automation → Workflows → + Create Workflow → Start from Scratch**
2. Name it `VM Drop — Callback`
3. **Add Trigger** → *Contact Tag* → Tag Added → `vm-drop`
4. Click **+** → **scroll down past the common actions** → **Voicemail** →
   select `VM-Drop-1`
5. Repeat for the Wait and Voicemail nodes down the Build Spec table
6. **Settings tab** → apply the four settings above
7. **Publish** (toggle top right — a saved-but-unpublished workflow never fires)

---

## Loading the list

1. **Contacts → Import**
2. CSV with columns `First Name` and `Phone`. Add `Company` if you have it.
3. On the import screen, **apply tag `vm-drop` to the entire batch**
4. Finish

The tag fires the trigger. To run a new list later, import with the same tag —
you never reopen the workflow.

**First run: 20 rows.** Wait 48 hours. Confirm drops are landing and the
recording sounds right on a real phone before scaling. A bad recording sent to
500 people burns 500 contacts you cannot easily re-approach.

---

## Optional second workflow — catch the callbacks

Worth ten minutes once the main one is live.

```
Create a workflow named: VM Drop — Responder

TRIGGER
Type: Customer Replied
Channels: all available, including inbound call

ACTIONS
Step 1 — Add Contact Tag: warm-lead
Step 2 — Remove Contact Tag: vm-drop
Step 3 — Internal Notification
  Send to: my phone
  Message: "Callback from {{contact.first_name}} {{contact.company_name}}
  — {{contact.phone}}"

SETTINGS
Allow Re-Entry: Off
```

Speed to response is the highest-leverage variable in the whole campaign.
Getting the alert on your phone the moment someone calls back is worth more than
any script change.

---

## Compliance gate — before the first import

Voice-only skips A2P 10DLC registration entirely (that is SMS-only). It does
**not** skip TCPA.

The FCC's Nov 21 2022 declaratory ruling makes ringless voicemail a "call" under
the TCPA. Marketing drops to cell phones need prior express written consent, and
exposure is $500–$1,500 per message.

Sort the list before it loads — full table in
`voicemail-drop-campaign.md` → *Compliance*. Short version: form fills, existing
clients, and listed business landlines go in. Purchased or scraped numbers do
not.
