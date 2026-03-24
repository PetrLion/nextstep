/* ============================================================
   app.js – Main application logic
   ============================================================ */

'use strict';

// ---------------------------------------------------------------------------
// CSRF helper
// ---------------------------------------------------------------------------

function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.getAttribute('content') : '';
}

// ---------------------------------------------------------------------------
// Toast notifications
// ---------------------------------------------------------------------------

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const colorMap = {
    success: 'text-success',
    danger:  'text-danger',
    warning: 'text-warning',
    info:    'text-accent',
    error:   'text-danger',
  };
  const iconMap = {
    success: 'fa-circle-check',
    danger:  'fa-circle-xmark',
    warning: 'fa-triangle-exclamation',
    info:    'fa-circle-info',
    error:   'fa-circle-xmark',
  };

  const id = 'toast-' + Date.now();
  const colorClass = colorMap[type] || 'text-light';
  const icon = iconMap[type] || 'fa-circle-info';

  const html = `
    <div id="${id}" class="toast align-items-center" role="alert" aria-live="assertive" aria-atomic="true">
      <div class="toast-header">
        <i class="fa-solid ${icon} me-2 ${colorClass}"></i>
        <strong class="me-auto">Security Dashboard</strong>
        <button type="button" class="btn-close btn-close-white ms-2" data-bs-dismiss="toast"></button>
      </div>
      <div class="toast-body">${escapeHtml(message)}</div>
    </div>`;

  container.insertAdjacentHTML('beforeend', html);
  const toastEl = document.getElementById(id);
  const bsToast = new bootstrap.Toast(toastEl, { delay: 4000 });
  bsToast.show();
  toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(String(str)));
  return div.innerHTML;
}

// ---------------------------------------------------------------------------
// Stats loading
// ---------------------------------------------------------------------------

async function fetchTopologyStats() {
  try {
    const res = await fetch('/api/security/topology');
    if (!res.ok) {
      setStats('—', '—', '—', '—');
      return;
    }
    const data = await res.json();
    setStats(data.node_count ?? '—', '—', '—', '—');
  } catch (_) {
    setStats('—', '—', '—', '—');
  }

  // Update open-ports and vuln counts from latest results
  updateStatsFromResults();
}

function setStats(nodes, ports, vulns, critical) {
  const ids = ['stat-nodes', 'stat-ports', 'stat-vulns', 'stat-critical'];
  const vals = [nodes, ports, vulns, critical];
  ids.forEach((id, i) => {
    const el = document.getElementById(id);
    if (el) el.textContent = vals[i];
  });
}

function updateStatsFromResults() {
  const results = window._cachedResults || [];
  let openPorts = '—';
  let vulns = '—';
  let critical = 0;

  results.forEach(r => {
    if (r.test_name === 'port_scan' && r.details && r.details.open_ports) {
      openPorts = r.details.open_ports.length;
    }
    if (r.test_name === 'vulnerability_check' && r.details && r.details.vulnerabilities) {
      vulns = r.details.vulnerabilities.length;
    }
    if (r.severity === 'critical') critical++;
  });

  const portEl = document.getElementById('stat-ports');
  const vulnEl = document.getElementById('stat-vulns');
  const critEl = document.getElementById('stat-critical');
  if (portEl && openPorts !== '—') portEl.textContent = openPorts;
  if (vulnEl && vulns !== '—') vulnEl.textContent = vulns;
  if (critEl) critEl.textContent = critical || '0';
}

// ---------------------------------------------------------------------------
// Security tests
// ---------------------------------------------------------------------------

async function runSecurityTest(testName) {
  const spinner = document.getElementById('spin-' + testName);
  if (spinner) spinner.classList.remove('d-none');

  try {
    const res = await fetch('/api/security/test/' + encodeURIComponent(testName), {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCsrfToken(),
        'Content-Type': 'application/json',
      },
    });
    const data = await res.json();

    if (res.ok) {
      const statusLabel = data.status === 'pass' ? '✅ Pass' : data.status === 'fail' ? '❌ Fail' : '⚠️ Warning';
      showToast(`${testName.replace(/_/g, ' ')}: ${statusLabel}`, data.status === 'pass' ? 'success' : 'danger');
      loadResults();
      updateStatsFromResults();
    } else {
      showToast('Error: ' + (data.error || 'Unknown error'), 'error');
    }
  } catch (err) {
    showToast('Network error: ' + err.message, 'error');
  } finally {
    if (spinner) spinner.classList.add('d-none');
  }
}

// ---------------------------------------------------------------------------
// Auto-fix
// ---------------------------------------------------------------------------

async function applyFix(fixName) {
  const label = fixName.replace(/_/g, ' ');
  if (!confirm(`Apply fix: "${label}"?\n\nThis will attempt to modify system security settings.`)) {
    return;
  }

  try {
    const res = await fetch('/api/security/fix/' + encodeURIComponent(fixName), {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCsrfToken(),
        'Content-Type': 'application/json',
      },
    });
    const data = await res.json();

    if (res.ok) {
      showToast(`Fix "${label}": ${data.message}`, data.status === 'success' ? 'success' : 'warning');
    } else {
      showToast('Fix error: ' + (data.error || 'Unknown'), 'error');
    }
  } catch (err) {
    showToast('Network error: ' + err.message, 'error');
  }
}

// ---------------------------------------------------------------------------
// Results
// ---------------------------------------------------------------------------

async function loadResults() {
  try {
    const res = await fetch('/api/security/results');
    if (!res.ok) return;
    const data = await res.json();
    window._cachedResults = data;
    renderResultsTable(data);
    updateStatsFromResults();
  } catch (_) { /* silent */ }
}

async function deleteResult(id) {
  if (!confirm('Delete this result?')) return;
  try {
    const res = await fetch('/api/security/results/' + encodeURIComponent(id), {
      method: 'DELETE',
      headers: { 'X-CSRFToken': getCsrfToken() },
    });
    if (res.ok) {
      showToast('Result deleted', 'success');
      loadResults();
    }
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

async function clearResults() {
  const results = window._cachedResults || [];
  if (!results.length) return;
  if (!confirm('Delete ALL results?')) return;
  await Promise.all(results.map(r =>
    fetch('/api/security/results/' + encodeURIComponent(r.id), {
      method: 'DELETE',
      headers: { 'X-CSRFToken': getCsrfToken() },
    }).catch(() => {})
  ));
  showToast('All results cleared', 'success');
  loadResults();
}

// ---------------------------------------------------------------------------
// Export
// ---------------------------------------------------------------------------

function exportCSV() {
  const results = window._cachedResults || [];
  if (!results.length) { showToast('No results to export', 'warning'); return; }

  const header = ['id', 'test_name', 'status', 'severity', 'duration', 'timestamp'];
  const rows = results.map(r => header.map(k => JSON.stringify(r[k] ?? '')).join(','));
  const csv = [header.join(','), ...rows].join('\n');
  downloadFile('security_results.csv', csv, 'text/csv');
}

function exportJSON() {
  const results = window._cachedResults || [];
  if (!results.length) { showToast('No results to export', 'warning'); return; }
  downloadFile('security_results.json', JSON.stringify(results, null, 2), 'application/json');
}

function downloadFile(name, content, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}
