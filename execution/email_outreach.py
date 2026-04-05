#!/usr/bin/env python3
"""
Email Template Generator for One Vision Marketing
Generates email drafts from templates for client outreach.

Usage:
    python execution/email_outreach.py --type cold-outreach --business "Joe's Barbershop" --owner "Joe" --city "Boston" --state "MA"
    python execution/email_outreach.py --type delivery --business "Joe's Barbershop" --client "Joe" --url "https://example.com"
    python execution/email_outreach.py --type follow-up --business "Joe's Barbershop" --client "Joe"
    python execution/email_outreach.py --type proposal --business "Joe's Barbershop" --owner "Joe"

This script generates the email text. Actual sending is done via Gmail MCP.
"""

import argparse
import sys
from datetime import date


TEMPLATES = {
    "cold-outreach": {
        "subject": "Helping {business_name} Grow Online",
        "body": """Hi {owner_name},

I came across {business_name} and really like what you're doing in {city}. As a fellow Massachusetts business owner, I know how important it is to have a strong online presence — and I think there's a great opportunity for {business_name} to reach even more customers.

My name is Isaiah Wright, and I run One Vision Marketing out of Bridgewater, MA. We're a full-service digital marketing agency that helps small businesses like yours grow through:

- Professional website creation & hosting
- Google, Facebook & Instagram advertising
- SEO to help customers find you online
- Strategies to bring in more clients and boost revenue
- Social media management & brand development

We've worked with businesses across Massachusetts, and I also have marketing research experience with RECNA here in Bridgewater, helping them expand their reach and grow.

I'd love to learn more about {business_name} and see how we can help — no pressure, just a conversation. If you're open to it, I can even put together a free website mockup so you can see what's possible.

Would you be open to a quick chat this week?

Best regards,
Isaiah Wright
One Vision Marketing
Bridgewater, MA
"""
    },
    "delivery": {
        "subject": "Your New Website is Live — {business_name}",
        "body": """Hi {client_name},

Great news — your website is officially live! You can check it out here:
{website_url}

Here's what's included:
- Fully custom, mobile-friendly design
- SEO optimization so customers can find you on Google
- Fast loading speeds
- Professional layout built around your brand

Take a look and let me know if you'd like any changes — I'm happy to make adjustments until it's exactly what you want.

This is just the beginning. Whenever you're ready, we can also look into advertising, social media, and other strategies to bring in more clients.

Thanks for trusting One Vision Marketing with your online presence.

Best regards,
Isaiah Wright
One Vision Marketing
Bridgewater, MA
"""
    },
    "follow-up": {
        "subject": "Just checking in — {business_name}",
        "body": """Hi {client_name},

I reached out recently about helping {business_name} with your online presence and wanted to follow up. I know things get busy, so no rush at all.

If you're interested, I'm still happy to put together a free website mockup for {business_name} — just so you can see what it could look like. No commitment, no pressure.

We help small businesses across Massachusetts with everything from websites and hosting to ads and client growth strategies. I'd love the chance to learn more about your goals and see if we can help.

Feel free to reply whenever it's convenient, or let me know a good time to chat.

Best regards,
Isaiah Wright
One Vision Marketing
Bridgewater, MA
"""
    },
    "proposal": {
        "subject": "Growth Plan for {business_name}",
        "body": """Hi {owner_name},

Thanks for taking the time to talk about {business_name} — I'm excited about the opportunity to help you grow.

Here's what I'm recommending to start:

**Website & Online Presence**
- Professional, mobile-friendly website designed around your brand
- Website hosting so you don't have to worry about the technical side
- SEO optimization to help customers find you on Google

**Marketing & Growth**
- Targeted ads on Google, Facebook & Instagram to reach new customers
- Strategies to increase foot traffic and client bookings
- Ongoing support as your business grows

I've helped businesses across Massachusetts build their online presence, and I also have marketing research experience with RECNA in Bridgewater, helping organizations expand their reach.

My goal is to make this easy for you — you focus on running your business, and I'll handle the marketing side. Let me know if you'd like to move forward or if you have any questions.

Best regards,
Isaiah Wright
One Vision Marketing
Bridgewater, MA
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
    parser = argparse.ArgumentParser(description="One Vision Marketing — Email Template Generator")
    parser.add_argument("--type", required=True, choices=TEMPLATES.keys(), help="Email template type")
    parser.add_argument("--business", dest="business_name", default="your business", help="Business name")
    parser.add_argument("--owner", dest="owner_name", default="there", help="Owner name")
    parser.add_argument("--client", dest="client_name", default="there", help="Client name")
    parser.add_argument("--city", default="your area", help="City")
    parser.add_argument("--state", default="MA", help="State")
    parser.add_argument("--url", dest="website_url", default="", help="Website URL")
    args = parser.parse_args()

    kwargs = {
        "business_name": args.business_name,
        "owner_name": args.owner_name,
        "client_name": args.client_name,
        "city": args.city,
        "state": args.state,
        "website_url": args.website_url,
    }

    subject, body = generate_email(args.type, **kwargs)

    print(f"SUBJECT: {subject}")
    print(f"\n{'='*50}\n")
    print(body)
    print(f"\n{'='*50}")
    print(f"\nGenerated on {date.today()} by One Vision Marketing")


if __name__ == "__main__":
    main()
