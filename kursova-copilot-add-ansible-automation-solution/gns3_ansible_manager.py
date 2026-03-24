#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GNS3 Ansible Manager - Управління топологією GNS3 через Ansible"""

import os
import sys
import json
import logging
from pathlib import Path

# Константи (БЕЗ присвоєнь!)
GNS3_URL = "http://127.0.0.1:3080"
FLASK_URL = "http://127.0.0.1:5050"
ANSIBLE_DIR = Path(__file__).parent / "network_topology" / "ansible"
INVENTORY = ANSIBLE_DIR / "inventory.ini"
LOG_FILE = "/tmp/ansible_gns3.log"

# Логування
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def main():
    """Основна функція"""
    global GNS3_URL, FLASK_URL, LOG_FILE
    
    logger.info("🚀 Запускаємо Ansible для GNS3")
    logger.info(f"📁 Ansible директорія: {ANSIBLE_DIR}")
    
    if not ANSIBLE_DIR.exists():
        logger.error(f"❌ Ansible директорія не знайдена: {ANSIBLE_DIR}")
        sys.exit(1)
    
    if not INVENTORY.exists():
        logger.error(f"❌ Inventory файл не знайдено: {INVENTORY}")
        sys.exit(1)
    
    logger.info("✅ Все готово до запуску!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
