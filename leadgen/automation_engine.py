#!/usr/bin/env python3
"""
AventisAI — Automation Engine
Runs scheduled lead discovery, enrichment, and outreach sequences.
Can run standalone (cron) or as a background thread inside the Flask app.
"""

import os
import sys
import json
import time
import subprocess
import threading
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import (
    init_db, get_db, get_leads, update_lead,
    add_automation_job, finish_automation_job, get_automation_jobs,
    get_sequence_runs, update_sequence_run, add_sequence_run,
    add_activity, log_email, table_exists,
)

EXECUTION_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "execution")

DEFAULT_CONFIG = {
    "discovery_enabled": True,
    "discovery_cities": ["Boston", "Worcester", "Springfield", "Providence", "Hartford"],
    "discovery_state": "MA",
    "discovery_count": 20,
    "discovery_type": None,
    "enrichment_enabled": True,
    "sequence_enabled": True,
    "sequence_followup_1_days": 3,
    "sequence_followup_2_days": 7,
    "sequence_breakup_days": 14,
    "daily_send_limit": 50,
}


def load_config():
    config = dict(DEFAULT_CONFIG)
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "automation_config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path) as f:
                config.update(json.load(f))
        except (json.JSONDecodeError, IOError):
            pass
    return config


def save_config(config):
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "automation_config.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)


def run_discovery(city=None, state=None, count=20, business_type=None, demo=False):
    """Run the lead finder for a specific city."""
    job_id = add_automation_job("discovery", {
        "city": city, "state": state, "count": count, "type": business_type
    })

    finder_script = os.path.join(EXECUTION_DIR, "aventis_lead_finder.py")
    if not os.path.exists(finder_script):
        finish_automation_job(job_id, "error", {"error": "aventis_lead_finder.py not found"})
        return {"error": "Lead finder script not found"}

    cmd = [sys.executable, finder_script]
    if city:
        cmd.extend(["--city", city])
    if state:
        cmd.extend(["--state", state])
    if business_type:
        cmd.extend(["--type", business_type])
    cmd.extend(["--count", str(count)])
    cmd.extend(["--enrich", "--score", "--save-db"])
    if demo:
        cmd.append("--demo")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        output = result.stdout[-2000:] if result.stdout else ""
        errors = result.stderr[-1000:] if result.stderr else ""

        lines = output.split("\n")
        saved_count = 0
        for line in lines:
            if "saved to database" in line.lower() or "added to crm" in line.lower():
                try:
                    saved_count = int("".join(c for c in line.split(":")[0] if c.isdigit()) or "0")
                except ValueError:
                    pass

        finish_automation_job(job_id, "completed", {
            "leads_found": saved_count,
            "output_tail": output[-500:],
            "errors": errors[:500] if errors else ""
        })
        return {"success": True, "leads_found": saved_count, "job_id": job_id}

    except subprocess.TimeoutExpired:
        finish_automation_job(job_id, "timeout", {"error": "Discovery timed out after 5 minutes"})
        return {"error": "Timeout"}
    except Exception as e:
        finish_automation_job(job_id, "error", {"error": str(e)[:500]})
        return {"error": str(e)}


def run_daily_discovery(config=None):
    """Run discovery across all configured cities."""
    config = config or load_config()
    if not config.get("discovery_enabled"):
        return {"skipped": True, "reason": "Discovery disabled"}

    results = []
    cities = config.get("discovery_cities", ["Boston"])
    state = config.get("discovery_state", "MA")
    count = config.get("discovery_count", 20)
    btype = config.get("discovery_type")

    for city in cities:
        result = run_discovery(
            city=city, state=state, count=count,
            business_type=btype
        )
        results.append({"city": city, **result})
        time.sleep(2)

    total_found = sum(r.get("leads_found", 0) for r in results)
    return {"total_found": total_found, "cities": results}


def check_followups():
    """Check for leads needing follow-up emails based on sequence timing."""
    config = load_config()
    if not config.get("sequence_enabled"):
        return {"skipped": True}

    now = datetime.now()
    actions = []

    contacted_leads = get_leads(
        filters={"status": "contacted"},
        limit=500, sort_by="contact_date", sort_dir="ASC"
    )

    for lead in contacted_leads:
        contact_date_str = lead.get("contact_date") or lead.get("updated_at") or ""
        if not contact_date_str:
            continue
        try:
            contact_date = datetime.fromisoformat(contact_date_str.replace("Z", "+00:00").split("+")[0])
        except (ValueError, TypeError):
            continue

        days_since = (now - contact_date).days

        if days_since >= config.get("sequence_breakup_days", 14):
            actions.append({
                "lead_id": lead["id"],
                "business_name": lead["business_name"],
                "campaign": "breakup",
                "days_since": days_since
            })
        elif days_since >= config.get("sequence_followup_2_days", 7):
            actions.append({
                "lead_id": lead["id"],
                "business_name": lead["business_name"],
                "campaign": "followup_2",
                "days_since": days_since
            })
        elif days_since >= config.get("sequence_followup_1_days", 3):
            actions.append({
                "lead_id": lead["id"],
                "business_name": lead["business_name"],
                "campaign": "followup_1",
                "days_since": days_since
            })

    return {"pending_followups": actions, "count": len(actions)}


def run_outreach(campaign_key, min_score=0, limit=10, dry_run=True):
    """Run outreach for a specific campaign."""
    job_id = add_automation_job("outreach", {
        "campaign": campaign_key, "min_score": min_score,
        "limit": limit, "dry_run": dry_run
    })

    outreach_script = os.path.join(EXECUTION_DIR, "aventis_outreach.py")
    if not os.path.exists(outreach_script):
        finish_automation_job(job_id, "error", {"error": "aventis_outreach.py not found"})
        return {"error": "Outreach script not found"}

    cmd = [sys.executable, outreach_script,
           "--campaign", campaign_key,
           "--min-score", str(min_score),
           "--limit", str(limit)]

    if not dry_run:
        cmd.append("--mark-contacted")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        output = result.stdout[-2000:] if result.stdout else ""

        finish_automation_job(job_id, "completed", {
            "campaign": campaign_key,
            "output_tail": output[-500:],
            "dry_run": dry_run
        })
        return {"success": True, "job_id": job_id, "output": output[-500:]}

    except subprocess.TimeoutExpired:
        finish_automation_job(job_id, "timeout", {"error": "Outreach timed out"})
        return {"error": "Timeout"}
    except Exception as e:
        finish_automation_job(job_id, "error", {"error": str(e)[:500]})
        return {"error": str(e)}


def get_automation_status():
    """Return current automation state for the dashboard."""
    config = load_config()
    jobs = get_automation_jobs(10)
    followups = check_followups()

    last_discovery = None
    last_outreach = None
    for job in jobs:
        if job["job_type"] == "discovery" and not last_discovery:
            last_discovery = job
        elif job["job_type"] == "outreach" and not last_outreach:
            last_outreach = job

    return {
        "config": config,
        "recent_jobs": jobs,
        "pending_followups": followups.get("count", 0),
        "followup_details": followups.get("pending_followups", [])[:20],
        "last_discovery": last_discovery,
        "last_outreach": last_outreach,
    }


class AutomationScheduler:
    """Background thread scheduler for automated tasks."""

    def __init__(self, interval_hours=24):
        self.interval = interval_hours * 3600
        self.running = False
        self.thread = None
        self.last_run = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _loop(self):
        while self.running:
            try:
                config = load_config()
                if config.get("discovery_enabled"):
                    run_daily_discovery(config)
                self.last_run = datetime.now().isoformat()
            except Exception as e:
                print(f"[Automation] Error in scheduled run: {e}")

            for _ in range(int(self.interval)):
                if not self.running:
                    break
                time.sleep(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AventisAI Automation Engine")
    parser.add_argument("--action", choices=["discover", "followups", "outreach", "status", "daily"],
                        default="status")
    parser.add_argument("--city", default=None)
    parser.add_argument("--state", default="MA")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--type", dest="business_type", default=None)
    parser.add_argument("--campaign", default="intro")
    parser.add_argument("--min-score", type=int, default=50)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--send", action="store_true", help="Actually mark as contacted (not dry run)")
    args = parser.parse_args()

    init_db()

    if args.action == "discover":
        result = run_discovery(
            city=args.city, state=args.state,
            count=args.count, business_type=args.business_type,
            demo=args.demo
        )
        print(json.dumps(result, indent=2))

    elif args.action == "daily":
        result = run_daily_discovery()
        print(json.dumps(result, indent=2))

    elif args.action == "followups":
        result = check_followups()
        print(json.dumps(result, indent=2))

    elif args.action == "outreach":
        result = run_outreach(
            campaign_key=args.campaign,
            min_score=args.min_score,
            limit=args.limit,
            dry_run=not args.send
        )
        print(json.dumps(result, indent=2))

    elif args.action == "status":
        result = get_automation_status()
        print(json.dumps(result, indent=2, default=str))
