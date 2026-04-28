#!/usr/bin/env python3
"""
Daily Lead Generation Runner
Runs all scrapers, filters results, scores leads, and saves to database.

Usage:
  python leadgen/daily_runner.py                    # Full daily run
  python leadgen/daily_runner.py --state MA         # Single state
  python leadgen/daily_runner.py --source sos       # SOS filings only
  python leadgen/daily_runner.py --source google    # Google Places only
  python leadgen/daily_runner.py --import-csv path  # Import existing CSV

Set up as cron job for daily automation:
  0 6 * * * cd /home/user/marketing-Sauce && python leadgen/daily_runner.py >> leadgen/daily.log 2>&1
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_db, add_lead, add_leads_bulk, get_stats, log_scrape, export_csv
from scrapers.sos_scraper import (
    scrape_ma_new_filings,
    scrape_ri_new_filings,
    scrape_ct_new_filings,
    check_website_exists,
    categorize_business,
    score_marketing_presence,
    calculate_priority,
)
from scrapers.google_places import find_businesses_without_websites, API_KEY


def run_sos_scrapers(states=None, days_back=7, max_per_state=100):
    if states is None:
        states = ["MA", "RI", "CT"]

    scrapers = {
        "MA": scrape_ma_new_filings,
        "RI": scrape_ri_new_filings,
        "CT": scrape_ct_new_filings,
    }

    total_added = 0
    for state in states:
        scraper = scrapers.get(state)
        if not scraper:
            continue

        print(f"\n[SOS] Scraping {state} Secretary of State...")
        leads, error = scraper(days_back=days_back, max_results=max_per_state)

        if error and not leads:
            print(f"  Error: {error}")
            log_scrape(f"SOS-{state}", state, 0, 0, "error", error)
            continue

        if error:
            print(f"  Warning: {error}")

        if leads:
            added = add_leads_bulk(leads)
            total_added += added
            print(f"  Found {len(leads)} filings, added {added} new leads")
            log_scrape(f"SOS-{state}", state, len(leads), added, "completed", error or "")
        else:
            print(f"  No new filings found")
            log_scrape(f"SOS-{state}", state, 0, 0, "completed", "No results")

    return total_added


def run_google_places(states=None, categories=None, max_per_city=10):
    if not API_KEY:
        print("\n[Google] Skipping — no GOOGLE_PLACES_API_KEY in .env")
        print("  Get one at: https://console.cloud.google.com/apis/credentials")
        return 0

    if states is None:
        states = ["MA", "RI", "CT"]
    if categories is None:
        categories = [
            "restaurant", "barber shop", "hair salon", "gym",
            "auto repair", "contractor", "tattoo", "bakery",
        ]

    total_added = 0
    for state in states:
        print(f"\n[Google] Searching {state} for businesses without websites...")
        leads = find_businesses_without_websites(state, categories, max_per_city)

        for lead in leads:
            lead["date_found"] = date.today().isoformat()

        added = add_leads_bulk(leads)
        total_added += added
        print(f"  Found {len(leads)} businesses, added {added} new leads")
        log_scrape(f"Google-{state}", state, len(leads), added, "completed")

    return total_added


def import_existing_csv(csv_path):
    print(f"\n[Import] Loading {csv_path}...")
    leads = []

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            has_website_raw = row.get("has_website", "No").strip().lower()
            has_website = 1 if has_website_raw in ("yes", "basic", "1", "true") else 0

            lead = {
                "business_name": row.get("name", row.get("business_name", "")).strip(),
                "category": row.get("category", "").strip(),
                "business_type": row.get("business_type", "").strip(),
                "phone": row.get("phone", "").strip(),
                "email": row.get("email", "").strip(),
                "city": row.get("city", "").strip(),
                "state": row.get("state", "").strip(),
                "has_website": has_website,
                "website_url": row.get("website_url", "").strip(),
                "marketing_score": 3 if has_website else 0,
                "priority": "medium" if has_website else "high",
                "date_found": row.get("date_found", date.today().isoformat()).strip(),
                "source": f"CSV Import: {os.path.basename(csv_path)}",
                "notes": row.get("notes", "").strip(),
                "status": "new",
            }

            if lead["business_name"]:
                leads.append(lead)

    added = add_leads_bulk(leads)
    print(f"  Loaded {len(leads)} rows, added {added} new leads")
    log_scrape("CSV Import", "ALL", len(leads), added, "completed")
    return added


def import_all_existing_csvs():
    leads_dir = os.path.join(os.path.dirname(__file__), "..", "clients", "leads")
    if not os.path.exists(leads_dir):
        return 0

    total = 0
    for f in sorted(os.listdir(leads_dir)):
        if f.endswith(".csv"):
            total += import_existing_csv(os.path.join(leads_dir, f))
    return total


def print_daily_report():
    stats = get_stats()
    print("\n" + "=" * 60)
    print(f"  DAILY LEAD GENERATION REPORT — {date.today()}")
    print("=" * 60)
    print(f"  Total leads in database:  {stats['total']}")
    print(f"  Leads without website:    {stats['no_website']}")
    print(f"  New leads today:          {stats['new_today']}")
    print(f"  Contacted:                {stats['contacted']}")
    print()
    print("  By State:")
    for state, count in stats.get("by_state", {}).items():
        print(f"    {state}: {count}")
    print()
    print("  By Category (top 10):")
    for cat, count in stats.get("by_category", {}).items():
        print(f"    {cat}: {count}")
    print()
    print("  By Priority:")
    for pri, count in stats.get("by_priority", {}).items():
        print(f"    {pri}: {count}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="One Vision Marketing — Daily Lead Generator")
    parser.add_argument("--state", choices=["MA", "RI", "CT"], help="Target single state")
    parser.add_argument("--source", choices=["sos", "google", "all"], default="all", help="Data source")
    parser.add_argument("--import-csv", type=str, help="Import leads from CSV file")
    parser.add_argument("--import-all", action="store_true", help="Import all existing CSVs from clients/leads/")
    parser.add_argument("--days-back", type=int, default=7, help="Days back for SOS filings")
    parser.add_argument("--max-results", type=int, default=100, help="Max results per state")
    parser.add_argument("--report-only", action="store_true", help="Only print report")
    args = parser.parse_args()

    init_db()

    print(f"One Vision Marketing — Lead Generator")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Source: {args.source}")

    if args.report_only:
        print_daily_report()
        return

    if args.import_csv:
        import_existing_csv(args.import_csv)
        print_daily_report()
        return

    if args.import_all:
        import_all_existing_csvs()
        print_daily_report()
        return

    states = [args.state] if args.state else None
    total_added = 0

    if args.source in ("sos", "all"):
        total_added += run_sos_scrapers(states, args.days_back, args.max_results)

    if args.source in ("google", "all"):
        total_added += run_google_places(states)

    print(f"\nTotal new leads added: {total_added}")
    print_daily_report()

    csv_output = os.path.join(os.path.dirname(__file__), "..", "clients", "leads",
                              f"daily_leads_{date.today().isoformat()}.csv")
    csv_data = export_csv({"date_from": date.today().isoformat()})
    if csv_data:
        os.makedirs(os.path.dirname(csv_output), exist_ok=True)
        with open(csv_output, "w") as f:
            f.write(csv_data)
        print(f"\nExported today's leads to: {csv_output}")


if __name__ == "__main__":
    main()
