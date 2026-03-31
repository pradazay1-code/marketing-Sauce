#!/usr/bin/env python3
"""
Email Template Generator for Marketing Sauce
Generates email drafts from templates for client outreach.

Usage:
    python execution/email_outreach.py --type cold-outreach --business "Joe's Barbershop" --owner "Joe Smith" --state "MA"
    python execution/email_outreach.py --type delivery --client "north-atlantic-tattoo" --url "https://example.com"

This script generates the email text. Actual sending is done via Gmail MCP.
"""

import argparse
import sys
from datetime import date


TEMPLATES = {
    "cold-outreach": {
        "subject": "Free Website Mockup for {business_name}",
        "body": """Hi {owner_name},

I came across {business_name} and was impressed by what you're building. I noticed you don't currently have a website — I'd love to help change that.

I run Marketing Sauce, a local digital marketing agency. We build clean, mobile-friendly websites for small businesses in the {state} area.

I'd be happy to put together a free mockup for you — no strings attached. If you like it, we can talk pricing. If not, no worries at all.

Would you be open to a quick 5-minute call this week?

Best,
Marketing Sauce
"""
    },
    "delivery": {
        "subject": "Your New Website is Live!",
        "body": """Hi {client_name},

Great news — your website is officially live! You can view it here:
{website_url}

The site is mobile-friendly and optimized for search engines. Here's what's included:
- Custom responsive design
- SEO optimization
- Contact form
- Mobile navigation

Let me know if you'd like any changes. We're here to help!

Best,
Marketing Sauce
"""
    },
    "follow-up": {
        "subject": "Quick follow-up from Marketing Sauce",
        "body": """Hi {client_name},

Just checking in — I sent over some info about building a website for {business_name} last week. Wanted to see if you had any questions.

No pressure at all. If you're interested, I'm happy to put together a quick mockup so you can see what your business would look like online.

Just reply to this email or give me a call anytime.

Best,
Marketing Sauce
"""
    },
    "proposal": {
        "subject": "Website Proposal for {business_name}",
        "body": """Hi {owner_name},

Thanks for your interest in getting a website for {business_name}! Here's what I'm thinking:

**What you'll get:**
- Professional, mobile-friendly website
- SEO optimization so customers can find you on Google
- Contact form for inquiries
- Fast loading, clean design

**Timeline:** 3-5 business days from approval

I'd love to hop on a quick call to learn more about your business and what you're looking for. When works best for you?

Best,
Marketing Sauce
"""
    }
}


def generate_email(template_type, **kwargs):
    """Generate email from template with provided variables."""
    if template_type not in TEMPLATES:
        print(f"ERROR: Unknown template type '{template_type}'")
        print(f"Available types: {', '.join(TEMPLATES.keys())}")
        sys.exit(1)

    template = TEMPLATES[template_type]
    subject = template["subject"]
    body = template["body"]

    # Replace placeholders with provided values
    for key, value in kwargs.items():
        placeholder = "{" + key + "}"
        subject = subject.replace(placeholder, value)
        body = body.replace(placeholder, value)

    return subject, body


def main():
    parser = argparse.ArgumentParser(description="Email Template Generator")
    parser.add_argument("--type", required=True, choices=TEMPLATES.keys(), help="Email template type")
    parser.add_argument("--business", dest="business_name", default="your business", help="Business name")
    parser.add_argument("--owner", dest="owner_name", default="there", help="Owner name")
    parser.add_argument("--client", dest="client_name", default="there", help="Client name")
    parser.add_argument("--state", default="MA", help="State")
    parser.add_argument("--url", dest="website_url", default="", help="Website URL")
    args = parser.parse_args()

    kwargs = {
        "business_name": args.business_name,
        "owner_name": args.owner_name,
        "client_name": args.client_name,
        "state": args.state,
        "website_url": args.website_url,
    }

    subject, body = generate_email(args.type, **kwargs)

    print(f"SUBJECT: {subject}")
    print(f"\n{'='*50}\n")
    print(body)
    print(f"\n{'='*50}")
    print(f"\nGenerated on {date.today()} by Marketing Sauce")


if __name__ == "__main__":
    main()
