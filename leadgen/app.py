#!/usr/bin/env python3
"""
LeadPilot — Lead Generation Dashboard
Full-featured Flask app: dashboard, leads, pipeline, map, reports, activities.
"""

import argparse
import csv
import io
import os
import sys
import subprocess
from datetime import date, datetime
from functools import wraps
from threading import Thread

from flask import Flask, request, jsonify, render_template, Response

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import (
    init_db, get_leads, count_leads, get_lead_by_id, add_lead, update_lead,
    delete_lead, get_stats, get_scrape_logs, export_csv, add_leads_bulk,
    add_activity, get_activities, get_recent_activities, get_pipeline_data,
    save_search, get_saved_searches, delete_saved_search, PIPELINE_STAGES,
    update_scrape_status, get_scrape_status,
)
from utils import enrich_lead, normalize_phone, is_valid_phone, is_valid_email, calculate_lead_score

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", os.urandom(24).hex())

DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "")

with app.app_context():
    init_db()


def check_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not DASHBOARD_PASSWORD:
            return f(*args, **kwargs)
        auth = request.authorization
        if auth and auth.password == DASHBOARD_PASSWORD:
            return f(*args, **kwargs)
        return Response(
            "Login required", 401,
            {"WWW-Authenticate": 'Basic realm="LeadPilot"'}
        )
    return decorated


@app.route("/")
@check_auth
def dashboard():
    stats = get_stats()
    logs = get_scrape_logs(10)
    activities = get_recent_activities(10)
    return render_template("dashboard.html", stats=stats, logs=logs, activities=activities)


@app.route("/leads")
@check_auth
def leads_page():
    return render_template("leads.html", saved_searches=get_saved_searches())


@app.route("/pipeline")
@check_auth
def pipeline_page():
    return render_template("pipeline.html", stages=PIPELINE_STAGES)


@app.route("/map")
@check_auth
def map_page():
    return render_template("map.html")


@app.route("/reports")
@check_auth
def reports_page():
    return render_template("reports.html", stats=get_stats())


@app.route("/lead/<int:lead_id>")
@check_auth
def lead_detail_page(lead_id):
    lead = get_lead_by_id(lead_id)
    if not lead:
        return "Lead not found", 404
    activities = get_activities(lead_id)
    return render_template("lead_detail.html", lead=lead, activities=activities)


@app.route("/api/leads")
@check_auth
def api_leads():
    filters = {}
    for key in ["state", "city", "category", "status", "priority", "search",
                "date_from", "date_to", "tag", "source"]:
        val = request.args.get(key)
        if val:
            filters[key] = val

    if request.args.get("has_website") not in (None, ""):
        filters["has_website"] = request.args.get("has_website") == "1"

    if request.args.get("has_phone") == "1":
        filters["has_phone"] = True

    if request.args.get("min_score"):
        try:
            filters["min_score"] = int(request.args.get("min_score"))
        except (ValueError, TypeError):
            pass

    try:
        limit = min(int(request.args.get("limit", 200)), 1000)
        offset = max(int(request.args.get("offset", 0)), 0)
    except (ValueError, TypeError):
        limit, offset = 200, 0

    sort_by = request.args.get("sort_by", "lead_score")
    sort_dir = request.args.get("sort_dir", "DESC")

    leads = get_leads(filters, limit, offset, sort_by, sort_dir)
    total = count_leads(filters)
    return jsonify({"leads": leads, "count": len(leads), "total": total, "offset": offset, "limit": limit})


@app.route("/api/leads/<int:lead_id>", methods=["GET"])
@check_auth
def api_get_lead(lead_id):
    lead = get_lead_by_id(lead_id)
    if not lead:
        return jsonify({"error": "Lead not found"}), 404
    lead["activities"] = get_activities(lead_id, 20)
    return jsonify(lead)


@app.route("/api/leads/<int:lead_id>", methods=["PUT"])
@check_auth
def api_update_lead(lead_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    if "phone" in data:
        data["phone"] = normalize_phone(data["phone"])
    update_lead(lead_id, data)
    return jsonify({"success": True})


@app.route("/api/leads/<int:lead_id>", methods=["DELETE"])
@check_auth
def api_delete_lead(lead_id):
    delete_lead(lead_id)
    return jsonify({"success": True})


@app.route("/api/leads", methods=["POST"])
@check_auth
def api_add_lead():
    data = request.get_json()
    if not data or not data.get("business_name"):
        return jsonify({"error": "business_name required"}), 400
    if "phone" in data:
        data["phone"] = normalize_phone(data["phone"])
    enrich_lead(data)
    lead_id = add_lead(data)
    if lead_id is None:
        return jsonify({"error": "Lead already exists"}), 409
    return jsonify({"success": True, "id": lead_id}), 201


@app.route("/api/leads/bulk-update", methods=["POST"])
@check_auth
def api_bulk_update():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    ids = data.get("ids", [])
    updates = data.get("updates", {})
    if not ids or not updates:
        return jsonify({"error": "ids and updates required"}), 400
    for lead_id in ids:
        update_lead(lead_id, updates)
    return jsonify({"success": True, "updated": len(ids)})


@app.route("/api/leads/<int:lead_id>/activities", methods=["GET"])
@check_auth
def api_get_activities(lead_id):
    return jsonify(get_activities(lead_id))


@app.route("/api/leads/<int:lead_id>/activities", methods=["POST"])
@check_auth
def api_add_activity(lead_id):
    data = request.get_json() or {}
    activity_type = data.get("type", "note")
    note = data.get("note", "")
    if not note:
        return jsonify({"error": "note required"}), 400
    add_activity(lead_id, activity_type, note)
    return jsonify({"success": True})


@app.route("/api/pipeline")
@check_auth
def api_pipeline():
    return jsonify(get_pipeline_data())


@app.route("/api/stats")
@check_auth
def api_stats():
    return jsonify(get_stats())


@app.route("/api/saved-searches", methods=["GET"])
@check_auth
def api_saved_searches():
    return jsonify(get_saved_searches())


@app.route("/api/saved-searches", methods=["POST"])
@check_auth
def api_save_search():
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    filters = data.get("filters", {})
    if not name:
        return jsonify({"error": "name required"}), 400
    save_search(name, filters)
    return jsonify({"success": True})


@app.route("/api/saved-searches/<int:search_id>", methods=["DELETE"])
@check_auth
def api_delete_saved_search(search_id):
    delete_saved_search(search_id)
    return jsonify({"success": True})


@app.route("/api/export")
@check_auth
def api_export():
    filters = {}
    for key in ["state", "city", "category", "status", "priority", "tag"]:
        val = request.args.get(key)
        if val:
            filters[key] = val
    if request.args.get("has_website") not in (None, ""):
        filters["has_website"] = request.args.get("has_website") == "1"

    csv_data = export_csv(filters)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=leadpilot_export_{date.today()}.csv"}
    )


@app.route("/api/run-scraper", methods=["POST"])
@check_auth
def api_run_scraper():
    data = request.get_json() or {}
    source = data.get("source", "all")
    state = data.get("state")

    allowed_sources = {"all", "overpass", "nominatim", "yp", "sos"}
    allowed_states = {"MA", "RI", "CT", None}
    if source not in allowed_sources or state not in allowed_states:
        return jsonify({"error": "Invalid source or state"}), 400

    # Refuse to start if one is already running
    current = get_scrape_status()
    if current.get("running"):
        return jsonify({
            "error": "Scraper already running",
            "current_step": current.get("current_step"),
            "leads_so_far": current.get("leads_so_far"),
        }), 409

    update_scrape_status(running=1, starting=True, source=source,
                         state=state or "ALL", current_step="Initializing...",
                         progress_pct=0, leads_so_far=0)

    def run_in_background():
        cmd = [sys.executable, "-u",
               os.path.join(os.path.dirname(__file__), "daily_runner.py")]
        if source != "all":
            cmd.extend(["--source", source])
        if state:
            cmd.extend(["--state", state])
        if data.get("only_no_website"):
            cmd.append("--only-no-website")
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        except subprocess.TimeoutExpired:
            update_scrape_status(running=0,
                                 current_step="Timeout after 30 minutes",
                                 progress_pct=100)
        except Exception as e:
            update_scrape_status(running=0,
                                 current_step=f"Error: {str(e)[:100]}",
                                 progress_pct=100)

    thread = Thread(target=run_in_background, daemon=True)
    thread.start()

    return jsonify({"success": True, "message": "Scraper started"})


@app.route("/api/scraper-status")
@check_auth
def api_scraper_status():
    """Live status of the running scraper. UI polls this every 2s."""
    return jsonify(get_scrape_status())


@app.route("/api/test-scrape", methods=["POST"])
@check_auth
def api_test_scrape():
    """Synchronous quick test — returns sample leads inline without saving.
    Used to verify scrapers work and give the user immediate feedback."""
    from scrapers.overpass_scraper import scrape_overpass
    from scrapers.nominatim_scraper import scrape_nominatim

    data = request.get_json() or {}
    source = data.get("source", "overpass")
    state = data.get("state", "MA")

    try:
        if source == "nominatim":
            leads, error = scrape_nominatim(state, max_per_query=3)
            leads = leads[:10]
        else:
            # default: overpass with a small sample (1 city only)
            from scrapers.overpass_scraper import CITIES, build_query, query_overpass, parse_element
            cities = CITIES.get(state, CITIES["MA"])[:1]  # just first city
            leads = []
            error = ""
            for city_name, lat, lng in cities:
                query = build_query(lat, lng)
                d, err = query_overpass(query)
                if err:
                    error = f"{city_name}: {err}"
                    continue
                if d:
                    for el in d.get("elements", [])[:30]:
                        lead = parse_element(el, city_name, state)
                        if lead and (lead["phone"] or lead["email"]):
                            leads.append(lead)
                            if len(leads) >= 10:
                                break

        return jsonify({
            "success": True,
            "source": source,
            "state": state,
            "leads": leads,
            "count": len(leads),
            "error": error,
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)[:300],
            "leads": [],
            "count": 0,
        }), 500


@app.route("/api/import-csv", methods=["POST"])
@check_auth
def api_import_csv():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename or not file.filename.endswith(".csv"):
        return jsonify({"error": "Must be a CSV file"}), 400

    try:
        content = file.read().decode("utf-8")
    except UnicodeDecodeError:
        content = file.read().decode("latin-1", errors="ignore")

    reader = csv.DictReader(io.StringIO(content))
    leads = []
    for row in reader:
        has_website_raw = row.get("has_website", "No").strip().lower()
        has_website = 1 if has_website_raw in ("yes", "basic", "1", "true") else 0
        lead = {
            "business_name": row.get("name", row.get("business_name", "")).strip(),
            "category": row.get("category", "").strip(),
            "business_type": row.get("business_type", "").strip(),
            "phone": normalize_phone(row.get("phone", "").strip()),
            "email": row.get("email", "").strip(),
            "address": row.get("address", "").strip(),
            "city": row.get("city", "").strip(),
            "state": row.get("state", "").strip(),
            "has_website": has_website,
            "marketing_score": 3 if has_website else 0,
            "priority": "medium" if has_website else "high",
            "date_found": row.get("date_found", date.today().isoformat()).strip(),
            "source": f"CSV Upload: {file.filename}",
            "notes": row.get("notes", "").strip(),
            "status": "new",
        }
        enrich_lead(lead)
        if lead["business_name"]:
            leads.append(lead)

    added = add_leads_bulk(leads)
    return jsonify({"success": True, "total": len(leads), "added": added})


@app.route("/api/logs")
@check_auth
def api_logs():
    logs = get_scrape_logs(50)
    return jsonify(logs)


@app.route("/api/health")
def api_health():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    print(f"\n  LeadPilot — Lead Generation Dashboard")
    print(f"  http://localhost:{args.port}")
    print(f"  Auth: {'ON' if DASHBOARD_PASSWORD else 'OFF (set DASHBOARD_PASSWORD env var)'}")
    print()
    app.run(host="0.0.0.0", port=args.port, debug=args.debug)
