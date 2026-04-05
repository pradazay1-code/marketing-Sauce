#!/usr/bin/env python3
"""
GitHub Actions email sender for One Vision Marketing.
Reads outreach_drafts.json, sends pending emails via Gmail SMTP.
"""

import json
import os
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# Accept multiple secret name formats
EMAIL = (
    os.environ.get("GMAIL_EMAIL") or
    os.environ.get("OUTLOOK_EMAIL") or
    ""
)
PASSWORD = (
    os.environ.get("GMAIL_APP_PASSWORD") or
    os.environ.get("OUTLOOK_PASSWORD") or
    ""
)
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"
DRAFTS_PATH = "clients/leads/outreach_drafts.json"
DELAY_BETWEEN_EMAILS = 30  # seconds


def send_email(to_email, subject, body):
    """Send a single email via Gmail SMTP."""
    msg = MIMEMultipart()
    msg["From"] = f"Isaiah Wright - One Vision Marketing <{EMAIL}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30)
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login(EMAIL, PASSWORD)
    server.sendmail(EMAIL, to_email, msg.as_string())
    server.quit()


def main():
    if not EMAIL or not PASSWORD:
        print("ERROR: Email credentials not found.")
        print("Add these secrets to your repo (Settings > Secrets > Actions):")
        print("  GMAIL_EMAIL = your-gmail@gmail.com")
        print("  GMAIL_APP_PASSWORD = your-16-char-app-password")
        print("  (or OUTLOOK_EMAIL / OUTLOOK_PASSWORD)")
        exit(1)

    print(f"Using email: {EMAIL}")
    print(f"SMTP server: {SMTP_SERVER}:{SMTP_PORT}")
    print(f"Password length: {len(PASSWORD)} chars\n")

    with open(DRAFTS_PATH, "r") as f:
        drafts = json.load(f)

    pending = [d for d in drafts if d.get("status") == "pending_approval" and d.get("email")]

    if not pending:
        print("No pending emails with addresses to send.")
        print(f"Total drafts: {len(drafts)}")
        print(f"Drafts with emails: {sum(1 for d in drafts if d.get('email'))}")
        print(f"Already sent: {sum(1 for d in drafts if d.get('status') == 'sent')}")
        return

    print(f"{'[DRY RUN] ' if DRY_RUN else ''}Found {len(pending)} emails to send:\n")

    sent = 0
    for i, draft in enumerate(pending):
        print(f"[{i+1}/{len(pending)}] To: {draft['email']}")
        print(f"  Subject: {draft['subject']}")
        print(f"  Business: {draft['business_name']} ({draft['city']}, {draft['state']})")

        if DRY_RUN:
            print("  Status: SKIPPED (dry run)\n")
            continue

        try:
            send_email(draft["email"], draft["subject"], draft["body"])
            draft["status"] = "sent"
            sent += 1
            print("  Status: SENT\n")

            # Save progress after each send
            with open(DRAFTS_PATH, "w") as f:
                json.dump(drafts, f, indent=2)

            # Delay between emails to avoid spam flags
            if i < len(pending) - 1:
                print(f"  Waiting {DELAY_BETWEEN_EMAILS}s before next email...")
                time.sleep(DELAY_BETWEEN_EMAILS)

        except smtplib.SMTPAuthenticationError as e:
            print(f"  ERROR: Authentication failed - {e}")
            print(f"  Email used: {EMAIL}")
            print(f"  Password length: {len(PASSWORD)}")
            print("  Make sure you're using a Gmail App Password (16 chars, no spaces):")
            print("  https://myaccount.google.com/apppasswords")
            exit(1)
        except Exception as e:
            print(f"  ERROR: {e}")
            draft["status"] = f"error: {str(e)}"

    # Final save
    with open(DRAFTS_PATH, "w") as f:
        json.dump(drafts, f, indent=2)

    print(f"\nDone! {sent}/{len(pending)} emails sent successfully.")


if __name__ == "__main__":
    main()
