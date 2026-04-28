#!/usr/bin/env python3
"""
LeadPilot — Daily Lead Generation Runner. All free sources, no API keys.

Sources:
  1. OpenStreetMap Overpass — free, returns phone+website for established businesses
  2. Nominatim search — free, search-based fallback when Overpass is rate-limited
  3. Yellow Pages — free HTML scraping
  4. State Secretary of State filings — free, finds brand new businesses

Usage:
  python leadgen/daily_runner.py                    # Full daily run
  python leadgen/daily_runner.py --state MA         # Single state
  python leadgen/daily_runner.py --source overpass  # OSM Overpass only
  python leadgen/daily_runner.py --source nominatim # Nominatim search only
  python leadgen/daily_runner.py --source yp        # Yellow Pages only
  python leadgen/daily_runner.py --source sos       # SOS filings only
  python leadgen/daily_runner.py --import-csv path  # Import CSV
"""

import argparse
import csv
import os
import sys
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import (
    init_db, add_lead, add_leads_bulk, get_stats, log_scrape, export_csv,
    update_scrape_status,
)
from utils import enrich_lead
from scrapers.sos_scraper import (
    scrape_ma_new_filings, scrape_ri_new_filings, scrape_ct_new_filings,
)
from scrapers.overpass_scraper import scrape_overpass
from scrapers.nominatim_scraper import scrape_nominatim
from scrapers.yellowpages_scraper import scrape_yellowpages


def make_progress_cb(source_label):
    """Returns a callback that logs to stdout AND writes live status to DB."""
    def cb(step, leads_so_far, pct):
        print(f"  [{pct}%] {step} (total leads: {leads_so_far})", flush=True)
        update_scrape_status(
            source=source_label,
            current_step=step,
            progress_pct=pct,
            leads_so_far=leads_so_far,
            last_message=step,
        )
    return cb


def run_overpass(states=None, max_per_city=30, only_no_website=False):
    if states is None:
        states = ["MA", "RI", "CT"]
    total_added = 0
    for state in states:
        update_scrape_status(state=state, source="OpenStreetMap")
        print(f"\n[Overpass] Searching {state}...")
        cb = make_progress_cb(f"OpenStreetMap-{state}")
        leads, error = scrape_overpass(state, max_per_city=max_per_city,
                                        only_no_website=only_no_website,
                                        progress_cb=cb)

        for lead in leads:
            enrich_lead(lead)
            lead["date_found"] = date.today().isoformat()

        if error and not leads:
            print(f"  Error: {error[:200]}")
            log_scrape(f"Overpass-{state}", state, 0, 0, "error", error[:500])
            continue

        added = add_leads_bulk(leads)
        total_added += added
        print(f"  Found {len(leads)} businesses, added {added} new leads")
        log_scrape(f"Overpass-{state}", state, len(leads), added, "completed",
                   error[:500] if error else "")

    return total_added


def run_nominatim(states=None, max_per_query=10, only_no_website=False):
    if states is None:
        states = ["MA", "RI", "CT"]
    total_added = 0
    for state in states:
        update_scrape_status(state=state, source="Nominatim")
        print(f"\n[Nominatim] Searching {state}...")
        cb = make_progress_cb(f"Nominatim-{state}")
        leads, error = scrape_nominatim(state, max_per_query=max_per_query,
                                         only_no_website=only_no_website,
                                         progress_cb=cb)

        for lead in leads:
            enrich_lead(lead)
            lead["date_found"] = date.today().isoformat()

        if error and not leads:
            print(f"  Error: {error[:200]}")
            log_scrape(f"Nominatim-{state}", state, 0, 0, "error", error[:500])
            continue

        added = add_leads_bulk(leads)
        total_added += added
        print(f"  Found {len(leads)} businesses, added {added} new leads")
        log_scrape(f"Nominatim-{state}", state, len(leads), added, "completed",
                   error[:500] if error else "")

    return total_added


def run_yellowpages(states=None, max_per_combo=10, only_no_website=False):
    if states is None:
        states = ["MA", "RI", "CT"]
    total_added = 0
    for state in states:
        update_scrape_status(state=state, source="YellowPages",
                             current_step=f"Searching Yellow Pages in {state}",
                             progress_pct=10)
        print(f"\n[YellowPages] Searching {state}...")
        leads, error = scrape_yellowpages(state, max_per_combo=max_per_combo,
                                           only_no_website=only_no_website)

        for lead in leads:
            enrich_lead(lead)
            lead["date_found"] = date.today().isoformat()

        if error and not leads:
            print(f"  Error: {error[:200]}")
            log_scrape(f"YP-{state}", state, 0, 0, "error", error[:500])
            update_scrape_status(current_step=f"YP {state}: {error[:80]}",
                                 progress_pct=100)
            continue

        added = add_leads_bulk(leads)
        total_added += added
        print(f"  Found {len(leads)} listings, added {added} new leads")
        log_scrape(f"YP-{state}", state, len(leads), added, "completed",
                   error[:500] if error else "")
        update_scrape_status(current_step=f"YP {state} complete: {len(leads)} leads",
                             leads_so_far=total_added, progress_pct=100)

    return total_added


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

        update_scrape_status(state=state, source="SOS",
                             current_step=f"Pulling {state} new filings",
                             progress_pct=20)
        print(f"\n[SOS] Scraping {state} Secretary of State...")
        leads, error = scraper(days_back=days_back, max_results=max_per_state)

        for lead in leads:
            enrich_lead(lead)

        if error and not leads:
            print(f"  Error: {error[:200]}")
            log_scrape(f"SOS-{state}", state, 0, 0, "error", error[:500])
            continue

        if error:
            print(f"  Warning: {error[:200]}")

        if leads:
            added = add_leads_bulk(leads)
            total_added += added
            print(f"  Found {len(leads)} filings, added {added} new leads")
            log_scrape(f"SOS-{state}", state, len(leads), added, "completed",
                       error[:500] if error else "")
        else:
            print(f"  No new filings found")
            log_scrape(f"SOS-{state}", state, 0, 0, "completed", "No results")

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
            enrich_lead(lead)

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
    print(f"  LEADPILOT DAILY REPORT — {date.today()}")
    print("=" * 60)
    print(f"  Total leads:              {stats['total']}")
    print(f"  Without website:          {stats['no_website']}")
    print(f"  With phone:               {stats['with_phone']}")
    print(f"  New today:                {stats['new_today']}")
    print(f"  New this week:            {stats['new_this_week']}")
    print(f"  Contacted:                {stats['contacted']}")
    print(f"  High priority:            {stats['high_priority']}")
    print(f"  Needs followup:           {stats['needs_followup']}")
    print(f"  Conversion rate:          {stats['conversion_rate']}%")
    print()
    if stats.get("by_state"):
        print("  By State:")
        for state, count in stats["by_state"].items():
            print(f"    {state}: {count}")
    print()
    if stats.get("by_source"):
        print("  By Source:")
        for src, count in stats["by_source"].items():
            print(f"    {src}: {count}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="LeadPilot — Daily Lead Generator")
    parser.add_argument("--state", choices=["MA", "RI", "CT"], help="Target single state")
    parser.add_argument("--source", choices=["overpass", "nominatim", "yp", "sos", "all"],
                        default="all", help="Data source")
    parser.add_argument("--import-csv", type=str, help="Import leads from CSV file")
    parser.add_argument("--import-all", action="store_true", help="Import all existing CSVs")
    parser.add_argument("--days-back", type=int, default=7, help="Days back for SOS filings")
    parser.add_argument("--max-results", type=int, default=100, help="Max results per state")
    parser.add_argument("--only-no-website", action="store_true",
                        help="Only return businesses without websites")
    parser.add_argument("--report-only", action="store_true", help="Only print report")
    args = parser.parse_args()

    init_db()

    print(f"LeadPilot — Lead Generator (FREE sources)")
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

    update_scrape_status(running=1, starting=True, source=args.source,
                         state=args.state or "ALL", current_step="Starting...",
                         progress_pct=0, leads_so_far=0)

    try:
        states = [args.state] if args.state else None
        total_added = 0

        if args.source in ("overpass", "all"):
            total_added += run_overpass(states, only_no_website=args.only_no_website)

        if args.source in ("nominatim", "all"):
            total_added += run_nominatim(states, only_no_website=args.only_no_website)

        if args.source in ("yp", "all"):
            total_added += run_yellowpages(states, only_no_website=args.only_no_website)

        if args.source in ("sos", "all"):
            total_added += run_sos_scrapers(states, args.days_back, args.max_results)

        print(f"\nTotal new leads added: {total_added}")
        print_daily_report()

        update_scrape_status(running=0, current_step=f"Complete: {total_added} new leads",
                             progress_pct=100, leads_so_far=total_added)

        if total_added > 0:
            csv_output = os.path.join(os.path.dirname(__file__), "..", "clients", "leads",
                                      f"daily_leads_{date.today().isoformat()}.csv")
            csv_data = export_csv({"date_from": date.today().isoformat()})
            if csv_data:
                os.makedirs(os.path.dirname(csv_output), exist_ok=True)
                with open(csv_output, "w") as f:
                    f.write(csv_data)
                print(f"\nExported today's leads to: {csv_output}")
    except Exception as e:
        update_scrape_status(running=0, current_step=f"Failed: {str(e)[:100]}",
                             progress_pct=100)
        raise


if __name__ == "__main__":
    main()
