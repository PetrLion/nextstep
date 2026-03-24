#!/usr/bin/env python3
"""Flask web UI for GNS3 topology monitoring (port 5050)."""

import json
import os
from datetime import datetime
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

GNS3_PROJECT_FILE = os.environ.get(
    "GNS3_PROJECT_FILE",
    "/tmp/gns3_project/Network_Topology.gns3",
)

HTML = """<!DOCTYPE html>
<html lang="uk">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>GNS3 Topology Monitor</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 30px; background: #f5f5f5; }
    h1   { color: #2e3436; }
    .card {
      background: #fff; border-radius: 8px; padding: 20px;
      margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,.1);
    }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }
    th { background: #2e3436; color: #fff; }
    tr:nth-child(even) { background: #f9f9f9; }
    .badge {
      display: inline-block; padding: 2px 10px; border-radius: 12px;
      font-size: 0.85em; font-weight: bold;
    }
    .ok   { background: #8ae234; color: #1a1a1a; }
    .warn { background: #fce94f; color: #1a1a1a; }
    .err  { background: #ef2929; color: #fff; }
    a { color: #3465a4; text-decoration: none; }
    a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <h1>🖧 GNS3 Topology Monitor</h1>

  <div class="card">
    <h2>📋 Проект</h2>
    <table>
      <tr><th>Параметр</th><th>Значення</th></tr>
      <tr><td>Назва</td><td>{{ project_name }}</td></tr>
      <tr><td>Файл</td><td>{{ project_file }}</td></tr>
      <tr><td>Статус файлу</td>
          <td><span class="badge {{ 'ok' if file_ok else 'err' }}">
              {{ '✅ знайдено' if file_ok else '❌ не знайдено' }}</span></td></tr>
      <tr><td>Версія</td><td>{{ version }}</td></tr>
      <tr><td>Час перевірки</td><td>{{ ts }}</td></tr>
    </table>
  </div>

  <div class="card">
    <h2>🖧 Вузли ({{ nodes | length }})</h2>
    {% if nodes %}
    <table>
      <tr><th>#</th><th>Ім'я</th><th>Тип</th><th>Console</th><th>X</th><th>Y</th></tr>
      {% for n in nodes %}
      <tr>
        <td>{{ loop.index }}</td>
        <td>{{ n.name }}</td>
        <td>{{ n.node_type }}</td>
        <td>{{ n.console }}</td>
        <td>{{ n.x }}</td>
        <td>{{ n.y }}</td>
      </tr>
      {% endfor %}
    </table>
    {% else %}
    <p>Вузли відсутні. Запустіть: <code>./start_all.sh --ansible</code></p>
    {% endif %}
  </div>

  <div class="card">
    <h2>🔗 З'єднання ({{ links | length }})</h2>
    {% if links %}
    <table>
      <tr><th>#</th><th>Вузол A</th><th>Вузол B</th></tr>
      {% for l in links %}
      <tr>
        <td>{{ loop.index }}</td>
        <td>{{ l.node_a }}</td>
        <td>{{ l.node_b }}</td>
      </tr>
      {% endfor %}
    </table>
    {% else %}
    <p>З'єднання відсутні.</p>
    {% endif %}
  </div>

  <div class="card">
    <h3>🚀 Швидкий старт</h3>
    <pre>./start_all.sh --ansible   # повний запуск з Ansible автоматизацією
./start_all.sh             # тільки GNS3 + веб-інтерфейс</pre>
    <p><a href="/api/topology">📊 JSON API</a></p>
  </div>
</body>
</html>
"""


def _load_project():
    """Load and parse the GNS3 project JSON file."""
    if not os.path.exists(GNS3_PROJECT_FILE):
        return None
    with open(GNS3_PROJECT_FILE, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _node_id_to_name(project):
    """Return a dict mapping node_id -> name."""
    return {n["node_id"]: n["name"] for n in project.get("topology", {}).get("nodes", [])}


@app.route("/")
def index():
    project = _load_project()
    file_ok = project is not None

    if project:
        nodes = project.get("topology", {}).get("nodes", [])
        id_map = _node_id_to_name(project)
        raw_links = project.get("topology", {}).get("links", [])
        links = []
        for lnk in raw_links:
            endpoints = lnk.get("nodes", [])
            if len(endpoints) >= 2:
                links.append({
                    "node_a": id_map.get(endpoints[0].get("node_id"), "?"),
                    "node_b": id_map.get(endpoints[1].get("node_id"), "?"),
                })
        version = project.get("version", "?")
        project_name = project.get("name", "?")
    else:
        nodes = []
        links = []
        version = "—"
        project_name = "—"

    return render_template_string(
        HTML,
        project_name=project_name,
        project_file=GNS3_PROJECT_FILE,
        file_ok=file_ok,
        version=version,
        nodes=nodes,
        links=links,
        ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


@app.route("/api/topology")
def api_topology():
    project = _load_project()
    if not project:
        return jsonify({"error": "Project file not found", "path": GNS3_PROJECT_FILE}), 404

    id_map = _node_id_to_name(project)
    raw_links = project.get("topology", {}).get("links", [])
    links_out = []
    for lnk in raw_links:
        endpoints = lnk.get("nodes", [])
        if len(endpoints) >= 2:
            links_out.append({
                "link_id": lnk.get("link_id"),
                "node_a": id_map.get(endpoints[0].get("node_id"), "?"),
                "node_b": id_map.get(endpoints[1].get("node_id"), "?"),
            })

    return jsonify({
        "project_name": project.get("name"),
        "version": project.get("version"),
        "nodes": project.get("topology", {}).get("nodes", []),
        "links": links_out,
        "scanned_at": datetime.now().isoformat(),
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
