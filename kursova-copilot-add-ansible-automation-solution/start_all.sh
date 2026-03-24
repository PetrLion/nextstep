#!/bin/bash
echo "🚀 Запускаємо все..."

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Прапор --ansible для опціонального запуску Ansible автоматизації
RUN_ANSIBLE=false
for arg in "$@"; do
    if [ "$arg" = "--ansible" ]; then
        RUN_ANSIBLE=true
    fi
done

# 1. Ansible автоматизація (опціонально, якщо передано --ansible)
#    Виконується ПЕРЕД запуском GNS3, щоб підготувати JSON проект
if [ "$RUN_ANSIBLE" = true ]; then
    echo ""
    echo "🤖 Запускаємо Ansible автоматизацію (JSON маніпуляція, без REST API)..."
    ANSIBLE_DIR="$SCRIPT_DIR/ansible"
    PLAYBOOK="$ANSIBLE_DIR/playbooks/topology.yml"
    INVENTORY="$ANSIBLE_DIR/inventory.ini"
    if [ -f "$PLAYBOOK" ] && [ -f "$INVENTORY" ]; then
        ansible-playbook -i "$INVENTORY" "$PLAYBOOK"
        ANSIBLE_RC=$?
        if [ $ANSIBLE_RC -eq 0 ]; then
            echo "✅ Ansible автоматизація завершена успішно"
        else
            echo "⚠️  Ansible завершився з помилкою (код $ANSIBLE_RC) — продовжуємо"
        fi
    else
        echo "⚠️  Ansible playbook не знайдено ($PLAYBOOK) — пропускаємо"
    fi
fi

# 2. GNS3 server
echo "📡 GNS3 server..."
gns3server --host 127.0.0.1 --port 3080 &
GNS3_PID=$!
sleep 3

# Перевірка
if curl -s http://localhost:3080/v3/version > /dev/null 2>&1; then
    echo "✅ GNS3 server запущено"
else
    echo "⚠️  GNS3 server не відповідає — спробуємо інакше"
    kill "$GNS3_PID" 2>/dev/null
    python3 -m gns3server --host 127.0.0.1 --port 3080 &
    GNS3_PID=$!
    sleep 3
fi

# 3. Веб-інтерфейс
echo "🌐 Запускаємо веб-інтерфейс..."
fuser -k 5050/tcp 2>/dev/null || true
sleep 1
WEB_APP="$SCRIPT_DIR/web/app.py"
if [ -f "$WEB_APP" ]; then
    python3 "$WEB_APP" &
    WEB_PID=$!
else
    echo "⚠️  $WEB_APP не знайдено — веб-інтерфейс не запущено"
    WEB_PID=""
fi

sleep 2
echo ""
echo "════════════════════════════════════"
echo "✅ Все запущено!"
echo "   GNS3 API:  http://localhost:3080"
echo "   Web UI:    http://localhost:5050"
if [ "$RUN_ANSIBLE" = true ]; then
    echo "   Ansible:   завершено (JSON: /tmp/gns3_project/Network_Topology.gns3)"
fi
echo "════════════════════════════════════"
echo ""
echo "Натисни Ctrl+C щоб зупинити все"
echo "Підказка: ./start_all.sh --ansible   щоб запустити з Ansible автоматизацією"

# Чекаємо
if [ -n "$WEB_PID" ]; then
    wait $WEB_PID
else
    wait $GNS3_PID
fi
