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

This is the canonical build. Every fix is already in it.

```
Create a workflow named: VM Drop — Callback

PURPOSE
Deliver four pre-recorded ringless voicemail drops to a list of cold leads
across roughly five weeks, then tag the contact as finished. This is a
VOICE-ONLY campaign. Voicemail is the only outbound channel.

TRIGGER
  Type: Contact Tag
  Condition: Tag Added
  Tag: vm-drop

TRIGGER FILTER — required, do not omit
  Filter: Contact Tag
  Operator: does not include
  Value: vm-drop-complete

  This prevents anyone who has already finished the sequence from ever
  re-entering it on a future list import.

ACTIONS — build in exactly this order, ten steps:

  Step 1 — Voicemail
    Audio file: VM-Drop-1
    Fires immediately on entry. Lands day 1.

  Step 2 — Wait
    Duration: 7 days

  Step 3 — Voicemail
    Audio file: VM-Drop-2
    Lands day 8.

  Step 4 — Wait
    Duration: 10 days

  Step 5 — Voicemail
    Audio file: VM-Drop-3
    Lands day 18.

  Step 6 — Wait
    Duration: 14 days

  Step 7 — Voicemail
    Audio file: VM-Drop-4
    The close-out. Lands day 32.

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
  Timezone: Contact's timezone — NOT the account timezone
  Excluded days: Sunday

DO NOT ADD ANY OF THE FOLLOWING
  - SMS or MMS actions of any kind
  - Email actions
  - If/Else branches, conditions, or goals
  - AI, conversation, or chatbot actions
  - Appointment, calendar, or booking actions
  - Any action not listed in the ten steps above

CRITICAL CONSTRAINTS
  1. Use the VOICEMAIL action, not the Call action. Voicemail deposits a
     recording without ringing the phone. A Call action rings the phone and
     is wrong for this campaign.
  2. Do NOT shorten the wait durations. 7, 10, and 14 days are deliberate.
     Do not compress them to a 2-3 day cadence.
  3. Keep the workflow strictly linear: trigger, then steps 1 through 10 in
     order, with no branching.
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
| **Filter** | **`Contact Tag` · does not include · `vm-drop-complete`** |

The filter is the piece the AI drops most often. Without it, step 9 strips the
`vm-drop` tag and a future import can restart the whole five weeks for someone
who already finished it.

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

## The four things the AI gets wrong most often

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
This is your entire exit condition. Without it, a lead who calls you back in
week one still receives the "this'll be my last message" close-out in week five,
after you have already spoken. That single miss undoes more deals than a weak
script does.

**4. The trigger filter is dropped.**
The AI treats the filter as optional decoration and builds a bare `Tag Added`
trigger. Open the trigger node and confirm
`Contact Tag · does not include · vm-drop-complete` is actually there. This is
what makes re-sends structurally impossible rather than merely unlikely.

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

**Clean the CSV first — always.** GHL dedupes on import by *exact* phone match,
so `(508) 555-1234`, `508-555-1234` and `+15085551234` become three contact
records for one person, and each one runs the full five-week sequence.

```bash
# see what would be removed, change nothing
python execution/dedupe_vm_list.py --input raw_leads.csv

# write the clean file and record the numbers as sent
python execution/dedupe_vm_list.py \
    --input raw_leads.csv \
    --output clients/leads/ready_to_import.csv \
    --commit
```

The script normalizes every number to E.164, drops invalid numbers, drops
in-file duplicates, drops anyone already in `clients/leads/vm-drop-history.csv`,
and drops anyone in `clients/leads/vm-drop-suppression.csv`. Only `--commit`
writes to history, so dry-run as often as you like.

Then:

1. **Contacts → Import**
2. Upload the **cleaned** file (`First Name`, `Phone`, `Company`)
3. On the import screen, **apply tag `vm-drop` to the entire batch**
4. Finish

The tag fires the trigger. To run a new list later, clean it and import with the
same tag — you never reopen the workflow.

**First run: 20 rows.** Wait 48 hours. Confirm drops are landing and the
recording sounds right on a real phone before scaling. A bad recording sent to
500 people burns 500 contacts you cannot easily re-approach.

---

## Never hitting the same person twice

Four layers, because each one catches what the others miss.

### Layer 1 — Workflow re-entry

**Settings → Allow Re-Entry: OFF.** Blocks the same contact record from running
the sequence twice. This is the primary guard and you already have it.

### Layer 2 — Trigger filter

**Trigger → Add Filter →** `Contact Tag` · **does not include** ·
`vm-drop-complete`

Step 9 removes the `vm-drop` tag, which means a re-import could re-fire the
trigger if re-entry ever gets toggled on or the workflow gets rebuilt. This
filter closes that hole: anyone who finished the sequence cannot re-enter,
regardless of any other setting.

### Layer 3 — CSV hygiene before import

The `dedupe_vm_list.py` step above. This is the layer that matters most, because
layers 1 and 2 both key off the *contact record* — and a differently-formatted
phone number creates a brand new record that no workflow setting can catch.

### Layer 4 — Suppression list

`clients/leads/vm-drop-suppression.csv` — anyone who must never be contacted
again. Add a row the moment someone asks:

```csv
phone,reason,date_added
508-555-0001,asked to stop,2026-09-02
508-555-0002,DNC registry,2026-09-02
```

Format does not matter; the script normalizes on read. This file is the one
piece of the system with legal weight — an opt-out you fail to honor is a
separate TCPA violation on top of the original send.

### Catching duplicates already in GHL

If contacts were imported before you started cleaning files, build a smart list
to find them:

**Contacts → Smart Lists → + Add** → filter `Tags` includes `vm-drop`, sort by
phone. Duplicates surface adjacent to each other. Merge or delete before the
next run.

---

## Second workflow — catch the callbacks (build this one too)

Not optional, and here is why: **Stop on Response halts the sequence mid-way, so
a responder never reaches step 10 and never gets tagged `vm-drop-complete`.**
That leaves them eligible to re-enter on a future import — the exact person you
least want to cold-drop again is the one who already called you back.

This workflow closes that loop.

```
Create a workflow named: VM Drop — Responder

PURPOSE
Catch anyone who responds during the voicemail campaign, mark them so they
can never re-enter it, and alert me immediately.

TRIGGER
  Type: Customer Replied
  Channels: all available, including inbound call and inbound SMS

TRIGGER FILTER
  Filter: Contact Tag
  Operator: includes
  Value: vm-drop

  Only contacts currently in the voicemail campaign should hit this.

ACTIONS
  Step 1 — Add Contact Tag
    Tag: warm-lead

  Step 2 — Add Contact Tag
    Tag: vm-drop-complete

  Step 3 — Remove Contact Tag
    Tag: vm-drop

  Step 4 — Internal Notification
    Send to: my phone
    Message: "Callback from {{contact.first_name}} at
    {{contact.company_name}} — {{contact.phone}}"

WORKFLOW SETTINGS
  Allow Re-Entry: OFF
```

Step 2 is the one that matters for hygiene — it applies the same permanent
marker the main workflow's step 10 would have, so the trigger filter on
`VM Drop — Callback` will block them from every future import.

Step 4 matters for revenue. Speed to response is the highest-leverage variable
in the campaign: getting the alert on your phone the moment someone calls back
beats any script change you could make.

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
