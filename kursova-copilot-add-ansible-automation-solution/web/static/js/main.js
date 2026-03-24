/* ============================================================
   GNS3 Dashboard – Main JavaScript
   ============================================================ */

// ---------------------------------------------------------------------------
// WebSocket (Socket.IO)
// ---------------------------------------------------------------------------

const socket = io({ transports: ['websocket', 'polling'] });

socket.on('connect', () => {
  setWsStatus('connected');
});

socket.on('disconnect', () => {
  setWsStatus('disconnected');
});

socket.on('connect_error', () => {
  setWsStatus('error');
});

function setWsStatus(state) {
  const el = document.getElementById('ws-status');
  if (!el) return;
  const map = {
    connected:    ['bg-success', '🟢 Live'],
    disconnected: ['bg-secondary', '⚫ Offline'],
    error:        ['bg-danger',   '🔴 Error'],
    connecting:   ['bg-secondary', '⚪ Connecting…'],
  };
  const [cls, label] = map[state] || map.connecting;
  el.innerHTML = `<span class="badge ${cls}">${label}</span>`;
}

// ---------------------------------------------------------------------------
// Toast notifications
// ---------------------------------------------------------------------------

/**
 * Display a Bootstrap toast.
 * @param {'success'|'danger'|'warning'|'info'} type  Bootstrap color variant
 * @param {string} message  Text to show
 */
function showToast(type, message) {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const id = `toast-${Date.now()}`;
  const icons = {
    success: 'bi-check-circle-fill',
    danger:  'bi-x-circle-fill',
    warning: 'bi-exclamation-triangle-fill',
    info:    'bi-info-circle-fill',
  };
  const icon = icons[type] || 'bi-bell-fill';

  const html = `
    <div id="${id}" class="toast align-items-center text-bg-${type} border-0" role="alert" aria-live="polite">
      <div class="d-flex">
        <div class="toast-body">
          <i class="bi ${icon} me-2"></i>${message}
        </div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
      </div>
    </div>`;
  container.insertAdjacentHTML('beforeend', html);

  const toastEl = document.getElementById(id);
  const toast = new bootstrap.Toast(toastEl, { delay: 4000 });
  toast.show();
  toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Format ISO timestamp to local readable format. */
function formatDate(isoString) {
  if (!isoString) return '—';
  try {
    return new Date(isoString).toLocaleString('uk-UA');
  } catch {
    return isoString;
  }
}

/** Debounce utility for input handlers in page scripts. */
function debounce(fn, delay) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}
