#!/usr/bin/env python3
import json
import uuid

PROJECT_FILE = "/home/petr0/GNS3/projects/6d0b684f-10d9-4849-9567-da44cff31363/Network_Topology.gns3"

# Читаємо проект
with open(PROJECT_FILE, 'r') as f:
    project = json.load(f)

# Додаємо вузли в topology.nodes
routers = ["R1", "R2", "R3", "R4"]
x_pos = 100

for router_name in routers:
    node = {
        "compute_id": "local",
        "console": 5000,
        "console_type": "telnet",
        "custom_adapters": [],
        "first_port_name": None,
        "height": 59,
        "label": {
            "rotation": 0,
            "style": "font-family: DejaVu Sans Mono;font-size: 10.0;font-weight: bold;fill: #2e3436;fill-opacity: 1.0",
            "text": router_name,
            "x": -25,
            "y": -25
        },
        "locked": False,
        "name": router_name,
        "node_id": str(uuid.uuid4()),
        "node_type": "qemu",
        "properties": {
            "adapters": 4,
            "memory": 256,
            "name": router_name
        },
        "x": x_pos,
        "y": 100,
        "width": 72,
        "symbol": ":/symbols/router.svg"
    }
    
    project["topology"]["nodes"].append(node)
    x_pos += 150

# Зберігаємо проект
with open(PROJECT_FILE, 'w') as f:
    json.dump(project, f, indent=2)

print("✅ 4 маршрутизатори додано!")
print(f"📁 Файл: {PROJECT_FILE}")
print(f"🔄 Перезавантажи браузер (F5)")
