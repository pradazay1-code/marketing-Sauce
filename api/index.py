"""Vercel serverless entrypoint for the AventisAI CRM.

Vercel's Python runtime looks for a WSGI/ASGI callable named `app` in each file
under api/. Everything is routed here by vercel.json, so this one function
serves the whole Flask app.

Local development is unchanged -- run `python wsgi.py` as before.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# leadgen/ modules import each other by bare name ("from database import ...")
# rather than as a package, so the directory itself has to be importable.
sys.path.insert(0, os.path.join(ROOT, "leadgen"))
sys.path.insert(0, ROOT)

from app import app  # noqa: E402

# Vercel discovers this symbol.
application = app
