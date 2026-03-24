#!/usr/bin/env python3
"""Flask web UI for GNS3 topology monitoring (read-only, port 5050)."""

import json
import logging
import os
import re
import secrets
import time
from collections import defaultdict
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    abort,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))

# HTTPS-ready: honour X-Forwarded-Proto when behind a reverse proxy
app.config["PREFERRED_URL_SCHEME"] = os.environ.get("URL_SCHEME", "http")

GNS3_PROJECT_FILE = os.environ.get(
    "GNS3_PROJECT_FILE",
    "/tmp/gns3_project/Network_Topology.gns3",
)
GNS3_SECURITY_FILE = os.environ.get(
    "GNS3_SECURITY_FILE",
    "/tmp/gns3_project/security_config.json",
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/tmp/gns3_web.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


@app.after_request
def _log_request(response):
    logger.info(
        "%s %s %s — %s",
        request.remote_addr,
        request.method,
        request.path,
        response.status_code,
    )
    return response


# ---------------------------------------------------------------------------
# Rate limiting (in-memory, no extra dependencies)
# ---------------------------------------------------------------------------

_rate_store: dict = defaultdict(list)
RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "60"))   # requests
RATE_WINDOW = int(os.environ.get("RATE_WINDOW", "60"))  # seconds


def _rate_limit(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        ip = request.remote_addr or "unknown"
        now = time.time()
        window_start = now - RATE_WINDOW
        _rate_store[ip] = [t for t in _rate_store[ip] if t > window_start]
        if len(_rate_store[ip]) >= RATE_LIMIT:
            logger.warning("Rate limit exceeded for %s", ip)
            abort(429)
        _rate_store[ip].append(now)
        return func(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# CSRF helpers
# ---------------------------------------------------------------------------

def _csrf_token() -> str:
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


def _validate_csrf():
    token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    if not token or token != session.get("csrf_token"):
        logger.warning("CSRF validation failed from %s", request.remote_addr)
        abort(403)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_\-\.]{1,64}$")


def _sanitize_name(value: str) -> str:
    """Return *value* if it matches the safe-name pattern, else raise 400."""
    if not _SAFE_NAME_RE.match(value):
        abort(400)
    return value


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _load_project():
    """Load and parse the GNS3 project JSON file."""
    if not os.path.exists(GNS3_PROJECT_FILE):
        return None
    try:
        with open(GNS3_PROJECT_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Failed to load project file: %s", exc)
        return None


def _load_security():
    """Load the security config JSON if it exists."""
    if not os.path.exists(GNS3_SECURITY_FILE):
        return None
    try:
        with open(GNS3_SECURITY_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Failed to load security file: %s", exc)
        return None


def _node_id_to_name(project: dict) -> dict:
    return {
        n["node_id"]: n["name"]
        for n in project.get("topology", {}).get("nodes", [])
    }


def _build_topology(project: dict) -> tuple[list, list]:
    """Return (nodes, links) parsed from the project dict."""
    nodes = project.get("topology", {}).get("nodes", [])
    id_map = _node_id_to_name(project)
    links = []
    for lnk in project.get("topology", {}).get("links", []):
        endpoints = lnk.get("nodes", [])
        if len(endpoints) >= 2:
            links.append(
                {
                    "node_a": id_map.get(endpoints[0].get("node_id"), "?"),
                    "iface_a": f"e{endpoints[0].get('adapter_number', 0)}/{endpoints[0].get('port_number', 0)}",
                    "node_b": id_map.get(endpoints[1].get("node_id"), "?"),
                    "iface_b": f"e{endpoints[1].get('adapter_number', 0)}/{endpoints[1].get('port_number', 0)}",
                }
            )
    return nodes, links


# Security zones metadata (static reference — matches Ansible vars)
_ZONES = {
    "ospf_area0":     {"label": "OSPF Area 0",     "nodes": {"R1", "R2", "R3", "R4"}, "color": "#3465a4"},
    "access_zone":    {"label": "Access Zone",      "nodes": {"R2", "PC1", "PC2"},     "color": "#4e9a06"},
    "restricted_zone":{"label": "Restricted Zone",  "nodes": {"R3", "PC3"},            "color": "#c4a000"},
    "dmz":            {"label": "DMZ",              "nodes": {"R4", "SRV-WEB", "SRV-REDIS", "SRV-DB"}, "color": "#cc0000"},
}


def _zone_for(node_name: str) -> str:
    for zone_key, zone in _ZONES.items():
        if node_name in zone["nodes"]:
            return zone["label"]
    return "—"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
@_rate_limit
def index():
    project = _load_project()
    security = _load_security()
    file_ok = project is not None

    if project:
        nodes, links = _build_topology(project)
        version = project.get("version", "?")
        project_name = project.get("name", "?")
    else:
        nodes, links = [], []
        version = "—"
        project_name = "—"

    # Annotate each node with its security zone
    annotated_nodes = [
        {**n, "zone": _zone_for(n.get("name", ""))}
        for n in nodes
    ]

    return render_template(
        "topology.html",
        project_name=project_name,
        project_file=GNS3_PROJECT_FILE,
        file_ok=file_ok,
        version=version,
        nodes=annotated_nodes,
        links=links,
        zones=_ZONES,
        security=security,
        ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        csrf_token=_csrf_token(),
    )


@app.errorhandler(403)
def _err_403(e):
    return render_template("topology.html", error="403 Forbidden", **_empty_ctx()), 403


@app.errorhandler(404)
def _err_404(e):
    return render_template("topology.html", error="404 Not Found", **_empty_ctx()), 404


@app.errorhandler(429)
def _err_429(e):
    return render_template("topology.html", error="429 Too Many Requests", **_empty_ctx()), 429


def _empty_ctx():
    return dict(
        project_name="—", project_file=GNS3_PROJECT_FILE, file_ok=False,
        version="—", nodes=[], links=[], zones=_ZONES, security=None,
        ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        csrf_token=_csrf_token(),
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    use_https = os.environ.get("HTTPS", "").lower() in ("1", "true", "yes")
    ssl_ctx = None
    if use_https:
        cert = os.environ.get("SSL_CERT", "cert.pem")
        key = os.environ.get("SSL_KEY", "key.pem")
        ssl_ctx = (cert, key)
        logger.info("Starting with HTTPS (cert=%s, key=%s)", cert, key)

    app.run(host="0.0.0.0", port=5050, debug=False, ssl_context=ssl_ctx)

