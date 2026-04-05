#!/usr/bin/env python3
"""
Send emails via Outlook SMTP for One Vision Marketing.

Usage:
  python execution/send_outlook_email.py \
    --to "info@business.com" \
    --subject "Helping Business Grow Online" \
    --body "Hi there, ..."

  Or batch mode from outreach_drafts.json:
  python execution/send_outlook_email.py --batch clients/leads/outreach_drafts.json

Requires OUTLOOK_EMAIL and OUTLOOK_PASSWORD in .env
"""

import argparse
import json
import os
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

SMTP_SERVER = "smtp-mail.outlook.com"
SMTP_PORT = 587
OUTLOOK_EMAIL = os.getenv("OUTLOOK_EMAIL", "onevisionmarketing1@outlook.com")
OUTLOOK_PASSWORD = os.getenv("OUTLOOK_PASSWORD", "")


def send_email(to_email, subject, body, sender_name="Isaiah Wright - One Vision Marketing"):
    """Send a single email via Outlook SMTP."""
    if not OUTLOOK_PASSWORD:
        print("ERROR: OUTLOOK_PASSWORD not set in .env")
        print("Add this to your .env file:")
        print('  OUTLOOK_EMAIL=onevisionmarketing1@outlook.com')
        print('  OUTLOOK_PASSWORD=your-password-here')
        return False

    msg = MIMEMultipart()
    msg["From"] = f"{sender_name} <{OUTLOOK_EMAIL}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(OUTLOOK_EMAIL, OUTLOOK_PASSWORD)
        server.sendmail(OUTLOOK_EMAIL, to_email, msg.as_string())
        server.quit()
        print(f"SENT to {to_email}: {subject}")
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"AUTH ERROR: {e}")
        print("You may need an App Password. Go to:")
        print("  https://account.microsoft.com/security")
        print("  > Advanced security options > App passwords")
        return False
    except Exception as e:
        print(f"ERROR sending to {to_email}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="One Vision Marketing — Outlook Email Sender")
    parser.add_argument("--to", help="Recipient email address")
    parser.add_argument("--subject", help="Email subject")
    parser.add_argument("--body", help="Email body text")
    parser.add_argument("--batch", help="Path to outreach_drafts.json for batch sending")
    parser.add_argument("--delay", type=int, default=30, help="Seconds between emails (default 30)")
    args = parser.parse_args()

    if args.batch:
        with open(args.batch, "r") as f:
            drafts = json.load(f)

        pending = [d for d in drafts if d.get("status") == "pending_approval" and d.get("email")]
        print(f"Found {len(pending)} emails to send out of {len(drafts)} total drafts.\n")

        sent = 0
        for draft in pending:
            success = send_email(draft["email"], draft["subject"], draft["body"])
            if success:
                draft["status"] = "sent"
                sent += 1
                # Save progress after each send
                with open(args.batch, "w") as f:
                    json.dump(drafts, f, indent=2)
            if sent < len(pending):
                print(f"  Waiting {args.delay}s before next email...")
                time.sleep(args.delay)

        print(f"\nDone! {sent}/{len(pending)} emails sent.")

    elif args.to and args.subject and args.body:
        send_email(args.to, args.subject, args.body)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
