#!/usr/bin/env python3
"""
Flask web UI for GNS3 network topology monitoring.

Features:
  - Dark-theme tabbed dashboard (Dashboard / Topology / Security)
  - Real-time host status (UP/DOWN) via SocketIO or 30-s polling fallback
  - Security-test endpoints (nmap, ping, ACL check, vuln scan)
  - Auto-fix endpoints  (close ports, enable firewall, apt update, reset ACL)
  - Read-only JSON API  (/api/topology, /api/hosts)
  - Operation log       (/api/logs)

Port: 5050  |  GNS3 API: http://localhost:3080
"""

import json
import os
import subprocess
import threading
import time
from datetime import datetime

from flask import Flask, jsonify, render_template, request

try:
    from flask_socketio import SocketIO, emit as sio_emit
    _SOCKETIO = True
except ImportError:
    _SOCKETIO = False

# ── Configuration ────────────────────────────────────────────────────────────
GNS3_PROJECT_FILE = os.environ.get(
    "GNS3_PROJECT_FILE",
    "/tmp/gns3_project/Network_Topology.gns3",
)
GNS3_API_URL = os.environ.get("GNS3_API_URL", "http://localhost:3080/v3")

# ── Static topology definition ───────────────────────────────────────────────
TOPOLOGY_NODES = [
    # Routers
    {"id": "r1", "name": "R1",           "label": "Core (OSPF Area 0)",  "zone": "core",      "ip": "10.0.0.1",     "console": 5001, "type": "router"},
    {"id": "r2", "name": "R2",           "label": "Access",               "zone": "access",    "ip": "10.1.0.2",     "console": 5002, "type": "router"},
    {"id": "r3", "name": "R3",           "label": "Perimeter (WAF/IDS)",  "zone": "perimeter", "ip": "10.2.0.3",     "console": 5003, "type": "router"},
    {"id": "r4", "name": "R4",           "label": "DMZ",                  "zone": "dmz",       "ip": "10.3.0.4",     "console": 5004, "type": "router"},
    # User PCs (Access zone, R2)
    {"id": "pc1",          "name": "PC1",          "label": "User 1",     "zone": "access",    "ip": "192.168.1.10", "console": 5010, "type": "pc"},
    {"id": "pc2",          "name": "PC2",          "label": "User 2",     "zone": "access",    "ip": "192.168.1.20", "console": 5011, "type": "pc"},
    # Perimeter PC (R3)
    {"id": "pc_perimeter", "name": "PC-PERIMETER", "label": "WAF/IDS",   "zone": "perimeter", "ip": "172.16.0.10",  "console": 5012, "type": "pc"},
    # DMZ servers (R4)
    {"id": "srv_web",   "name": "SRV-WEB",   "label": "Apache",      "zone": "dmz", "ip": "10.10.10.10", "console": 5020, "type": "server"},
    {"id": "srv_redis", "name": "SRV-REDIS", "label": "Redis",        "zone": "dmz", "ip": "10.10.10.20", "console": 5021, "type": "server"},
    {"id": "srv_db",    "name": "SRV-DB",    "label": "PostgreSQL",   "zone": "dmz", "ip": "10.10.10.30", "console": 5022, "type": "server"},
]

TOPOLOGY_LINKS = [
    {"source": "r1", "target": "r2",          "label": "10.1.0.0/30"},
    {"source": "r1", "target": "r3",          "label": "10.2.0.0/30"},
    {"source": "r1", "target": "r4",          "label": "10.3.0.0/30"},
    {"source": "r2", "target": "pc1",         "label": "192.168.1.0/24"},
    {"source": "r2", "target": "pc2",         "label": "192.168.1.0/24"},
    {"source": "r3", "target": "pc_perimeter","label": "172.16.0.0/24"},
    {"source": "r4", "target": "srv_web",     "label": "10.10.10.0/24"},
    {"source": "r4", "target": "srv_redis",   "label": "10.10.10.0/24"},
    {"source": "r4", "target": "srv_db",      "label": "10.10.10.0/24"},
]

# ── Flask app ────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config["SECRET_KEY"] = "gns3-network-monitor"

if _SOCKETIO:
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ── Shared state ─────────────────────────────────────────────────────────────
_state_lock = threading.Lock()
_state = {
    "hosts":       {n["id"]: {"status": "UNKNOWN", "last_check": "—"} for n in TOPOLOGY_NODES},
    "logs":        [],
    "last_update": "—",
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _log(message, level="INFO"):
    """Prepend a log entry (max 100 kept)."""
    entry = {
        "ts":      datetime.now().strftime("%H:%M:%S"),
        "level":   level,
        "message": message,
    }
    with _state_lock:
        _state["logs"].insert(0, entry)
        if len(_state["logs"]) > 100:
            _state["logs"] = _state["logs"][:100]


def _ping(ip):
    """Return True if *ip* responds to a single ICMP ping within 1 s."""
    try:
        r = subprocess.run(
            ["ping", "-c", "1", "-W", "1", ip],
            capture_output=True,
            timeout=3,
        )
        return r.returncode == 0
    except Exception:
        return False


def _load_project():
    """Load the GNS3 project JSON file, or None if not found."""
    if not os.path.exists(GNS3_PROJECT_FILE):
        return None
    with open(GNS3_PROJECT_FILE, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _gns3_node_statuses():
    """
    Query GNS3 REST API for node statuses.
    Returns {name: status_str} or {} on any error.
    """
    try:
        import urllib.request
        with urllib.request.urlopen(f"{GNS3_API_URL}/projects", timeout=2) as resp:
            projects = json.loads(resp.read())
        if not projects:
            return {}
        pid = projects[0]["project_id"]
        with urllib.request.urlopen(f"{GNS3_API_URL}/projects/{pid}/nodes", timeout=2) as resp:
            nodes = json.loads(resp.read())
        return {n["name"]: n.get("status", "unknown") for n in nodes}
    except Exception:
        return {}


def _host_list_with_status():
    """Return TOPOLOGY_NODES enriched with live status."""
    gns3 = _gns3_node_statuses()
    result = []
    for node in TOPOLOGY_NODES:
        with _state_lock:
            hs = dict(_state["hosts"].get(node["id"], {}))
        # GNS3 API takes priority
        g = gns3.get(node["name"])
        if g == "started":
            status = "UP"
        elif g == "stopped":
            status = "DOWN"
        else:
            status = hs.get("status", "UNKNOWN")
        result.append({**node, "status": status, "last_check": hs.get("last_check", "—")})
    return result


# ── Background ping thread ───────────────────────────────────────────────────

def _background_status_check():
    while True:
        try:
            for node in TOPOLOGY_NODES:
                status = "UP" if _ping(node["ip"]) else "DOWN"
                with _state_lock:
                    _state["hosts"][node["id"]] = {
                        "status":     status,
                        "last_check": datetime.now().strftime("%H:%M:%S"),
                    }
            with _state_lock:
                _state["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                hosts_snapshot = dict(_state["hosts"])

            if _SOCKETIO:
                socketio.emit("status_update", {"hosts": hosts_snapshot})
        except Exception as exc:
            _log(f"Background check error: {exc}", "ERROR")
        time.sleep(30)


# ── Template context processor ───────────────────────────────────────────────

@app.context_processor
def _inject_globals():
    return {"socketio_available": _SOCKETIO}


# ── Page routes ──────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    hosts = _host_list_with_status()
    with _state_lock:
        logs        = _state["logs"][:20]
        last_update = _state["last_update"]
    project = _load_project()
    return render_template(
        "dashboard.html",
        active_tab   = "dashboard",
        hosts        = hosts,
        logs         = logs,
        last_update  = last_update,
        project_file = GNS3_PROJECT_FILE,
        file_ok      = project is not None,
    )


@app.route("/topology")
def topology():
    return render_template(
        "topology.html",
        active_tab = "topology",
        nodes_list = TOPOLOGY_NODES,
        nodes_json = json.dumps(TOPOLOGY_NODES),
        links_json = json.dumps(TOPOLOGY_LINKS),
    )


@app.route("/security")
def security():
    with _state_lock:
        logs = _state["logs"][:20]
    return render_template("security.html", active_tab="security", logs=logs)


# ── Read-only JSON API ───────────────────────────────────────────────────────

@app.route("/api/topology")
def api_topology():
    project = _load_project()
    return jsonify({
        "nodes":          TOPOLOGY_NODES,
        "links":          TOPOLOGY_LINKS,
        "project_file":   GNS3_PROJECT_FILE,
        "project_loaded": project is not None,
        "scanned_at":     datetime.now().isoformat(),
    })


@app.route("/api/hosts")
def api_hosts():
    return jsonify(_host_list_with_status())


@app.route("/api/logs")
def api_logs():
    with _state_lock:
        return jsonify(list(_state["logs"]))


# ── Security test endpoints ──────────────────────────────────────────────────

@app.route("/api/security/scan_ports", methods=["POST"])
def sec_scan_ports():
    data   = request.get_json(silent=True) or {}
    target = data.get("target", "192.168.1.0/24")
    _log(f"Port scan: {target}")
    try:
        r = subprocess.run(
            ["nmap", "-sV", "--open", target],
            capture_output=True, text=True, timeout=60,
        )
        output = r.stdout or r.stderr
        _log(f"Port scan done: {target}")
        return jsonify({"status": "ok", "output": output})
    except FileNotFoundError:
        msg = "nmap not installed (apt install nmap)"
        _log(msg, "WARN")
        return jsonify({"status": "error", "output": msg})
    except subprocess.TimeoutExpired:
        return jsonify({"status": "error", "output": "Scan timed out after 60 s"})
    except Exception as exc:
        return jsonify({"status": "error", "output": str(exc)})


@app.route("/api/security/check_vulns", methods=["POST"])
def sec_check_vulns():
    data   = request.get_json(silent=True) or {}
    target = data.get("target", "localhost")
    _log(f"Vuln check: {target}")
    try:
        r = subprocess.run(
            ["nmap", "-p", "21,22,23,25,80,443,3306,5432,6379,8080", target],
            capture_output=True, text=True, timeout=30,
        )
        output = r.stdout or r.stderr
    except FileNotFoundError:
        output = "nmap not available (apt install nmap)"
    return jsonify({"status": "ok", "output": output, "target": target})


@app.route("/api/security/ping_all", methods=["POST"])
def sec_ping_all():
    _log("Ping all hosts")
    results = []
    for node in TOPOLOGY_NODES:
        up = _ping(node["ip"])
        results.append(f"{'✅' if up else '❌'} {node['name']} ({node['ip']}): {'UP' if up else 'DOWN'}")
        with _state_lock:
            _state["hosts"][node["id"]] = {
                "status":     "UP" if up else "DOWN",
                "last_check": datetime.now().strftime("%H:%M:%S"),
            }
    _log("Ping all done")
    return jsonify({"status": "ok", "output": "\n".join(results)})


@app.route("/api/security/check_acl", methods=["POST"])
def sec_check_acl():
    _log("ACL check")
    try:
        r = subprocess.run(
            ["iptables", "-L", "-n", "-v"],
            capture_output=True, text=True, timeout=10,
        )
        return jsonify({"status": "ok", "output": r.stdout or r.stderr})
    except FileNotFoundError:
        return jsonify({"status": "error", "output": "iptables not available"})
    except Exception as exc:
        return jsonify({"status": "error", "output": str(exc)})


# ── Auto-fix endpoints ───────────────────────────────────────────────────────

@app.route("/api/autofix/close_ports", methods=["POST"])
def fix_close_ports():
    data  = request.get_json(silent=True) or {}
    ports = data.get("ports", [21, 23, 8080])
    _log(f"Closing ports: {ports}")
    results = []
    try:
        for port in ports:
            r = subprocess.run(
                ["iptables", "-A", "INPUT", "-p", "tcp", "--dport", str(port), "-j", "DROP"],
                capture_output=True, text=True,
            )
            results.append(f"{'✅' if r.returncode == 0 else '❌'} port {port}" +
                           (f": {r.stderr.strip()}" if r.returncode != 0 else ""))
    except FileNotFoundError:
        results.append("❌ iptables not available")
    return jsonify({"status": "ok", "output": "\n".join(results)})


@app.route("/api/autofix/enable_firewall", methods=["POST"])
def fix_enable_firewall():
    _log("Enabling firewall (ufw)")
    try:
        r = subprocess.run(["ufw", "--force", "enable"], capture_output=True, text=True)
        return jsonify({"status": "ok", "output": r.stdout or r.stderr})
    except FileNotFoundError:
        msg = "ufw not available (apt install ufw)"
        _log(msg, "WARN")
        return jsonify({"status": "error", "output": msg})


@app.route("/api/autofix/update_patches", methods=["POST"])
def fix_update_patches():
    _log("apt-get update")
    try:
        r = subprocess.run(
            ["apt-get", "update", "-y"],
            capture_output=True, text=True, timeout=120,
        )
        return jsonify({"status": "ok", "output": r.stdout or r.stderr})
    except FileNotFoundError:
        return jsonify({"status": "error", "output": "apt-get not available"})
    except subprocess.TimeoutExpired:
        return jsonify({"status": "error", "output": "apt-get timed out"})


@app.route("/api/autofix/reset_acl", methods=["POST"])
def fix_reset_acl():
    _log("Resetting iptables ACL")
    cmds = [
        ["iptables", "-F"],
        ["iptables", "-X"],
        ["iptables", "-P", "INPUT",   "ACCEPT"],
        ["iptables", "-P", "FORWARD", "ACCEPT"],
        ["iptables", "-P", "OUTPUT",  "ACCEPT"],
    ]
    results = []
    try:
        for cmd in cmds:
            r = subprocess.run(cmd, capture_output=True, text=True)
            results.append(f"{'✅' if r.returncode == 0 else '❌'} {' '.join(cmd[1:])}" +
                           (f": {r.stderr.strip()}" if r.returncode != 0 else ""))
    except FileNotFoundError:
        results.append("❌ iptables not available")
    _log("ACL reset done")
    return jsonify({"status": "ok", "output": "\n".join(results)})


# ── SocketIO events ──────────────────────────────────────────────────────────

if _SOCKETIO:
    @socketio.on("connect")
    def _on_connect():
        with _state_lock:
            snap = dict(_state["hosts"])
        sio_emit("status_update", {"hosts": snap})


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    # Start background ping thread
    t = threading.Thread(target=_background_status_check, daemon=True)
    t.start()

    if _SOCKETIO:
        socketio.run(app, host="0.0.0.0", port=5050, debug=False)
    else:
        app.run(host="0.0.0.0", port=5050, debug=False)


if __name__ == "__main__":
    main()
