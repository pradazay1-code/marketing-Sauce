#!/usr/bin/env python3
"""
Find leads using WebSearch (works within sandboxed environments).
This is the alternative to find_leads.py which requires direct HTTP access.

Usage:
  python execution/find_leads_web.py --state MA --count 15

Note: This script generates the search queries and output format.
The actual WebSearch calls are made by the Claude agent orchestrating this script.
Run this to see the queries that should be searched, then pipe results back in.
"""

import argparse
import json
import os
from datetime import date


# Target cities by state
CITIES = {
    "MA": ["Boston", "Worcester", "Springfield", "Fall River", "New Bedford",
            "Brockton", "Lowell", "Haverhill", "Westborough", "Chatham",
            "Orleans", "Bridgewater", "Taunton", "Plymouth", "Framingham"],
    "RI": ["Providence", "Warwick", "Cranston", "Pawtucket", "East Providence",
            "Woonsocket", "Newport", "Central Falls", "Westerly", "Bristol"],
    "CT": ["Hartford", "New Haven", "Bridgeport", "Stamford", "Waterbury",
            "Norwalk", "Danbury", "New Britain", "Meriden", "Middletown"],
}

# Business types to search for
BUSINESS_TYPES = [
    "restaurant", "barbershop", "salon", "bakery", "cafe",
    "auto repair", "contractor", "landscaping", "tattoo shop",
    "boutique", "retail shop", "food truck", "cleaning service",
]


def generate_search_queries(state, count):
    """Generate search queries for finding leads."""
    cities = CITIES.get(state, CITIES["MA"])
    queries = []

    for city in cities[:count // 2 + 1]:
        queries.append(f"new small businesses opened {city} {state} 2025 2026")
        queries.append(f"{city} {state} businesses without website")

    return queries


def create_lead_template():
    """Return empty lead template for manual filling."""
    return {
        "business_name": "",
        "type": "",
        "city": "",
        "state": "",
        "address": "",
        "phone": "N/A",
        "owner_name": "there",
        "online_presence": "",
        "website_status": "No Website",
        "priority": "HIGH",
        "notes": "",
        "email": "",
    }


def save_leads(leads, output_path="clients/leads/raw_leads.json"):
    """Save leads to JSON file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(leads, f, indent=2)
    print(f"Saved {len(leads)} leads to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="One Vision Marketing — Lead Finder")
    parser.add_argument("--state", default="MA", choices=["MA", "RI", "CT"], help="Target state")
    parser.add_argument("--count", type=int, default=15, help="Number of leads to find")
    parser.add_argument("--queries-only", action="store_true", help="Only print search queries")
    args = parser.parse_args()

    queries = generate_search_queries(args.state, args.count)

    if args.queries_only:
        print("Search queries to execute via WebSearch:")
        for i, q in enumerate(queries, 1):
            print(f"  {i}. {q}")
        return

    print(f"Lead Finder — Targeting {args.state}, {args.count} leads")
    print(f"Date: {date.today()}")
    print(f"\nGenerated {len(queries)} search queries:")
    for i, q in enumerate(queries, 1):
        print(f"  {i}. {q}")

    print(f"\nInstructions:")
    print(f"  1. Run each query via WebSearch")
    print(f"  2. Extract business info from results")
    print(f"  3. Save to clients/leads/raw_leads.json")
    print(f"\nLead template:")
    print(json.dumps(create_lead_template(), indent=2))


if __name__ == "__main__":
    main()
