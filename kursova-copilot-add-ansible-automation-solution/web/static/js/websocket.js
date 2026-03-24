/* ============================================================
   websocket.js – Socket.IO real-time updates client
   ============================================================ */

'use strict';

(function () {
  let _socket = null;
  let _connected = false;
  let _reconnectTimer = null;

  function connect() {
    if (_socket) {
      _socket.disconnect();
    }

    _socket = io({
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: 10,
      reconnectionDelay: 2000,
    });

    _socket.on('connect', () => {
      _connected = true;
      _setIndicator(true);
    });

    _socket.on('disconnect', () => {
      _connected = false;
      _setIndicator(false);
    });

    _socket.on('connect_error', () => {
      _connected = false;
      _setIndicator(false);
    });

    _socket.on('connection_status', (data) => {
      if (data && data.status === 'connected') {
        _connected = true;
        _setIndicator(true);
      }
    });

    // Real-time test result updates
    _socket.on('test_update', (record) => {
      if (!record || !record.id) return;

      // Merge into cache
      if (!window._cachedResults) window._cachedResults = [];
      const idx = window._cachedResults.findIndex(r => r.id === record.id);
      if (idx >= 0) {
        window._cachedResults[idx] = record;
      } else {
        window._cachedResults.push(record);
      }

      renderResultsTable(window._cachedResults);
      if (typeof updateStatsFromResults === 'function') updateStatsFromResults();

      const statusLabel = record.status === 'pass' ? '✅ Pass'
        : record.status === 'fail' ? '❌ Fail' : '⚠️ Warning';
      if (typeof showToast === 'function') {
        showToast(
          `[Live] ${(record.test_name || '').replace(/_/g, ' ')}: ${statusLabel}`,
          record.status === 'pass' ? 'success' : 'danger'
        );
      }
    });
  }

  function _setIndicator(online) {
    const el = document.getElementById('ws-indicator');
    if (!el) return;
    const icon = el.querySelector('.fa-circle');
    if (!icon) return;
    icon.style.color = online ? 'var(--success, #3fb950)' : 'var(--text-secondary, #8b949e)';
    el.title = online ? 'WebSocket: connected' : 'WebSocket: disconnected';
  }

  document.addEventListener('DOMContentLoaded', connect);
})();
