"""
LeadPilot — Email Service.
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
    msg["From"] = f"{settings.get('from_name', 'LeadPilot')} <{settings['from_email']}>"
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
One Vision Marketing""",
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
One Vision Marketing""",
    },
    {
        "name": "Follow-Up",
        "subject": "Following up — {{business_name}}",
        "body": """Hi {{owner_name}},

Just following up on my last message about {{business_name}}. I know things get busy, so I wanted to keep this brief.

I genuinely think I can help bring more customers to {{business_name}} through a better online presence. Happy to share a few quick ideas whenever works for you.

Best,
[Your Name]
One Vision Marketing""",
    },
]
