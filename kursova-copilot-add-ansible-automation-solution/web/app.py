#!/usr/bin/env python3
"""Flask web UI for GNS3 topology monitoring (port 5050)."""

import json
import os
from datetime import datetime
from flask import Flask, jsonify, render_template

app = Flask(__name__)

GNS3_PROJECT_FILE = os.environ.get(
    "GNS3_PROJECT_FILE",
    "/tmp/gns3_project/Network_Topology.gns3",
)

# Zone and IP metadata for the 9-device topology
_ZONE_MAP = {
    "R1":           ("router",    "Core"),
    "R2":           ("router",    "Access"),
    "R3":           ("router",    "Perimeter"),
    "R4":           ("router",    "DMZ"),
    "PC1":          ("access",    "Access"),
    "PC2":          ("access",    "Access"),
    "PC-PERIMETER": ("perimeter", "Perimeter"),
    "SRV-WEB":      ("dmz",       "DMZ"),
    "SRV-REDIS":    ("dmz",       "DMZ"),
    "SRV-DB":       ("dmz",       "DMZ"),
}

_IP_MAP = {
    "R1":           "10.0.0.1",
    "R2":           "10.0.1.1",
    "R3":           "10.0.2.1",
    "R4":           "10.0.3.1",
    "PC1":          "10.0.1.10",
    "PC2":          "10.0.1.11",
    "PC-PERIMETER": "10.0.2.10",
    "SRV-WEB":      "10.0.3.10",
    "SRV-REDIS":    "10.0.3.11",
    "SRV-DB":       "10.0.3.12",
}


def _load_project():
    """Load and parse the GNS3 project JSON file."""
    if not os.path.exists(GNS3_PROJECT_FILE):
        return None
    with open(GNS3_PROJECT_FILE, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _node_id_to_name(project):
    """Return a dict mapping node_id -> name."""
    return {n["node_id"]: n["name"] for n in project.get("topology", {}).get("nodes", [])}


def _parse_topology(project):
    """Return (nodes, links, routers, pcs, servers) from a loaded project."""
    nodes = project.get("topology", {}).get("nodes", [])
    id_map = _node_id_to_name(project)
    raw_links = project.get("topology", {}).get("links", [])
    links = []
    for lnk in raw_links:
        endpoints = lnk.get("nodes", [])
        if len(endpoints) >= 2:
            ep_a = endpoints[0]
            ep_b = endpoints[1]
            iface_a = ep_a.get("label", {}).get("text", "")
            iface_b = ep_b.get("label", {}).get("text", "")
            links.append({
                "node_a": id_map.get(ep_a.get("node_id"), "?"),
                "node_b": id_map.get(ep_b.get("node_id"), "?"),
                "iface_a": iface_a,
                "iface_b": iface_b,
            })

    routers = [n for n in nodes if n["name"] in ("R1", "R2", "R3", "R4")]
    pcs     = [n for n in nodes if n["name"] in ("PC1", "PC2", "PC-PERIMETER")]
    servers = [n for n in nodes if n["name"] in ("SRV-WEB", "SRV-REDIS", "SRV-DB")]
    return nodes, links, routers, pcs, servers


@app.route("/")
def index():
    project = _load_project()
    file_ok = project is not None

    if project:
        nodes, links, routers, pcs, servers = _parse_topology(project)
        version = project.get("version", "?")
        project_name = project.get("name", "?")
    else:
        nodes, links, routers, pcs, servers = [], [], [], [], []
        version = "—"
        project_name = "—"

    return render_template(
        "dashboard.html",
        project_name=project_name,
        project_file=GNS3_PROJECT_FILE,
        file_ok=file_ok,
        version=version,
        nodes=nodes,
        links=links,
        routers=routers,
        pcs=pcs,
        servers=servers,
        ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


@app.route("/topology")
def topology():
    project = _load_project()
    file_ok = project is not None

    if project:
        nodes, links, routers, pcs, servers = _parse_topology(project)
        version = project.get("version", "?")
        project_name = project.get("name", "?")
    else:
        nodes, links, routers, pcs, servers = [], [], [], [], []
        version = "—"
        project_name = "—"

    nodes_json = json.dumps([
        {"name": n["name"], "x": n.get("x", 0), "y": n.get("y", 0), "console": n.get("console")}
        for n in nodes
    ])
    links_json = json.dumps(links)

    return render_template(
        "topology.html",
        project_name=project_name,
        project_file=GNS3_PROJECT_FILE,
        file_ok=file_ok,
        version=version,
        nodes=nodes,
        links=links,
        nodes_json=nodes_json,
        links_json=links_json,
        ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


@app.route("/api/topology")
def api_topology():
    project = _load_project()
    if not project:
        return jsonify({"error": "Project file not found", "path": GNS3_PROJECT_FILE}), 404

    nodes, links, routers, pcs, servers = _parse_topology(project)

    return jsonify({
        "project_name": project.get("name"),
        "version": project.get("version"),
        "nodes": project.get("topology", {}).get("nodes", []),
        "links": links,
        "scanned_at": datetime.now().isoformat(),
    })


@app.route("/api/node/<name>/<action>", methods=["POST"])
def node_action(name, action):
    """Stub endpoint for node start/stop/delete actions."""
    allowed_actions = ("start", "stop", "delete")
    if action not in allowed_actions:
        return jsonify({"error": f"Unknown action '{action}'"}), 400
    # Without a live GNS3 server this is a stub that returns a friendly message
    return jsonify({"message": f"Action '{action}' for node '{name}' queued. Connect GNS3 server to execute."})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)

