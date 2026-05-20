#!/usr/bin/env python3
"""
AventisAI — 2026 Lead Generation CRM
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
    get_db, init_db, get_leads, count_leads, get_lead_by_id, add_lead, update_lead,
    delete_lead, get_stats, get_scrape_logs, clear_scrape_logs, export_csv, add_leads_bulk,
    add_activity, get_activities, get_recent_activities, get_pipeline_data,
    save_search, get_saved_searches, delete_saved_search, PIPELINE_STAGES,
    update_scrape_status, get_scrape_status,
    get_email_settings, update_email_settings,
    save_email_template, get_email_templates, get_email_template, delete_email_template,
    get_email_log, log_email, get_recent_leads,
    get_campaigns, save_campaign, get_automation_jobs, get_funnel_analytics,
    wipe_all_leads,
)
from utils import enrich_lead, normalize_phone
from email_service import send_email, send_bulk_emails, render_template as render_email_template, DEFAULT_TEMPLATES

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", os.urandom(24).hex())
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB upload cap

DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "")
MAX_CSV_LEADS = 25000


@app.errorhandler(413)
def request_too_large(e):
    return jsonify({"error": "Upload exceeds 16 MB limit"}), 413

with app.app_context():
    init_db()

# Start automation scheduler as a background thread (checks config before running)
try:
    from automation_engine import AutomationScheduler
    _auto_scheduler = AutomationScheduler(interval_hours=12)
    _auto_scheduler.start()
except Exception as e:
    print(f"[Automation] Scheduler failed to start: {e}")
    _auto_scheduler = None


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
            {"WWW-Authenticate": 'Basic realm="AventisAI"'}
        )
    return decorated


@app.route("/")
@check_auth
def dashboard():
    stats = get_stats()
    logs = get_scrape_logs(10)
    activities = get_recent_activities(10)
    recent_leads = get_recent_leads(5)
    return render_template("dashboard.html", stats=stats, logs=logs, activities=activities, recent_leads=recent_leads)


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


@app.route("/email")
@check_auth
def email_page():
    templates = get_email_templates()
    if not templates:
        for t in DEFAULT_TEMPLATES:
            save_email_template(t["name"], t["subject"], t["body"])
        templates = get_email_templates()
    settings = get_email_settings()
    recent_emails = get_email_log(20)
    return render_template("email.html", templates=templates, settings=settings, recent_emails=recent_emails)


@app.route("/content")
@check_auth
def content_page():
    return render_template("content.html")


@app.route("/api/content/generate", methods=["POST"])
@check_auth
def api_content_generate():
    data = request.get_json() or {}
    content_type = data.get("type", "post")
    pillar = data.get("pillar")
    city = data.get("city")
    count = min(int(data.get("count", 1)), 30)
    owner = data.get("owner", "")
    brand = data.get("brand", "")

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "execution"))
    from generate_instagram import (
        generate_post, generate_carousel, generate_reel,
        generate_story, generate_calendar,
    )

    if content_type == "post":
        results = [generate_post(pillar=pillar, city=city, owner=owner, brand=brand) for _ in range(count)]
    elif content_type == "carousel":
        results = [generate_carousel(topic_pillar=pillar, owner=owner, brand=brand) for _ in range(count)]
    elif content_type == "reel":
        results = [generate_reel(owner=owner, brand=brand) for _ in range(count)]
    elif content_type == "story":
        results = [generate_story() for _ in range(count)]
    elif content_type == "calendar":
        results = generate_calendar(days=count, owner=owner, brand=brand)
    else:
        return jsonify({"error": "Invalid content type"}), 400

    return jsonify({"success": True, "content": results, "type": content_type})


@app.route("/lead/<int:lead_id>")
@check_auth
def lead_detail_page(lead_id):
    lead = get_lead_by_id(lead_id)
    if not lead:
        return "Lead not found", 404
    activities = get_activities(lead_id)
    emails = get_email_log(10, lead_id=lead_id)
    return render_template("lead_detail.html", lead=lead, activities=activities, emails=emails)


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

    if request.args.get("has_email") == "1":
        filters["has_email"] = True

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
    lead = get_lead_by_id(lead_id)
    if not lead:
        return jsonify({"error": "Lead not found"}), 404
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

    ids_param = request.args.get("ids", "").strip()
    if ids_param:
        try:
            id_list = [int(x) for x in ids_param.split(",") if x.strip().isdigit()]
            filters["ids"] = id_list[:10000]
        except (ValueError, TypeError):
            pass

    csv_data = export_csv(filters)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=aventisai_export_{date.today()}.csv"}
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
        if data.get("only_new_businesses"):
            cmd.append("--only-new-businesses")
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
        print(f"[test-scrape] error: {e}")
        return jsonify({
            "success": False,
            "error": "Test scrape failed — the data source may be temporarily unavailable. Try a different source.",
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

    raw_bytes = file.read()
    try:
        content = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        content = raw_bytes.decode("latin-1", errors="ignore")

    reader = csv.DictReader(io.StringIO(content))
    leads = []
    for i, row in enumerate(reader):
        if i >= MAX_CSV_LEADS:
            return jsonify({
                "error": f"CSV exceeds {MAX_CSV_LEADS}-lead limit per import. Split into smaller files."
            }), 400
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


@app.route("/api/logs/clear", methods=["POST"])
@check_auth
def api_clear_logs():
    only_errors = (request.get_json() or {}).get("only_errors", False)
    clear_scrape_logs(only_errors=only_errors)
    return jsonify({"success": True})


# --- Email API ---

@app.route("/api/email/settings", methods=["GET"])
@check_auth
def api_email_settings_get():
    settings = get_email_settings()
    settings.pop("smtp_pass", None)
    return jsonify(settings)


@app.route("/api/email/settings", methods=["POST"])
@check_auth
def api_email_settings_update():
    data = request.get_json() or {}
    update_email_settings(data)
    return jsonify({"success": True})


@app.route("/api/email/templates", methods=["GET"])
@check_auth
def api_email_templates_list():
    return jsonify(get_email_templates())


@app.route("/api/email/templates", methods=["POST"])
@check_auth
def api_email_template_save():
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    subject = data.get("subject", "").strip()
    body = data.get("body", "").strip()
    tid = data.get("id")
    if not name or not subject:
        return jsonify({"error": "name and subject required"}), 400
    save_email_template(name, subject, body, template_id=tid)
    return jsonify({"success": True})


@app.route("/api/email/templates/<int:tid>", methods=["DELETE"])
@check_auth
def api_email_template_delete(tid):
    delete_email_template(tid)
    return jsonify({"success": True})


@app.route("/api/email/send", methods=["POST"])
@check_auth
def api_email_send():
    data = request.get_json() or {}
    to_email = data.get("to_email", "").strip()
    subject = data.get("subject", "").strip()
    body = data.get("body", "").strip()
    lead_id = data.get("lead_id")
    template_id = data.get("template_id")

    if not to_email or not subject:
        return jsonify({"error": "to_email and subject required"}), 400

    ok, err = send_email(to_email, subject, body, lead_id=lead_id, template_id=template_id)
    if ok:
        return jsonify({"success": True})
    return jsonify({"error": err}), 400


@app.route("/api/email/send-bulk", methods=["POST"])
@check_auth
def api_email_send_bulk():
    data = request.get_json() or {}
    lead_ids = data.get("lead_ids", [])
    subject_template = data.get("subject", "").strip()
    body_template = data.get("body", "").strip()
    template_id = data.get("template_id")

    if not lead_ids or not subject_template:
        return jsonify({"error": "lead_ids and subject required"}), 400

    leads = []
    for lid in lead_ids:
        lead = get_lead_by_id(lid)
        if lead and lead.get("email"):
            leads.append(lead)

    if not leads:
        return jsonify({"error": "No leads with email addresses in selection"}), 400

    sent, errors = send_bulk_emails(leads, subject_template, body_template, template_id)
    return jsonify({"success": True, "sent": sent, "errors": errors[:10]})


@app.route("/api/email/preview", methods=["POST"])
@check_auth
def api_email_preview():
    data = request.get_json() or {}
    lead_id = data.get("lead_id")
    subject = data.get("subject", "")
    body = data.get("body", "")

    lead = {}
    if lead_id:
        lead = get_lead_by_id(lead_id) or {}

    return jsonify({
        "subject": render_email_template(subject, lead),
        "body": render_email_template(body, lead),
    })


@app.route("/api/email/log")
@check_auth
def api_email_log_list():
    lead_id = request.args.get("lead_id", type=int)
    return jsonify(get_email_log(50, lead_id=lead_id))


@app.route("/api/categories")
@check_auth
def api_categories():
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT category FROM leads WHERE category != '' ORDER BY category").fetchall()
    conn.close()
    return jsonify([row["category"] for row in rows])


@app.route("/api/cities")
@check_auth
def api_cities():
    state = request.args.get("state")
    conn = get_db()
    if state:
        rows = conn.execute("SELECT DISTINCT city FROM leads WHERE city != '' AND state = ? ORDER BY city", (state,)).fetchall()
    else:
        rows = conn.execute("SELECT DISTINCT city FROM leads WHERE city != '' ORDER BY city").fetchall()
    conn.close()
    return jsonify([row["city"] for row in rows])


@app.route("/automation")
@check_auth
def automation_page():
    return render_template("automation.html")


@app.route("/api/automation/status")
@check_auth
def api_automation_status():
    from automation_engine import get_automation_status
    status = get_automation_status()
    status["scheduler_running"] = _auto_scheduler.running if _auto_scheduler else False
    status["scheduler_last_run"] = _auto_scheduler.last_run if _auto_scheduler else None
    return jsonify(status)


@app.route("/api/automation/config", methods=["GET"])
@check_auth
def api_automation_config_get():
    from automation_engine import load_config
    return jsonify(load_config())


@app.route("/api/automation/config", methods=["POST"])
@check_auth
def api_automation_config_save():
    from automation_engine import load_config, save_config
    data = request.get_json() or {}
    config = load_config()
    config.update(data)
    save_config(config)
    return jsonify({"success": True})


@app.route("/api/automation/discover", methods=["POST"])
@check_auth
def api_automation_discover():
    from automation_engine import run_discovery
    data = request.get_json() or {}

    def run_bg():
        run_discovery(
            city=data.get("city"),
            state=data.get("state", "MA"),
            count=data.get("count", 20),
            business_type=data.get("type"),
            demo=data.get("demo", False)
        )

    thread = Thread(target=run_bg, daemon=True)
    thread.start()
    return jsonify({"success": True, "message": "Discovery started"})


@app.route("/api/automation/outreach", methods=["POST"])
@check_auth
def api_automation_outreach():
    from automation_engine import run_outreach
    data = request.get_json() or {}
    campaign = data.get("campaign", "intro")
    min_score = data.get("min_score", 50)
    limit = data.get("limit", 10)
    dry_run = data.get("dry_run", True)

    def run_bg():
        run_outreach(campaign, min_score, limit, dry_run)

    thread = Thread(target=run_bg, daemon=True)
    thread.start()
    return jsonify({"success": True, "message": f"Outreach '{campaign}' started"})


@app.route("/api/automation/followups")
@check_auth
def api_automation_followups():
    from automation_engine import check_followups
    return jsonify(check_followups())


@app.route("/api/automation/jobs")
@check_auth
def api_automation_jobs():
    return jsonify(get_automation_jobs(30))


@app.route("/api/analytics/funnel")
@check_auth
def api_funnel_analytics():
    return jsonify(get_funnel_analytics())


@app.route("/api/campaigns")
@check_auth
def api_campaigns_list():
    return jsonify(get_campaigns())


@app.route("/api/campaigns", methods=["POST"])
@check_auth
def api_campaign_save():
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    key = data.get("campaign_key", "").strip()
    if not name or not key:
        return jsonify({"error": "name and campaign_key required"}), 400
    save_campaign(name, key, data.get("target_filters"), data.get("sequence_steps"), data.get("id"))
    return jsonify({"success": True})


@app.route("/api/leads/wipe", methods=["POST"])
@check_auth
def api_wipe_leads():
    """Delete ALL leads and related data. Fresh start."""
    wipe_all_leads()
    return jsonify({"success": True, "message": "All leads wiped"})


# --- City coordinates for map (server-side) ---
CITY_COORDS = {
    "Boston,MA":[42.3601,-71.0589],"Worcester,MA":[42.2626,-71.8023],"Springfield,MA":[42.1015,-72.5898],
    "Brockton,MA":[42.0834,-71.0184],"New Bedford,MA":[41.6362,-70.9342],"Lowell,MA":[42.6334,-71.3162],
    "Fall River,MA":[41.7015,-71.155],"Taunton,MA":[41.9006,-71.0898],"Plymouth,MA":[41.9584,-70.6673],
    "Framingham,MA":[42.2793,-71.4162],"Cambridge,MA":[42.3736,-71.1097],"Quincy,MA":[42.2529,-71.0023],
    "Newton,MA":[42.337,-71.2092],"Somerville,MA":[42.3876,-71.0995],"Pittsfield,MA":[42.45,-73.25],
    "Haverhill,MA":[42.7762,-71.0773],"Lynn,MA":[42.4668,-70.9495],"Lawrence,MA":[42.707,-71.1631],
    "Medford,MA":[42.4184,-71.1062],"Malden,MA":[42.4251,-71.0662],"Waltham,MA":[42.3765,-71.2356],
    "Brookline,MA":[42.3318,-71.1212],"Revere,MA":[42.4084,-71.012],"Peabody,MA":[42.528,-70.9286],
    "Methuen,MA":[42.7262,-71.1909],"Attleboro,MA":[41.9445,-71.2856],"Leominster,MA":[42.5251,-71.7598],
    "Fitchburg,MA":[42.5834,-71.8023],"Salem,MA":[42.5195,-70.8967],"Beverly,MA":[42.5584,-70.88],
    "Chicopee,MA":[42.1487,-72.6079],"Holyoke,MA":[42.2042,-72.6162],"Westfield,MA":[42.1251,-72.7495],
    "Gloucester,MA":[42.6159,-70.6628],"Marlborough,MA":[42.3459,-71.5523],"Natick,MA":[42.2834,-71.3495],
    "Weymouth,MA":[42.2209,-70.9395],"Barnstable,MA":[41.7003,-70.2962],"Falmouth,MA":[41.5514,-70.6148],
    "Norwood,MA":[42.1945,-71.1995],"Needham,MA":[42.2834,-71.2328],"Dedham,MA":[42.2418,-71.1662],
    "Braintree,MA":[42.2034,-70.998],"Randolph,MA":[42.1626,-71.0412],"Stoughton,MA":[42.1251,-71.0995],
    "Canton,MA":[42.1584,-71.1448],"Franklin,MA":[42.0834,-71.3967],"Milford,MA":[42.14,-71.5162],
    "Mansfield,MA":[42.0334,-71.2195],"Bridgewater,MA":[41.9901,-70.975],"Easton,MA":[42.0234,-71.1295],
    "Abington,MA":[42.1051,-70.9445],"Rockland,MA":[42.1309,-70.9078],"Hanover,MA":[42.1126,-70.8128],
    "Hingham,MA":[42.2301,-70.8895],"Northampton,MA":[42.3259,-72.6412],"Amherst,MA":[42.3751,-72.5195],
    "Providence,RI":[41.824,-71.4128],"Warwick,RI":[41.7001,-71.4162],"Cranston,RI":[41.7798,-71.4373],
    "Pawtucket,RI":[41.8787,-71.3826],"East Providence,RI":[41.8137,-71.3701],"Newport,RI":[41.4901,-71.3128],
    "Woonsocket,RI":[42.0029,-71.5148],"Coventry,RI":[41.6898,-71.5673],"North Providence,RI":[41.8501,-71.4595],
    "Cumberland,RI":[41.9701,-71.4328],"West Warwick,RI":[41.697,-71.5218],"Johnston,RI":[41.8218,-71.5128],
    "North Kingstown,RI":[41.5501,-71.4628],"South Kingstown,RI":[41.4434,-71.5228],"Westerly,RI":[41.378,-71.827],
    "Bristol,RI":[41.6737,-71.2662],"Barrington,RI":[41.7401,-71.3078],"Middletown,RI":[41.5184,-71.2878],
    "Tiverton,RI":[41.6251,-71.2128],"Lincoln,RI":[41.9201,-71.4378],"Smithfield,RI":[41.9001,-71.5278],
    "Central Falls,RI":[41.8901,-71.3928],"Warren,RI":[41.7301,-71.2828],
    "Hartford,CT":[41.7658,-72.6734],"New Haven,CT":[41.3083,-72.9279],"Bridgeport,CT":[41.1865,-73.1952],
    "Stamford,CT":[41.0534,-73.5387],"Waterbury,CT":[41.5582,-73.0515],"Norwalk,CT":[41.1177,-73.4082],
    "Danbury,CT":[41.4015,-73.454],"New Britain,CT":[41.6612,-72.7795],"West Hartford,CT":[41.762,-72.742],
    "Meriden,CT":[41.5382,-72.807],"Middletown,CT":[41.5623,-72.6506],"Bristol,CT":[41.6718,-72.9462],
    "Manchester,CT":[41.7759,-72.5215],"East Hartford,CT":[41.7826,-72.6182],"Enfield,CT":[41.9762,-72.5918],
    "Milford,CT":[41.2226,-73.0568],"Shelton,CT":[41.2068,-73.1318],"Stratford,CT":[41.1845,-73.1318],
    "Torrington,CT":[41.8007,-73.1212],"Groton,CT":[41.3501,-72.0778],"New London,CT":[41.3557,-72.0995],
    "Norwich,CT":[41.5242,-72.0762],"Hamden,CT":[41.3959,-72.8968],"West Haven,CT":[41.2712,-72.947],
    "Guilford,CT":[41.2884,-72.6818],"Branford,CT":[41.2784,-72.8151],"Wallingford,CT":[41.457,-72.8232],
    "Southington,CT":[41.5959,-72.8779],"Farmington,CT":[41.7198,-72.832],"Newington,CT":[41.698,-72.7246],
    "Glastonbury,CT":[41.7123,-72.608],"Wethersfield,CT":[41.7143,-72.6529],
}


@app.route("/api/map-data")
@check_auth
def api_map_data():
    """Return leads with coordinates for the map. Fills in lat/lng from city lookup when missing."""
    filters = {}
    for key in ["state", "category", "priority"]:
        val = request.args.get(key)
        if val:
            filters[key] = val
    if request.args.get("has_website") not in (None, ""):
        filters["has_website"] = request.args.get("has_website") == "1"

    leads = get_leads(filters, limit=2000, offset=0, sort_by="lead_score", sort_dir="DESC")

    result = []
    for lead in leads:
        lat = lead.get("latitude")
        lng = lead.get("longitude")

        if not lat or not lng:
            city = (lead.get("city") or "").strip()
            state = (lead.get("state") or "").strip()
            key = f"{city},{state}"
            coords = CITY_COORDS.get(key)
            if not coords:
                key_lower = key.lower()
                for k, v in CITY_COORDS.items():
                    if k.lower() == key_lower:
                        coords = v
                        break
            if coords:
                lat, lng = coords[0], coords[1]

        if lat and lng:
            result.append({
                "id": lead["id"],
                "business_name": lead["business_name"],
                "category": lead.get("category", ""),
                "phone": lead.get("phone", ""),
                "email": lead.get("email", ""),
                "address": lead.get("address", ""),
                "city": lead.get("city", ""),
                "state": lead.get("state", ""),
                "has_website": lead.get("has_website", 0),
                "website_url": lead.get("website_url", ""),
                "priority": lead.get("priority", ""),
                "lead_score": lead.get("lead_score", 0),
                "status": lead.get("status", "new"),
                "lat": lat,
                "lng": lng,
            })

    return jsonify({
        "leads": result,
        "total_in_db": count_leads(filters),
        "mapped": len(result),
    })


@app.route("/api/health")
def api_health():
    db_ok = False
    db_kind = "postgres" if os.environ.get("DATABASE_URL") else "sqlite"
    try:
        from database import get_db
        conn = get_db()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        db_ok = True
    except Exception as e:
        return jsonify({
            "status": "degraded",
            "database": db_kind,
            "db_ok": False,
            "error": str(e)[:200],
            "timestamp": datetime.now().isoformat(),
        }), 503
    return jsonify({
        "status": "ok",
        "database": db_kind,
        "db_ok": db_ok,
        "timestamp": datetime.now().isoformat(),
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    print(f"\n  AventisAI — 2026 Lead Generation CRM")
    print(f"  http://localhost:{args.port}")
    print(f"  Auth: {'ON' if DASHBOARD_PASSWORD else 'OFF (set DASHBOARD_PASSWORD env var)'}")
    print()
    app.run(host="0.0.0.0", port=args.port, debug=args.debug)
