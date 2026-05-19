#!/usr/bin/env python3
"""
AventisAI Email Outreach Engine

AI-personalized cold email generation + multi-step sequences for AventisAI.

Features:
  - Pulls leads from the CRM database (filterable by score, status, tags)
  - Generates AI-personalized first line based on lead's business details
  - Supports multi-step sequences with delays
  - Logs every send to the CRM (activities + email_log tables)
  - Outputs draft .json files for Gmail MCP to send (with approval)

Usage:
  # Generate drafts for high-priority leads
  python execution/aventis_outreach.py --campaign intro --min-score 70 --limit 10

  # Generate follow-up #2 for leads contacted 5+ days ago with no response
  python execution/aventis_outreach.py --campaign followup_1 --status contacted --days-since 5

  # Send via Gmail MCP (set --send to enable, otherwise drafts only)
  python execution/aventis_outreach.py --campaign intro --send
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "leadgen"))

try:
    from database import (
        get_leads, update_lead, get_lead_by_id, add_activity,
        log_email, init_db
    )
    HAS_DB = True
except Exception as e:
    print(f"[WARN] DB not available: {e}")
    HAS_DB = False

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
SENDER_NAME = os.environ.get("AVENTIS_SENDER_NAME", "Pradip")
SENDER_EMAIL = os.environ.get("AVENTIS_SENDER_EMAIL", "pradip@aventismarketing.com")
COMPANY_NAME = "AventisAI"
COMPANY_TAGLINE = "All-in-one AI-powered business software"

# ---------------------------------------------------------------------------
# Email Templates — Campaign Sequences
# ---------------------------------------------------------------------------

CAMPAIGNS = {
    "intro": {
        "name": "Initial Cold Outreach",
        "subject_templates": [
            "Quick question, {first_name}",
            "{business_name} — 2-min question",
            "Are you still using {tech_tool}?",
            "Saw {business_name} on Google",
            "Idea for {business_name}",
        ],
        "body_template": """Hi {first_name},

{personalized_opener}

I run AventisAI — we replace 8-10 separate business tools (CRM, email, SMS, booking, reviews, chatbot) with one AI-powered platform.

Most {business_type} owners we work with are paying $600-$1,500/month across 5+ different SaaS tools. We replace all of it for $297-$497/month — with AI built in for chat, follow-ups, and review responses.

Worth a 15-min look to see if it'd save you money?

If yes, just reply with a time that works. If not, no worries.

— {sender_name}
{company_name}
{company_tagline}""",
        "delay_days": 0,
    },
    "followup_1": {
        "name": "Follow-up #1 (3 days)",
        "subject_templates": [
            "Re: Quick question, {first_name}",
            "Re: {business_name}",
            "Following up — {first_name}",
        ],
        "body_template": """Hi {first_name},

Bumping this in case it got buried.

The pitch: AventisAI replaces what you're paying for {tech_tool} (and 5-7 other tools) with one AI platform. Most {business_type} clients save $400-$800/month while getting better automation.

15-min demo this week?

— {sender_name}""",
        "delay_days": 3,
    },
    "followup_2": {
        "name": "Follow-up #2 (Value-add, 7 days)",
        "subject_templates": [
            "Free idea for {business_name}",
            "{business_name} — quick observation",
        ],
        "body_template": """Hi {first_name},

Last note from me — no pitch this time.

I noticed {observation}. Here's a quick idea that might help: {value_tip}

If you ever want to chat about consolidating your tools or adding AI to your workflow, my door's open.

— {sender_name}
{company_name}""",
        "delay_days": 7,
    },
    "breakup": {
        "name": "Breakup Email (14 days)",
        "subject_templates": [
            "Closing the loop, {first_name}",
            "Should I follow up later?",
        ],
        "body_template": """Hi {first_name},

I'll stop reaching out here — I know you're busy.

If your priorities shift and you want to take a look at AventisAI down the road, just reply with "later" and I'll check back in 3 months.

Otherwise, all the best with {business_name}.

— {sender_name}""",
        "delay_days": 14,
    },
}

# ---------------------------------------------------------------------------
# AI Personalization (Claude)
# ---------------------------------------------------------------------------

def generate_personalized_opener(lead):
    """Use Claude to generate a personalized opening line based on the lead's business."""
    if not ANTHROPIC_KEY:
        return generate_template_opener(lead)

    try:
        import anthropic
    except ImportError:
        print("[AI] anthropic library not installed, using template opener")
        return generate_template_opener(lead)

    tech_stack = lead.get("tech_stack", []) or []
    if isinstance(tech_stack, str):
        try:
            tech_stack = json.loads(tech_stack)
        except Exception:
            tech_stack = []

    business_summary = (
        f"Business: {lead.get('business_name')}\n"
        f"Type: {lead.get('business_type')}\n"
        f"Location: {lead.get('city')}, {lead.get('state')}\n"
        f"Reviews: {lead.get('review_count', 0)} on Google ({lead.get('review_rating', 0)}/5)\n"
        f"Website: {lead.get('website_url') or 'none'}\n"
        f"Tech stack detected: {', '.join(tech_stack) if tech_stack else 'unknown'}\n"
        f"Has chat widget: {lead.get('has_chat_widget', False)}\n"
        f"Active on social: {bool(lead.get('has_social_media'))}\n"
    )

    prompt = f"""Write a personalized opening line (1-2 sentences MAX) for a cold email to this business.

{business_summary}

Rules:
- Reference something SPECIFIC about their business (location, review count, tech stack, or industry pattern)
- Sound human, not salesy
- Don't say "I noticed you have a great business" or similar generic praise
- Don't pitch in the opener — that comes later
- Keep under 30 words
- Don't include "Hi [name]" — that's already in the email
- Output ONLY the opener text, nothing else

Examples of good openers:
- "Saw you've got 87 reviews on Google for the cafe — that's solid for Plymouth."
- "Quick one — you're using both Mailchimp and Calendly, which is what got me curious."
- "Noticed Harborview Realty doesn't have a chat widget yet — most agents are getting 40% of inquiries through chat now."

Now write the opener for this business:"""

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        opener = msg.content[0].text.strip().strip('"').strip()
        return opener
    except Exception as e:
        print(f"[AI] Error generating opener: {e}")
        return generate_template_opener(lead)


def generate_template_opener(lead):
    """Fallback non-AI personalization based on lead data."""
    reviews = lead.get("review_count", 0) or 0
    tech_stack = lead.get("tech_stack", []) or []
    if isinstance(tech_stack, str):
        try:
            tech_stack = json.loads(tech_stack)
        except Exception:
            tech_stack = []
    pain_tools = [t for t in tech_stack if t in (
        "hubspot", "mailchimp", "calendly", "intercom", "drift",
        "constant_contact", "convertkit", "active_campaign", "clickfunnels")]

    if pain_tools and len(pain_tools) >= 2:
        tools = " and ".join(pain_tools[:2])
        return f"Quick one — saw you're using both {tools}, which is what got me curious."
    if pain_tools:
        return f"Noticed {lead.get('business_name')} is using {pain_tools[0]} — wanted to share something."
    if reviews >= 100:
        return f"Saw {lead.get('business_name')} has {reviews}+ reviews on Google — that's serious for {lead.get('city')}."
    if reviews >= 30:
        return f"You're doing real work over at {lead.get('business_name')} — {reviews} reviews and {lead.get('review_rating')}/5 is no joke."
    if not lead.get("has_website"):
        return f"Noticed {lead.get('business_name')} doesn't have a website yet — that's actually why I'm reaching out."
    return f"Came across {lead.get('business_name')} and wanted to reach out about something specific."


def pick_tech_tool(lead):
    """Pick the most relevant tech tool to reference in the email."""
    tech_stack = lead.get("tech_stack", []) or []
    if isinstance(tech_stack, str):
        try:
            tech_stack = json.loads(tech_stack)
        except Exception:
            tech_stack = []
    priority = ["hubspot", "mailchimp", "constant_contact", "convertkit",
                "active_campaign", "calendly", "intercom", "drift", "clickfunnels"]
    for tool in priority:
        if tool in tech_stack:
            return tool.replace("_", " ").title()
    return "Mailchimp"


def get_first_name(lead):
    """Extract or guess a first name from the lead."""
    owner = lead.get("owner_name", "")
    if owner:
        return owner.split()[0]
    return "there"


def generate_email(lead, campaign_key):
    """Generate a full email draft for a lead and campaign."""
    import random
    campaign = CAMPAIGNS[campaign_key]
    first_name = get_first_name(lead)
    business_name = lead.get("business_name", "your business")
    business_type = (lead.get("business_type") or "business").replace("_", " ")
    tech_tool = pick_tech_tool(lead)

    subject_template = random.choice(campaign["subject_templates"])
    subject = subject_template.format(
        first_name=first_name,
        business_name=business_name,
        tech_tool=tech_tool,
    )

    personalized_opener = generate_personalized_opener(lead) if campaign_key == "intro" else ""

    # Observation + tip for value-add followup
    observation = (
        f"you've got strong reviews ({lead.get('review_count', 0)}) but no chat widget on the site"
        if not lead.get("has_chat_widget") and lead.get("has_website")
        else f"you're active in {lead.get('city')}"
    )
    value_tip = (
        "adding a simple AI chat to your homepage usually captures 20-30% more leads "
        "that would have bounced. Even if you don't use AventisAI, it's worth doing."
    )

    body = campaign["body_template"].format(
        first_name=first_name,
        business_name=business_name,
        business_type=business_type,
        tech_tool=tech_tool,
        personalized_opener=personalized_opener,
        observation=observation,
        value_tip=value_tip,
        sender_name=SENDER_NAME,
        company_name=COMPANY_NAME,
        company_tagline=COMPANY_TAGLINE,
    )

    return {
        "lead_id": lead.get("id"),
        "to_email": lead.get("email"),
        "to_name": business_name,
        "from_name": SENDER_NAME,
        "from_email": SENDER_EMAIL,
        "subject": subject,
        "body": body.strip(),
        "campaign": campaign_key,
        "campaign_name": campaign["name"],
        "generated_at": datetime.now().isoformat(),
    }


# ---------------------------------------------------------------------------
# Lead Selection
# ---------------------------------------------------------------------------

def filter_leads(min_score=0, status=None, days_since=None, limit=20, has_email=True):
    """Get leads matching filters from the CRM."""
    if not HAS_DB:
        return []
    init_db()
    all_leads = get_leads(filters={}, sort_by="lead_score", sort_dir="DESC", limit=1000)

    if isinstance(all_leads, dict):
        all_leads = all_leads.get("leads", all_leads.get("items", []))

    filtered = []
    for lead in all_leads:
        if has_email and not lead.get("email"):
            continue
        if lead.get("lead_score", 0) < min_score:
            continue
        if status and lead.get("status") != status:
            continue
        if days_since:
            contact_date = lead.get("contact_date") or lead.get("updated_at")
            if contact_date:
                try:
                    cd = datetime.fromisoformat(contact_date.replace("Z", ""))
                    if (datetime.now() - cd).days < days_since:
                        continue
                except Exception:
                    pass
        filtered.append(lead)
        if len(filtered) >= limit:
            break
    return filtered


# ---------------------------------------------------------------------------
# Output / Sending
# ---------------------------------------------------------------------------

def save_drafts(drafts, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(drafts, f, indent=2, default=str)
    print(f"\n[Drafts] Saved {len(drafts)} email drafts to {output_path}")


def print_drafts(drafts):
    print(f"\n{'='*70}")
    print(f"  GENERATED {len(drafts)} EMAIL DRAFTS")
    print(f"{'='*70}\n")
    for i, draft in enumerate(drafts, 1):
        print(f"--- DRAFT {i}/{len(drafts)} ---")
        print(f"To:      {draft['to_name']} <{draft['to_email']}>")
        print(f"Subject: {draft['subject']}")
        print(f"Campaign: {draft['campaign_name']}")
        print()
        print(draft["body"])
        print()
        print("─" * 70)
        print()


def log_send_intent(draft):
    """Record that we generated this draft (and would send it)."""
    if not HAS_DB or not draft.get("lead_id"):
        return
    try:
        log_email(
            lead_id=draft["lead_id"],
            to_email=draft["to_email"],
            subject=draft["subject"],
            body=draft["body"],
        )
        add_activity(
            lead_id=draft["lead_id"],
            activity_type="email_drafted",
            note=f"[{draft['campaign']}] {draft['subject']}",
        )
        update_lead(draft["lead_id"], {
            "status": "contacted",
            "contacted": 1,
            "contact_date": str(date.today()),
        })
    except Exception as e:
        print(f"[Log] Error: {e}")


# ---------------------------------------------------------------------------
# Main CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="AventisAI Outreach Engine")
    parser.add_argument("--campaign", default="intro",
                        choices=list(CAMPAIGNS.keys()),
                        help="Which campaign to run")
    parser.add_argument("--min-score", type=int, default=60,
                        help="Minimum lead score (0-100)")
    parser.add_argument("--status", help="Filter by lead status (new, contacted, etc.)")
    parser.add_argument("--days-since", type=int,
                        help="Only leads not contacted in N days")
    parser.add_argument("--limit", type=int, default=10,
                        help="Max emails to generate")
    parser.add_argument("--lead-id", type=int, help="Generate for a specific lead")
    parser.add_argument("--output",
                        default=None,
                        help="Output JSON path for drafts")
    parser.add_argument("--mark-contacted", action="store_true",
                        help="Mark leads as contacted after generation")
    args = parser.parse_args()

    # 1. Get leads
    if args.lead_id:
        lead = get_lead_by_id(args.lead_id)
        leads = [lead] if lead else []
    else:
        leads = filter_leads(
            min_score=args.min_score,
            status=args.status,
            days_since=args.days_since,
            limit=args.limit,
        )

    if not leads:
        print("No leads matched the filter criteria.")
        return

    print(f"[Pipeline] {len(leads)} leads matched. Generating '{args.campaign}' emails...\n")

    # 2. Generate emails
    drafts = []
    for i, lead in enumerate(leads, 1):
        print(f"  [{i}/{len(leads)}] {lead.get('business_name')[:40]:40} ", end="", flush=True)
        draft = generate_email(lead, args.campaign)
        drafts.append(draft)
        print(f"OK")
        time.sleep(0.2)

    # 3. Save + display
    output_path = args.output or os.path.join(
        PROJECT_ROOT, "clients", "leads", "outreach_drafts",
        f"{args.campaign}_{date.today()}.json"
    )
    save_drafts(drafts, output_path)
    print_drafts(drafts)

    # 4. Log to CRM
    if args.mark_contacted:
        for draft in drafts:
            log_send_intent(draft)
        print(f"[CRM] Logged {len(drafts)} leads as contacted")

    print(f"\nNext step: Review drafts in {output_path}")
    print(f"Then send via Gmail MCP (mcp__gmail__send_message) after approval.")


if __name__ == "__main__":
    main()
