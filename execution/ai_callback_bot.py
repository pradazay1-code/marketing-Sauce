#!/usr/bin/env python3
"""
AI Callback Bot — Instant Lead Callback System
Aventis Marketing / OneVision Marketing

Triggers AI voice callbacks to new leads within 60 seconds of form submission.
Speed-to-lead is the #1 predictor of conversion — this system responds instantly.

USE CASES:
- New lead fills form on your website → AI calls them in 60 seconds
- Facebook Lead Ad submission → AI calls them
- Missed call to your business → AI calls back
- Abandoned checkout / scheduling → AI recovery call

SUPPORTED PLATFORMS:
- Bland.ai (recommended — easiest, per-minute pricing ~$0.09/min)
- Synthflow.ai (best all-in-one, ~$99/mo)
- Vapi.ai (developer-friendly, per-usage)

USAGE:

1. Direct trigger (one-off callback):
   python ai_callback_bot.py --phone "+15551234567" --name "John" \\
     --prompt onevision_marketing

2. Run as webhook server (auto-triggers on form submissions):
   python ai_callback_bot.py --serve --port 5000

3. Configure Facebook Lead Ads / your website to POST to:
   https://your-server.com/webhook/lead

SETUP:
- Sign up: https://www.bland.ai (free credits to start)
- Get API key from dashboard
- Add to .env: BLAND_API_KEY=your_key_here
- (Optional) BLAND_VOICE_ID=voice_id (default: professional female)
- (Optional) CALLBACK_WEBHOOK_URL=https://your-server.com/webhook/lead-result
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests flask")
    sys.exit(1)

try:
    from flask import Flask, request, jsonify
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai_callback_prompts import PROMPT_LIBRARY, get_prompt

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BLAND_API_URL = "https://api.bland.ai/v1/calls"
BLAND_API_KEY = os.environ.get("BLAND_API_KEY", "")
DEFAULT_VOICE = os.environ.get("BLAND_VOICE_ID", "maya")  # Bland default warm female
CALLBACK_LOG = os.path.join(BASE_DIR, "clients", "aventisai", "callback_log.json")


# ---------------------------------------------------------------------------
# Bland.ai Integration
# ---------------------------------------------------------------------------

def make_callback(phone, first_name, prompt_key, extra_vars=None):
    """Trigger an AI callback to a lead via Bland.ai."""
    if not BLAND_API_KEY:
        raise RuntimeError(
            "BLAND_API_KEY not set. Sign up at https://www.bland.ai, get your key, "
            "and add it to .env or export BLAND_API_KEY=your_key"
        )

    format_vars = {"first_name": first_name or "there"}
    if extra_vars:
        format_vars.update(extra_vars)

    prompt = get_prompt(prompt_key, **format_vars)

    payload = {
        "phone_number": normalize_phone(phone),
        "task": prompt["system_prompt"],
        "first_sentence": prompt["first_message"],
        "voice": DEFAULT_VOICE,
        "wait_for_greeting": True,
        "record": True,
        "max_duration": prompt.get("max_call_duration_seconds", 300) // 60,
        "temperature": 0.7,
        "model": "enhanced",
        "language": "ENG",
        "voicemail_message": (
            f"Hey {first_name}, this is Ashley from OneVision Marketing. "
            f"Missed you — I'll shoot you a quick text and try you again soon. "
            f"Thanks!"
        ),
        "metadata": {
            "prompt_key": prompt_key,
            "triggered_at": datetime.utcnow().isoformat(),
            "lead_name": first_name,
        },
    }

    if prompt.get("booking_calendar_url"):
        payload["metadata"]["calendar_url"] = prompt["booking_calendar_url"]

    headers = {
        "Authorization": BLAND_API_KEY,
        "Content-Type": "application/json",
    }

    response = requests.post(BLAND_API_URL, json=payload, headers=headers, timeout=15)

    if response.status_code >= 400:
        return {
            "ok": False,
            "error": f"Bland API returned {response.status_code}: {response.text[:300]}",
        }

    result = response.json()
    log_callback(phone, first_name, prompt_key, result)

    return {
        "ok": True,
        "call_id": result.get("call_id"),
        "status": result.get("status"),
        "batch_id": result.get("batch_id"),
        "message": f"Callback initiated to {phone} in ~15 seconds",
    }


def normalize_phone(phone):
    """Ensure phone number is in E.164 format (+1XXXXXXXXXX for US)."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    if phone.startswith("+"):
        return phone
    raise ValueError(f"Invalid phone number: {phone}")


def log_callback(phone, name, prompt_key, result):
    """Log every callback attempt for audit and analytics."""
    os.makedirs(os.path.dirname(CALLBACK_LOG), exist_ok=True)
    log = []
    if os.path.exists(CALLBACK_LOG):
        try:
            with open(CALLBACK_LOG) as f:
                log = json.load(f)
        except json.JSONDecodeError:
            log = []
    log.append({
        "timestamp": datetime.utcnow().isoformat(),
        "phone": phone,
        "name": name,
        "prompt": prompt_key,
        "call_id": result.get("call_id"),
        "status": result.get("status"),
    })
    with open(CALLBACK_LOG, "w") as f:
        json.dump(log[-1000:], f, indent=2)


def get_call_status(call_id):
    """Fetch call transcript and outcome after the call completes."""
    if not BLAND_API_KEY:
        raise RuntimeError("BLAND_API_KEY not set")

    headers = {"Authorization": BLAND_API_KEY}
    resp = requests.get(f"{BLAND_API_URL}/{call_id}", headers=headers, timeout=15)
    if resp.status_code >= 400:
        return {"ok": False, "error": resp.text[:200]}
    return {"ok": True, "call": resp.json()}


# ---------------------------------------------------------------------------
# Webhook Server (Flask)
# ---------------------------------------------------------------------------

def create_app():
    """Flask app that receives lead form submissions and triggers callbacks."""
    if not HAS_FLASK:
        raise RuntimeError("Flask not installed. Run: pip install flask")

    app = Flask(__name__)

    @app.route("/webhook/lead", methods=["POST"])
    def lead_webhook():
        """Universal lead intake webhook. Accepts JSON from:
        - Website forms
        - Facebook Lead Ads (via Zapier/Make)
        - GoHighLevel form submissions
        - Manual API calls

        Expected payload:
        {
          "name": "John Smith",
          "phone": "+15551234567",
          "email": "john@example.com",
          "prompt": "onevision_marketing" (optional, defaults to onevision),
          "message": "..." (optional context)
        }
        """
        try:
            data = request.get_json(force=True) or {}
        except Exception:
            data = dict(request.form)

        name = data.get("name") or data.get("first_name") or data.get("full_name") or ""
        first_name = name.split()[0] if name else ""
        phone = data.get("phone") or data.get("phone_number") or data.get("mobile") or ""
        prompt_key = data.get("prompt") or data.get("callback_type") or "onevision_marketing"

        if not phone:
            return jsonify({"ok": False, "error": "phone number required"}), 400
        if prompt_key not in PROMPT_LIBRARY:
            return jsonify({
                "ok": False,
                "error": f"unknown prompt: {prompt_key}. Available: {list(PROMPT_LIBRARY.keys())}"
            }), 400

        extra_vars = {}
        for key in ("business_name", "cuisine_type", "city", "state",
                    "inquiry_type", "service_type"):
            if key in data:
                extra_vars[key] = data[key]

        try:
            result = make_callback(phone, first_name, prompt_key, extra_vars)
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

        return jsonify(result), (200 if result.get("ok") else 500)

    @app.route("/webhook/lead-result", methods=["POST"])
    def call_result_webhook():
        """Bland.ai will POST call results here after the call ends.
        Configure this URL in your Bland dashboard under Webhooks."""
        data = request.get_json(force=True) or {}
        call_id = data.get("call_id")
        status = data.get("status")
        transcript = data.get("concatenated_transcript", "")

        print(f"\n[CALLBACK RESULT] Call {call_id} — {status}")
        if transcript:
            print(f"Transcript preview: {transcript[:200]}...")

        results_log = os.path.join(BASE_DIR, "clients", "aventisai",
                                    "callback_results.json")
        os.makedirs(os.path.dirname(results_log), exist_ok=True)
        results = []
        if os.path.exists(results_log):
            try:
                with open(results_log) as f:
                    results = json.load(f)
            except json.JSONDecodeError:
                results = []
        results.append({
            "call_id": call_id,
            "status": status,
            "duration": data.get("call_length"),
            "transcript": transcript,
            "completed_at": datetime.utcnow().isoformat(),
            "summary": data.get("summary", ""),
        })
        with open(results_log, "w") as f:
            json.dump(results[-500:], f, indent=2)

        return jsonify({"ok": True})

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({
            "ok": True,
            "bland_configured": bool(BLAND_API_KEY),
            "prompts_available": list(PROMPT_LIBRARY.keys()),
        })

    @app.route("/test", methods=["GET"])
    def test_page():
        return """
<!DOCTYPE html>
<html><head><title>AI Callback Bot — Test</title>
<style>body{font-family:sans-serif;max-width:500px;margin:40px auto;padding:20px}
input,select,button{width:100%;padding:10px;margin:6px 0;font-size:14px;box-sizing:border-box}
button{background:#2563eb;color:white;border:none;border-radius:6px;font-weight:600;cursor:pointer}
</style></head><body>
<h2>AI Callback Bot — Test</h2>
<p>Fill in your info to receive a test callback.</p>
<form onsubmit="test(event)">
<input name="name" placeholder="Your name" required>
<input name="phone" placeholder="+1XXXXXXXXXX" required>
<select name="prompt">
  <option value="onevision_marketing">OneVision Marketing</option>
  <option value="akira_buyer">Akira Real Estate — Buyer</option>
  <option value="akira_seller">Akira Real Estate — Seller</option>
</select>
<button>Trigger Callback</button>
</form>
<pre id="out"></pre>
<script>
async function test(e){e.preventDefault();
const fd=new FormData(e.target);
const body={};fd.forEach((v,k)=>body[k]=v);
const r=await fetch('/webhook/lead',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
document.getElementById('out').textContent=await r.text();
}
</script></body></html>
"""

    return app


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="AI Callback Bot for lead conversion")
    parser.add_argument("--phone", help="Phone number to call (E.164 or US 10-digit)")
    parser.add_argument("--name", help="Lead's first name", default="there")
    parser.add_argument("--prompt", default="onevision_marketing",
                        help=f"Prompt to use. Options: {list(PROMPT_LIBRARY.keys())}")
    parser.add_argument("--serve", action="store_true",
                        help="Run as webhook server instead of one-off call")
    parser.add_argument("--port", type=int, default=5000, help="Port for webhook server")
    parser.add_argument("--status", help="Check status of a call by call_id")
    parser.add_argument("--list-prompts", action="store_true",
                        help="List available prompt templates")
    args = parser.parse_args()

    if args.list_prompts:
        print("\nAvailable callback prompts:\n")
        for key, val in PROMPT_LIBRARY.items():
            print(f"  {key}")
            print(f"    → {val['name']}")
            print()
        return

    if args.status:
        result = get_call_status(args.status)
        print(json.dumps(result, indent=2))
        return

    if args.serve:
        app = create_app()
        print(f"\n[SERVER] AI Callback Bot listening on http://0.0.0.0:{args.port}")
        print(f"[SERVER] Bland.ai configured: {bool(BLAND_API_KEY)}")
        print(f"[SERVER] Webhook: POST http://your-domain.com/webhook/lead")
        print(f"[SERVER] Test page: http://localhost:{args.port}/test")
        print(f"[SERVER] Health: http://localhost:{args.port}/health\n")
        app.run(host="0.0.0.0", port=args.port, debug=False)
        return

    if not args.phone:
        parser.error("--phone required (or use --serve for webhook mode)")

    print(f"\nTriggering callback to {args.name} at {args.phone}...")
    print(f"Using prompt: {args.prompt}\n")
    result = make_callback(args.phone, args.name, args.prompt)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
