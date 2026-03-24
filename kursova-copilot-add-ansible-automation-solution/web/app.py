#!/usr/bin/env python3
"""GNS3 Security Dashboard – main Flask application (port 5050)."""

import json
import os
import shlex
import subprocess
import threading
import time
import uuid
from datetime import datetime

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect, generate_csrf
from markupsafe import escape

from security.port_scan import PortScanner
from security.cis_benchmark import CISBenchmark
from security.vulnerability_check import VulnerabilityChecker
from security.ping_check import PingChecker
from security.acl_validator import ACLValidator
from validators.input_validator import InputValidator

# ---------------------------------------------------------------------------
# App configuration
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", os.urandom(32).hex())
app.config["WTF_CSRF_TIME_LIMIT"] = None

CORS(app)
csrf = CSRFProtect(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# ---------------------------------------------------------------------------
# Project file locations
# ---------------------------------------------------------------------------

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GNS3_PROJECT_FILE = os.environ.get(
    "GNS3_PROJECT_FILE",
    "/tmp/gns3_project/Network_Topology.gns3",
)
GNS3_PROJECT_FALLBACK = os.path.join(_PROJECT_DIR, "ansible", "Network_Topology.gns3")

# ---------------------------------------------------------------------------
# In-memory results store (thread-safe)
# ---------------------------------------------------------------------------

_results_lock = threading.Lock()
_results = []  # list[dict]

# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------

@app.after_request
def add_security_headers(response):
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com 'unsafe-inline'; "
        "style-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com 'unsafe-inline'; "
        "font-src 'self' https://cdnjs.cloudflare.com; "
        "connect-src 'self' ws: wss:; "
        "img-src 'self' data:;"
    )
    return response


@app.context_processor
def inject_csrf():
    return {"csrf_token": generate_csrf}

# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/topology")
def topology():
    return render_template("topology.html")


@app.route("/results")
def results_page():
    return render_template("results.html")


@app.route("/settings")
def settings():
    return render_template("settings.html")

# ---------------------------------------------------------------------------
# API – topology
# ---------------------------------------------------------------------------

@app.route("/api/security/topology")
def api_topology():
    project = _load_gns3_project()
    if project is None:
        return jsonify({"error": "GNS3 project file not found", "nodes": [], "links": []}), 404

    topology = project.get("topology", {})
    raw_nodes = topology.get("nodes", [])
    raw_links = topology.get("links", [])

    id_map = {n["node_id"]: n["name"] for n in raw_nodes}

    nodes_out = []
    for n in raw_nodes:
        nodes_out.append({
            "id": n.get("node_id"),
            "name": n.get("name"),
            "node_type": n.get("node_type", "unknown"),
            "x": n.get("x", 0),
            "y": n.get("y", 0),
            "console": n.get("console"),
            "status": n.get("status", "stopped"),
        })

    links_out = []
    for lnk in raw_links:
        endpoints = lnk.get("nodes", [])
        if len(endpoints) >= 2:
            links_out.append({
                "id": lnk.get("link_id"),
                "source": endpoints[0].get("node_id"),
                "target": endpoints[1].get("node_id"),
                "source_name": id_map.get(endpoints[0].get("node_id"), "?"),
                "target_name": id_map.get(endpoints[1].get("node_id"), "?"),
            })

    return jsonify({
        "project_name": project.get("name"),
        "version": project.get("version"),
        "nodes": nodes_out,
        "links": links_out,
        "node_count": len(nodes_out),
        "link_count": len(links_out),
        "scanned_at": datetime.now().isoformat(),
    })

# ---------------------------------------------------------------------------
# API – security tests
# ---------------------------------------------------------------------------

@app.route("/api/security/test/<test_name>", methods=["POST"])
def run_security_test(test_name):
    validator = InputValidator()
    try:
        validator.validate_test_name(test_name)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    start = time.monotonic()
    try:
        result_data = _dispatch_test(test_name)
    except Exception as exc:  # pylint: disable=broad-except
        result_data = {
            "status": "error",
            "severity": "high",
            "message": "Test execution error: {}".format(str(escape(str(exc)))),
        }

    duration_ms = int((time.monotonic() - start) * 1000)

    record = {
        "id": str(uuid.uuid4()),
        "test_name": test_name,
        "status": result_data.get("status", "error"),
        "severity": result_data.get("severity", "unknown"),
        "duration": duration_ms,
        "timestamp": datetime.now().isoformat(),
        "details": result_data,
    }

    with _results_lock:
        _results.append(record)

    socketio.emit("test_update", record)

    return jsonify(record), 200


def _dispatch_test(test_name):
    runners = {
        "port_scan": PortScanner,
        "cis_benchmark": CISBenchmark,
        "vulnerability_check": VulnerabilityChecker,
        "ping_check": PingChecker,
        "acl_validation": ACLValidator,
    }
    cls = runners[test_name]
    return cls().run()

# ---------------------------------------------------------------------------
# API – auto-fix
# ---------------------------------------------------------------------------

@app.route("/api/security/fix/<fix_name>", methods=["POST"])
def apply_fix(fix_name):
    validator = InputValidator()
    try:
        validator.validate_fix_name(fix_name)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    fix_functions = {
        "close_ports": _fix_close_ports,
        "enable_firewall": _fix_enable_firewall,
        "update_system": _fix_update_system,
        "reset_acl": _fix_reset_acl,
    }

    result = fix_functions[fix_name]()
    return jsonify(result), 200


def _fix_close_ports():
    dangerous_ports = [21, 23, 445, 6379]
    applied = []
    errors = []

    for port in dangerous_ports:
        cmd = ["iptables", "-A", "INPUT", "-p", "tcp", "--dport", str(port), "-j", "DROP"]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=10, check=False,
            )
            if result.returncode == 0:
                applied.append("Blocked port {}".format(port))
            else:
                errors.append("Port {}: {}".format(port, result.stderr.strip()[:80]))
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            errors.append("Port {}: {}".format(port, str(exc)[:80]))

    status = "success" if applied else "warning"
    return {
        "status": status,
        "message": "Close ports: {} rules applied, {} errors".format(len(applied), len(errors)),
        "details": {"applied": applied, "errors": errors},
        "fix_name": "close_ports",
    }


def _fix_enable_firewall():
    details = []
    status = "warning"

    try:
        result = subprocess.run(
            ["ufw", "enable"],
            capture_output=True, text=True, timeout=15, check=False,
            input="y\n",
        )
        if result.returncode == 0:
            details.append("ufw enabled successfully")
            status = "success"
        else:
            out = (result.stderr.strip() or result.stdout.strip())[:80]
            details.append("ufw: {}".format(out))
    except FileNotFoundError:
        details.append("ufw not found")
    except subprocess.TimeoutExpired:
        details.append("ufw timed out")

    try:
        result = subprocess.run(
            ["iptables", "-L", "-n"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if result.returncode == 0:
            details.append("iptables is available and running")
            status = "success"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        details.append("iptables not accessible")

    return {
        "status": status,
        "message": "Firewall configuration attempted",
        "details": {"steps": details},
        "fix_name": "enable_firewall",
    }


def _fix_update_system():
    details = []

    try:
        result = subprocess.run(
            ["apt-get", "-s", "upgrade"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        upgradable = [
            line.split()[1]
            for line in result.stdout.splitlines()
            if line.startswith("Inst ")
        ]
        details.append("{} packages can be upgraded".format(len(upgradable)))
        details.extend(upgradable[:10])
        if len(upgradable) > 10:
            details.append("... and {} more".format(len(upgradable) - 10))
    except FileNotFoundError:
        details.append("apt-get not found (non-Debian system)")
    except subprocess.TimeoutExpired:
        details.append("apt-get check timed out")

    return {
        "status": "success",
        "message": "System update check completed (simulation)",
        "details": {"steps": details},
        "fix_name": "update_system",
    }


def _fix_reset_acl():
    details = []
    errors = []

    for cmd in (["iptables", "-F"], ["iptables", "-P", "INPUT", "ACCEPT"]):
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=10, check=False,
            )
            if result.returncode == 0:
                details.append("Executed: {}".format(" ".join(cmd)))
            else:
                errors.append("{}: {}".format(" ".join(cmd), result.stderr.strip()[:80]))
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            errors.append(str(exc)[:80])

    status = "success" if details else "warning"
    return {
        "status": status,
        "message": "ACL reset attempted",
        "details": {"applied": details, "errors": errors},
        "fix_name": "reset_acl",
    }

# ---------------------------------------------------------------------------
# API – results CRUD
# ---------------------------------------------------------------------------

@app.route("/api/security/results")
def get_results():
    with _results_lock:
        return jsonify(list(_results))


@app.route("/api/security/results/<test_id>")
def get_result(test_id):
    with _results_lock:
        for r in _results:
            if r["id"] == test_id:
                return jsonify(r)
    return jsonify({"error": "Result not found"}), 404


@app.route("/api/security/results/<test_id>", methods=["DELETE"])
def delete_result(test_id):
    with _results_lock:
        original = len(_results)
        _results[:] = [r for r in _results if r["id"] != test_id]
        removed = original - len(_results)
    if removed:
        return jsonify({"status": "deleted", "id": test_id})
    return jsonify({"error": "Result not found"}), 404

# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@socketio.on("connect")
def handle_connect():
    socketio.emit("connection_status", {"status": "connected"})

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_gns3_project():
    for path in (GNS3_PROJECT_FILE, GNS3_PROJECT_FALLBACK):
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    return json.load(fh)
            except (OSError, json.JSONDecodeError):
                continue
    return None

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5050, debug=False)
