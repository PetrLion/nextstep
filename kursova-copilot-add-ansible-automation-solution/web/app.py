#!/usr/bin/env python3
"""Flask web dashboard for GNS3 topology management (port 5050)."""

import ipaddress
import json
import os
import subprocess
import threading
from datetime import datetime
from typing import Optional

import requests
from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_socketio import SocketIO, emit

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET", "gns3-dashboard-secret")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GNS3_URL = os.environ.get("GNS3_URL", "http://127.0.0.1:3080")
GNS3_PROJECT_FILE = os.environ.get(
    "GNS3_PROJECT_FILE",
    "/tmp/gns3_project/Network_Topology.gns3",
)
GNS3_PROJECT_ID = os.environ.get("GNS3_PROJECT_ID", "")

# In-memory cache for scan / validation results
_scan_cache: dict = {}
_validation_cache: dict = {}

# ---------------------------------------------------------------------------
# GNS3 helpers (REST API + .gns3 file fallback)
# ---------------------------------------------------------------------------


def _gns3_get(path: str, timeout: int = 3) -> Optional[dict]:
    """GET from GNS3 REST API; returns parsed JSON or None on error."""
    try:
        r = requests.get(f"{GNS3_URL}/v3{path}", timeout=timeout)
        if r.ok:
            return r.json()
    except requests.RequestException:
        pass
    return None


def _gns3_post(path: str, data: Optional[dict] = None, timeout: int = 5):
    """POST to GNS3 REST API; returns (ok, response_dict)."""
    try:
        r = requests.post(
            f"{GNS3_URL}/v3{path}",
            json=data or {},
            timeout=timeout,
        )
        return r.ok, r.json() if r.content else {}
    except requests.RequestException as exc:
        return False, {"error": str(exc)}


def _gns3_delete(path: str, timeout: int = 5):
    """DELETE via GNS3 REST API; returns (ok, response_dict)."""
    try:
        r = requests.delete(f"{GNS3_URL}/v3{path}", timeout=timeout)
        return r.ok, r.json() if r.content else {}
    except requests.RequestException as exc:
        return False, {"error": str(exc)}


def _load_project_file():
    """Load and parse the .gns3 project file (fallback when API unavailable)."""
    if not os.path.exists(GNS3_PROJECT_FILE):
        return None
    with open(GNS3_PROJECT_FILE, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _resolve_project_id() -> str:
    """Return active project ID: env var > API > file."""
    if GNS3_PROJECT_ID:
        return GNS3_PROJECT_ID
    projects = _gns3_get("/projects")
    if projects:
        for p in projects:
            if p.get("status") == "opened":
                return p["project_id"]
        if projects:
            return projects[0]["project_id"]
    project = _load_project_file()
    if project:
        return project.get("project_id", "")
    return ""


def _node_id_to_name(nodes: list) -> dict:
    """Return mapping node_id -> name."""
    return {n["node_id"]: n["name"] for n in nodes}


def _get_nodes_and_links():
    """Return (nodes, links, source) using API first, then file fallback."""
    pid = _resolve_project_id()
    if pid:
        api_nodes = _gns3_get(f"/projects/{pid}/nodes")
        api_links = _gns3_get(f"/projects/{pid}/links")
        if api_nodes is not None and api_links is not None:
            id_map = _node_id_to_name(api_nodes)
            links_out = []
            for lnk in api_links:
                endpoints = lnk.get("nodes", [])
                if len(endpoints) >= 2:
                    links_out.append(
                        {
                            "link_id": lnk.get("link_id"),
                            "node_a": id_map.get(endpoints[0].get("node_id"), "?"),
                            "node_b": id_map.get(endpoints[1].get("node_id"), "?"),
                            "node_a_id": endpoints[0].get("node_id"),
                            "node_b_id": endpoints[1].get("node_id"),
                        }
                    )
            return api_nodes, links_out, "api"

    # fallback: .gns3 file
    project = _load_project_file()
    if project:
        nodes = project.get("topology", {}).get("nodes", [])
        id_map = _node_id_to_name(nodes)
        links_out = []
        for lnk in project.get("topology", {}).get("links", []):
            endpoints = lnk.get("nodes", [])
            if len(endpoints) >= 2:
                links_out.append(
                    {
                        "link_id": lnk.get("link_id"),
                        "node_a": id_map.get(endpoints[0].get("node_id"), "?"),
                        "node_b": id_map.get(endpoints[1].get("node_id"), "?"),
                        "node_a_id": endpoints[0].get("node_id"),
                        "node_b_id": endpoints[1].get("node_id"),
                    }
                )
        return nodes, links_out, "file"

    return [], [], "none"


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    """Dashboard – table of all nodes."""
    nodes, links, source = _get_nodes_and_links()
    gns3_online = source == "api"
    return render_template(
        "index.html",
        nodes=nodes,
        links=links,
        gns3_online=gns3_online,
        source=source,
        ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        project_file=GNS3_PROJECT_FILE,
        gns3_url=GNS3_URL,
    )


@app.route("/topology")
def topology():
    """Interactive topology graph."""
    nodes, links, source = _get_nodes_and_links()
    return render_template(
        "topology.html",
        nodes_json=json.dumps(nodes),
        links_json=json.dumps(links),
        gns3_online=(source == "api"),
    )


@app.route("/validation")
def validation():
    """Topology validation page."""
    return render_template("validation.html", result=_validation_cache)


@app.route("/scan")
def scan():
    """Network scan page."""
    return render_template("scan.html", result=_scan_cache)


@app.route("/config")
def config():
    """Config editor page."""
    nodes, _, source = _get_nodes_and_links()
    return render_template("config.html", nodes=nodes, gns3_online=(source == "api"))


# ---------------------------------------------------------------------------
# REST API
# ---------------------------------------------------------------------------


@app.route("/api/nodes")
def api_nodes():
    nodes, _, _ = _get_nodes_and_links()
    return jsonify(nodes)


@app.route("/api/links")
def api_links():
    _, links, _ = _get_nodes_and_links()
    return jsonify(links)


@app.route("/api/topology")
def api_topology():
    nodes, links, source = _get_nodes_and_links()
    return jsonify(
        {
            "nodes": nodes,
            "links": links,
            "source": source,
            "scanned_at": datetime.now().isoformat(),
        }
    )


@app.route("/api/node/<node_id>/start", methods=["POST"])
def api_node_start(node_id: str):
    pid = _resolve_project_id()
    if not pid:
        return jsonify({"error": "No project found"}), 404
    ok, data = _gns3_post(f"/projects/{pid}/nodes/{node_id}/start")
    _broadcast_nodes()
    return jsonify(data), 200 if ok else 500


@app.route("/api/node/<node_id>/stop", methods=["POST"])
def api_node_stop(node_id: str):
    pid = _resolve_project_id()
    if not pid:
        return jsonify({"error": "No project found"}), 404
    ok, data = _gns3_post(f"/projects/{pid}/nodes/{node_id}/stop")
    _broadcast_nodes()
    return jsonify(data), 200 if ok else 500


@app.route("/api/node/<node_id>", methods=["DELETE"])
def api_node_delete(node_id: str):
    pid = _resolve_project_id()
    if not pid:
        return jsonify({"error": "No project found"}), 404
    ok, data = _gns3_delete(f"/projects/{pid}/nodes/{node_id}")
    _broadcast_nodes()
    return jsonify(data), 200 if ok else 500


@app.route("/api/node", methods=["POST"])
def api_node_create():
    pid = _resolve_project_id()
    if not pid:
        return jsonify({"error": "No project found"}), 404
    payload = request.get_json(force=True) or {}
    ok, data = _gns3_post(f"/projects/{pid}/nodes", payload)
    _broadcast_nodes()
    return jsonify(data), 201 if ok else 500


@app.route("/api/link", methods=["POST"])
def api_link_create():
    pid = _resolve_project_id()
    if not pid:
        return jsonify({"error": "No project found"}), 404
    payload = request.get_json(force=True) or {}
    ok, data = _gns3_post(f"/projects/{pid}/links", payload)
    _broadcast_nodes()
    return jsonify(data), 201 if ok else 500


@app.route("/api/link/<link_id>", methods=["DELETE"])
def api_link_delete(link_id: str):
    pid = _resolve_project_id()
    if not pid:
        return jsonify({"error": "No project found"}), 404
    ok, data = _gns3_delete(f"/projects/{pid}/links/{link_id}")
    _broadcast_nodes()
    return jsonify(data), 200 if ok else 500


@app.route("/api/validate")
def api_validate():
    """Validate topology: isolated nodes, cycles, connectivity."""
    nodes, links, source = _get_nodes_and_links()
    errors = []
    warnings = []

    if not nodes:
        errors.append("No nodes found in topology")
    else:
        # Build adjacency for connectivity check
        node_ids = {n["node_id"] for n in nodes}
        connected_ids: set = set()
        adj: dict[str, list] = {n["node_id"]: [] for n in nodes}
        for lnk in links:
            a = lnk.get("node_a_id", "")
            b = lnk.get("node_b_id", "")
            if a and b:
                adj[a].append(b)
                adj[b].append(a)
                connected_ids.add(a)
                connected_ids.add(b)

        # Isolated nodes
        isolated = [
            n["name"] for n in nodes if n["node_id"] not in connected_ids
        ]
        if isolated:
            warnings.append(f"Isolated nodes (no links): {', '.join(isolated)}")

        # Cycle detection for undirected graph (DFS)
        visited: set = set()

        def _has_cycle(v: str, parent: str) -> bool:
            visited.add(v)
            for nb in adj.get(v, []):
                if nb == parent:
                    continue
                if nb in visited:
                    return True
                if _has_cycle(nb, v):
                    return True
            return False

        cycle_found = False
        for node_id in node_ids:
            if node_id not in visited:
                if _has_cycle(node_id, ""):
                    cycle_found = True
                    break
        if cycle_found:
            warnings.append("Cycle detected in topology graph")

    status = "error" if errors else ("warning" if warnings else "ok")
    result = {
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "nodes_count": len(nodes),
        "links_count": len(links),
        "source": source,
        "checked_at": datetime.now().isoformat(),
    }
    _validation_cache.clear()
    _validation_cache.update(result)
    socketio.emit("validation_update", result)
    return jsonify(result)


@app.route("/api/scan")
def api_scan():
    """Scan network for active hosts and open ports."""
    nodes, _, source = _get_nodes_and_links()

    hosts_up = []
    hosts_down = []
    scan_errors = []

    for node in nodes:
        ip = None
        # Try to extract management IP from node properties
        props = node.get("properties", {})
        for key in ("console_host", "management_ip", "hostname"):
            if props.get(key) and props[key] not in ("0.0.0.0", ""):
                ip = props[key]
                break

        if not ip:
            hosts_down.append({"name": node.get("name", "?"), "reason": "no IP"})
            continue

        # Validate IP address to prevent command injection
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            scan_errors.append({"name": node.get("name", "?"), "ip": ip, "error": "invalid IP address"})
            continue

        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "1", ip],
                capture_output=True,
                timeout=3,
            )
            if result.returncode == 0:
                hosts_up.append({"name": node.get("name", "?"), "ip": ip})
            else:
                hosts_down.append({"name": node.get("name", "?"), "ip": ip, "reason": "no ping reply"})
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            scan_errors.append({"name": node.get("name", "?"), "ip": ip, "error": str(exc)})

    result = {
        "hosts_up": hosts_up,
        "hosts_down": hosts_down,
        "errors": scan_errors,
        "total": len(nodes),
        "source": source,
        "scanned_at": datetime.now().isoformat(),
    }
    _scan_cache.clear()
    _scan_cache.update(result)
    socketio.emit("scan_update", result)
    return jsonify(result)


@app.route("/api/node/<node_id>/config")
def api_node_config_get(node_id: str):
    """Get startup config for a node."""
    pid = _resolve_project_id()
    if not pid:
        return jsonify({"error": "No project found"}), 404
    data = _gns3_get(f"/projects/{pid}/nodes/{node_id}/files/etc/frr/frr.conf")
    if data is None:
        # Try alternative paths
        data = _gns3_get(f"/projects/{pid}/nodes/{node_id}/files/startup-config.cfg")
    return jsonify({"config": data})


@app.route("/api/ansible_update", methods=["POST"])
def api_ansible_update():
    """Receive updates from Ansible automation manager."""
    payload = request.get_json(force=True) or {}
    socketio.emit("ansible_update", payload)
    return jsonify({"status": "received"})


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------


@socketio.on("connect")
def on_connect():
    nodes, links, source = _get_nodes_and_links()
    emit("topology_update", {"nodes": nodes, "links": links, "source": source})


def _broadcast_nodes():
    """Push updated topology to all connected clients."""
    def _run():
        nodes, links, source = _get_nodes_and_links()
        socketio.emit("topology_update", {"nodes": nodes, "links": links, "source": source})

    threading.Thread(target=_run, daemon=True).start()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5050, debug=False, allow_unsafe_werkzeug=True)
