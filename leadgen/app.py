#!/usr/bin/env python3
"""
One Vision Marketing — Lead Generation Dashboard
Flask web app for viewing, filtering, searching, and managing leads.

Usage:
  python leadgen/app.py              # Start on port 5000
  python leadgen/app.py --port 8080  # Custom port
"""

import argparse
import csv
import io
import json
import os
import sys
import subprocess
from datetime import date, datetime
from threading import Thread

from flask import Flask, request, jsonify, render_template, Response, redirect, url_for

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import (
    init_db, get_leads, get_lead_by_id, add_lead, update_lead,
    delete_lead, get_stats, get_scrape_logs, export_csv, add_leads_bulk
)

app = Flask(__name__, template_folder="templates", static_folder="static")


@app.route("/")
def dashboard():
    stats = get_stats()
    logs = get_scrape_logs(10)
    return render_template("dashboard.html", stats=stats, logs=logs)


@app.route("/leads")
def leads_page():
    return render_template("leads.html")


@app.route("/api/leads")
def api_leads():
    filters = {}
    for key in ["state", "city", "category", "status", "priority", "search", "date_from", "date_to"]:
        val = request.args.get(key)
        if val:
            filters[key] = val

    if request.args.get("has_website") is not None and request.args.get("has_website") != "":
        filters["has_website"] = request.args.get("has_website") == "1"

    if request.args.get("min_score"):
        filters["min_score"] = request.args.get("min_score")

    limit = min(int(request.args.get("limit", 200)), 1000)
    offset = int(request.args.get("offset", 0))
    sort_by = request.args.get("sort_by", "date_found")
    sort_dir = request.args.get("sort_dir", "DESC")

    leads = get_leads(filters, limit, offset, sort_by, sort_dir)
    return jsonify({"leads": leads, "count": len(leads), "offset": offset, "limit": limit})


@app.route("/api/leads/<int:lead_id>", methods=["GET"])
def api_get_lead(lead_id):
    lead = get_lead_by_id(lead_id)
    if not lead:
        return jsonify({"error": "Lead not found"}), 404
    return jsonify(lead)


@app.route("/api/leads/<int:lead_id>", methods=["PUT"])
def api_update_lead(lead_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    update_lead(lead_id, data)
    return jsonify({"success": True})


@app.route("/api/leads/<int:lead_id>", methods=["DELETE"])
def api_delete_lead(lead_id):
    delete_lead(lead_id)
    return jsonify({"success": True})


@app.route("/api/leads", methods=["POST"])
def api_add_lead():
    data = request.get_json()
    if not data or not data.get("business_name"):
        return jsonify({"error": "business_name required"}), 400
    lead_id = add_lead(data)
    if lead_id is None:
        return jsonify({"error": "Lead already exists"}), 409
    return jsonify({"success": True, "id": lead_id}), 201


@app.route("/api/leads/bulk-update", methods=["POST"])
def api_bulk_update():
    data = request.get_json()
    ids = data.get("ids", [])
    updates = data.get("updates", {})
    if not ids or not updates:
        return jsonify({"error": "ids and updates required"}), 400
    for lead_id in ids:
        update_lead(lead_id, updates)
    return jsonify({"success": True, "updated": len(ids)})


@app.route("/api/stats")
def api_stats():
    return jsonify(get_stats())


@app.route("/api/export")
def api_export():
    filters = {}
    for key in ["state", "city", "category", "status", "priority", "has_website"]:
        val = request.args.get(key)
        if val:
            filters[key] = val
    if request.args.get("has_website") is not None and request.args.get("has_website") != "":
        filters["has_website"] = request.args.get("has_website") == "1"

    csv_data = export_csv(filters)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=leads_export_{date.today()}.csv"}
    )


@app.route("/api/run-scraper", methods=["POST"])
def api_run_scraper():
    data = request.get_json() or {}
    source = data.get("source", "all")
    state = data.get("state")

    def run_in_background():
        cmd = [sys.executable, os.path.join(os.path.dirname(__file__), "daily_runner.py")]
        if source != "all":
            cmd.extend(["--source", source])
        if state:
            cmd.extend(["--state", state])
        subprocess.run(cmd, capture_output=True, text=True)

    thread = Thread(target=run_in_background)
    thread.start()

    return jsonify({"success": True, "message": "Scraper started in background"})


@app.route("/api/import-csv", methods=["POST"])
def api_import_csv():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename.endswith(".csv"):
        return jsonify({"error": "Must be a CSV file"}), 400

    content = file.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))
    leads = []
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
            "marketing_score": 3 if has_website else 0,
            "priority": "medium" if has_website else "high",
            "date_found": row.get("date_found", date.today().isoformat()).strip(),
            "source": f"CSV Upload: {file.filename}",
            "notes": row.get("notes", "").strip(),
            "status": "new",
        }
        if lead["business_name"]:
            leads.append(lead)

    added = add_leads_bulk(leads)
    return jsonify({"success": True, "total": len(leads), "added": added})


@app.route("/api/logs")
def api_logs():
    logs = get_scrape_logs(50)
    return jsonify(logs)


if __name__ == "__main__":
    init_db()
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    print(f"\n  One Vision Marketing — Lead Dashboard")
    print(f"  http://localhost:{args.port}")
    print()
    app.run(host="0.0.0.0", port=args.port, debug=args.debug)
