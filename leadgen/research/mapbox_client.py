"""Mapbox Geocoding v6 — turn addresses into coordinates for the map view.

IMPORTANT — permanent storage
-----------------------------
Mapbox's terms distinguish temporary geocoding (display only, must not be
stored) from permanent geocoding (`permanent=true`), which is what you need when
results are written to a database. This CRM stores latitude and longitude on the
lead row, so every request here sets `permanent=true`.

Permanent geocoding is a **paid** feature on most Mapbox plans. If you are on a
free tier the API returns 403 and this module reports that plainly rather than
silently downgrading to temporary geocoding, which would put you offside of the
terms while looking like it worked.

Set MAPBOX_ALLOW_TEMPORARY=1 only if you understand you must not persist the
result. The module honours it, but flags every response it produces.

Docs: https://docs.mapbox.com/api/search/geocoding/
"""

import os
import requests

FORWARD = "https://api.mapbox.com/search/geocode/v6/forward"
DEFAULT_TIMEOUT = 15


def access_token():
    return os.getenv("MAPBOX_ACCESS_TOKEN", "").strip()


def is_configured():
    return bool(access_token())


def _permanent():
    return not os.getenv("MAPBOX_ALLOW_TEMPORARY")


def geocode(address=None, city=None, state=None, postcode=None,
            country="us", timeout=DEFAULT_TIMEOUT):
    """Forward-geocode an address to {lat, lng}.

    Returns {ok, lat, lng, matched, permanent, error}. Never raises.
    """
    token = access_token()
    if not token:
        return {"ok": False, "error": "MAPBOX_ACCESS_TOKEN not set",
                "lat": None, "lng": None}

    q = ", ".join(str(p).strip() for p in (address, city, state, postcode)
                  if p and str(p).strip())
    if not q:
        return {"ok": False, "error": "nothing to geocode",
                "lat": None, "lng": None}

    params = {
        "q": q,
        "access_token": token,
        "limit": 1,
        "country": country,
        "types": "address,street,place,postcode",
    }
    if _permanent():
        params["permanent"] = "true"

    try:
        r = requests.get(FORWARD, params=params, timeout=timeout)
    except requests.RequestException as e:
        return {"ok": False, "error": f"network: {str(e)[:120]}",
                "lat": None, "lng": None}

    if r.status_code == 401:
        return {"ok": False, "error": "Mapbox rejected the token (401)",
                "lat": None, "lng": None}
    if r.status_code == 403:
        return {
            "ok": False,
            "lat": None, "lng": None,
            "error": ("Mapbox returned 403. Permanent geocoding is required to "
                      "store coordinates and is a paid feature — enable it on "
                      "your Mapbox plan, or set MAPBOX_ALLOW_TEMPORARY=1 and do "
                      "not persist the results."),
        }
    if r.status_code == 429:
        return {"ok": False, "error": "Mapbox rate limit (429)",
                "lat": None, "lng": None}
    if r.status_code >= 400:
        return {"ok": False, "error": f"Mapbox HTTP {r.status_code}",
                "lat": None, "lng": None}

    feats = (r.json() or {}).get("features") or []
    if not feats:
        return {"ok": False, "error": "no match", "lat": None, "lng": None}

    f = feats[0]
    coords = (f.get("geometry") or {}).get("coordinates") or []
    if len(coords) < 2:
        return {"ok": False, "error": "no coordinates", "lat": None, "lng": None}

    props = f.get("properties") or {}
    return {
        "ok": True,
        "error": "",
        "lng": coords[0],
        "lat": coords[1],
        "matched": props.get("full_address") or props.get("name") or q,
        "accuracy": (props.get("coordinates") or {}).get("accuracy"),
        "permanent": _permanent(),
    }


def geocode_lead(lead):
    return geocode(
        address=lead.get("address"),
        city=lead.get("city"),
        state=lead.get("state"),
        postcode=lead.get("zip_code"),
    )


def is_public_token(token=None):
    """True only for a `pk.` token.

    Mapbox issues two kinds. `pk.` is public, designed to sit in a web page and
    restricted by URL. `sk.` is secret and carries full account access --
    putting one in client-side HTML hands over the account. This distinction
    decides whether the token may be sent to the browser at all.
    """
    t = token if token is not None else access_token()
    return bool(t) and t.startswith("pk.")


def style_config(for_browser=False):
    """Config for the map view.

    With `for_browser=True` the token is included ONLY if it is public. A secret
    token still works for server-side geocoding, but the map falls back to
    OpenStreetMap tiles rather than leaking it.
    """
    token = access_token()
    cfg = {
        "enabled": bool(token),
        "style": os.getenv("MAPBOX_STYLE", "mapbox/streets-v12"),
        "has_token": bool(token),
        "token_is_public": is_public_token(token),
    }
    if for_browser:
        if is_public_token(token):
            cfg["token"] = token
            cfg["tiles"] = True
        else:
            cfg["token"] = ""
            cfg["tiles"] = False
            cfg["note"] = (
                "A secret (sk.) token cannot be used in the browser. Geocoding "
                "still works server-side; for Mapbox map tiles add a public "
                "(pk.) token instead." if token else
                "No MAPBOX_ACCESS_TOKEN set — using OpenStreetMap tiles.")
    else:
        cfg["token"] = token
    return cfg
