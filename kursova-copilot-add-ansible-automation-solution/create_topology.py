#!/usr/bin/env python3
import requests
import json

GNS3_URL = "http://127.0.0.1:3080"

# 1. Створити проект
project_data = {
    "name": "Network_Topology",
    "path": "/tmp/gns3_projects"
}

r = requests.post(f"{GNS3_URL}/v3/projects", json=project_data)
if r.status_code in [200, 201]:
    project = r.json()
    project_id = project["project_id"]
    print(f"✅ Проект створено: {project_id}")
else:
    print(f"⚠️ Помилка: {r.status_code} {r.text}")
    project_id = None

if project_id:
    print(f"🌐 Топологія доступна: {GNS3_URL}/static/web-ui/controller/#/projects/{project_id}")

