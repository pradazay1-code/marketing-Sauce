"""
AventisAI — Email Service.
Sends outreach emails via SMTP. Supports templates with variable substitution.
"""

import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from database import get_email_settings, log_email


def render_template(template_str, lead):
    """Replace {{variable}} placeholders with lead fields."""
    def replacer(match):
        key = match.group(1).strip()
        return str(lead.get(key, "") or "")
    return re.sub(r"\{\{(\w+)\}\}", replacer, template_str)


def send_email(to_email, subject, body, lead_id=None, template_id=None, is_html=False):
    """Send a single email via configured SMTP. Returns (success, error_message)."""
    settings = get_email_settings()
    if not settings.get("enabled"):
        return False, "Email not configured. Go to Settings to set up SMTP."
    if not settings.get("smtp_host") or not settings.get("from_email"):
        return False, "SMTP settings incomplete. Configure host and from_email."
    if not to_email:
        return False, "No recipient email address."

    msg = MIMEMultipart("alternative")
    msg["From"] = f"{settings.get('from_name', 'AventisAI')} <{settings['from_email']}>"
    msg["To"] = to_email
    msg["Subject"] = subject

    if is_html:
        msg.attach(MIMEText(body, "html"))
    else:
        msg.attach(MIMEText(body, "plain"))

    try:
        host = settings["smtp_host"]
        port = int(settings.get("smtp_port", 587))
        user = settings.get("smtp_user", "")
        password = settings.get("smtp_pass", "")

        with smtplib.SMTP(host, port, timeout=15) as server:
            server.ehlo()
            if port != 25:
                server.starttls()
                server.ehlo()
            if user and password:
                server.login(user, password)
            server.send_message(msg)

        log_email(lead_id, to_email, subject, body, template_id)
        return True, ""

    except smtplib.SMTPAuthenticationError:
        return False, "SMTP authentication failed. Check username/password."
    except smtplib.SMTPRecipientsRefused:
        return False, f"Recipient refused: {to_email}"
    except smtplib.SMTPException as e:
        return False, f"SMTP error: {str(e)[:200]}"
    except Exception as e:
        return False, f"Connection error: {str(e)[:200]}"


def send_bulk_emails(leads, subject_template, body_template, template_id=None):
    """Send personalized emails to multiple leads. Returns (sent_count, errors)."""
    sent = 0
    errors = []

    for lead in leads:
        email = lead.get("email", "").strip()
        if not email:
            continue

        subject = render_template(subject_template, lead)
        body = render_template(body_template, lead)

        ok, err = send_email(email, subject, body, lead_id=lead.get("id"), template_id=template_id)
        if ok:
            sent += 1
        else:
            errors.append(f"{lead.get('business_name', '?')}: {err}")

    return sent, errors


DEFAULT_TEMPLATES = [
    {
        "name": "Cold Outreach — No Website",
        "subject": "Quick question about {{business_name}}'s online presence",
        "body": """Hi {{owner_name}},

I came across {{business_name}} in {{city}} and noticed you don't currently have a website. In today's market, over 80% of customers look online before visiting a local business.

I help small businesses like yours get online quickly with a professional website that brings in customers — no tech knowledge needed on your end.

Would you be open to a quick 5-minute call this week to see if it's a fit?

Best,
[Your Name]
Aventis Marketing""",
    },
    {
        "name": "Cold Outreach — Weak Website",
        "subject": "I have some ideas for {{business_name}}'s website",
        "body": """Hi {{owner_name}},

I found {{business_name}} while researching businesses in {{city}}, {{state}}. I took a look at your current website and I think there are some easy wins that could bring you more customers.

A few things I noticed:
- Your site could rank higher on Google with some SEO tweaks
- A mobile-friendly redesign could capture more local traffic
- Adding online booking/ordering could increase revenue

I'd love to show you what I have in mind — no charge for the consultation.

Would you have 10 minutes this week?

Best,
[Your Name]
Aventis Marketing""",
    },
    {
        "name": "Follow-Up",
        "subject": "Following up — {{business_name}}",
        "body": """Hi {{owner_name}},

Just following up on my last message about {{business_name}}. I know things get busy, so I wanted to keep this brief.

I genuinely think I can help bring more customers to {{business_name}} through a better online presence. Happy to share a few quick ideas whenever works for you.

Best,
[Your Name]
Aventis Marketing""",
    },
    {
        "name": "AI Software — Real Estate",
        "subject": "You lost 3 leads last weekend — here's why",
        "body": """Hi {{owner_name}},

The average real estate agent loses 3-5 buyer inquiries every weekend because they can't respond fast enough. By the time Monday hits, those leads already called someone else.

We built an AI system that responds to every lead within 60 seconds — whether it comes from Zillow, your website, or a missed call. It qualifies them, books a showing, and adds them to your pipeline automatically.

No hiring an assistant. No missing another commission.

Worth a 10-minute call this week? I'll show you exactly how it works with your current setup.

— [Your Name]
Aventis Marketing""",
    },
    {
        "name": "AI Software — Home Services",
        "subject": "That missed call at 2pm was a $4,000 job",
        "body": """Hi {{owner_name}},

When you're on a job site, you can't answer every call. But your customers won't leave a voicemail — they'll call the next contractor on Google.

We set up an AI system for service companies like {{business_name}} that:
- Texts back every missed call instantly
- Books the estimate on your calendar without you lifting a finger
- Sends automatic reminders so customers actually show up
- Follows up on old quotes that never closed

You're already getting the calls. You're just not catching all of them.

Want me to show you how it works? Takes 10 minutes, no commitment.

— [Your Name]
Aventis Marketing""",
    },
    {
        "name": "AI Software — Medical/Dental/Spa",
        "subject": "Your front desk is losing you $8K/month",
        "body": """Hi {{owner_name}},

Here's the math: the average practice loses 15-20 appointment requests per month to hold times, missed calls, and slow follow-ups. At $400+ per treatment, that's $6,000-$8,000 walking out the door.

We built an AI booking assistant for practices like {{business_name}} that:
- Answers inquiries 24/7 via text, webchat, and social DMs
- Books directly onto your calendar with no back-and-forth
- Sends reminders that cut no-shows by 35%
- Automatically asks happy patients for Google reviews

Your front desk handles the people in the room. Our AI handles everyone trying to get in.

I'd love to show you a quick demo — 10 minutes, no pressure. What does your Thursday look like?

— [Your Name]
Aventis Marketing""",
    },
    {
        "name": "AI Software — Law Firms",
        "subject": "67% of your website visitors leave without contacting you",
        "body": """Hi {{owner_name}},

Most people looking for an attorney visit 3-4 websites before making a call. If your site doesn't capture them immediately, they're gone — and they're hiring someone else.

We built an AI intake system for firms like {{business_name}} that:
- Engages every website visitor with an AI chat assistant
- Qualifies them before they reach your desk (case type, timeline, budget)
- Sends the intake form automatically and follows up if they don't complete it
- Tracks every lead in a pipeline so nothing slips through the cracks

You went to law school to practice law, not chase down leads.

Worth a short call? I'll walk you through exactly how it works.

— [Your Name]
Aventis Marketing""",
    },
    {
        "name": "AI Software — Gyms/Fitness",
        "subject": "That 'I'll think about it' lead just joined another gym",
        "body": """Hi {{owner_name}},

Most people who inquire about a membership don't sign up on the first visit. They say "I'll think about it" and disappear. The gyms that win are the ones that follow up.

We set up an AI follow-up system for fitness businesses like {{business_name}} that:
- Texts every new inquiry within 60 seconds with a free trial offer
- Follows up automatically at day 1, 3, and 7 if they go quiet
- Sends class schedules, trainer availability, and booking links
- Re-engages old leads every 30 days with a "we miss you" offer

No one on your team has to remember to follow up. The AI just does it.

Want to see it in action? Quick 10-minute demo — I'll build a sample workflow for {{business_name}} on the call.

— [Your Name]
Aventis Marketing""",
    },
]
