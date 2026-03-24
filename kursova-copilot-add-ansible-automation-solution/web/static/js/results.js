/* ============================================================
   results.js – Results table management
   ============================================================ */

'use strict';

let _sortColumn = 'timestamp';
let _sortAsc = false;
let _filterStatus = null;

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------

function renderResultsTable(data) {
  const tbody = document.getElementById('results-tbody');
  if (!tbody) return;

  let rows = [...data];

  // Filter
  if (_filterStatus) {
    rows = rows.filter(r => r.status === _filterStatus);
  }

  // Sort
  rows.sort((a, b) => {
    let va = a[_sortColumn] ?? '';
    let vb = b[_sortColumn] ?? '';
    if (typeof va === 'string') va = va.toLowerCase();
    if (typeof vb === 'string') vb = vb.toLowerCase();
    if (va < vb) return _sortAsc ? -1 : 1;
    if (va > vb) return _sortAsc ? 1 : -1;
    return 0;
  });

  const emptyRow = document.getElementById('results-empty-row');

  if (!rows.length) {
    if (emptyRow) {
      emptyRow.style.display = '';
    } else {
      tbody.innerHTML = `
        <tr><td colspan="7" class="text-center text-muted py-4">
          <i class="fa-solid fa-flask me-2"></i>No results found
        </td></tr>`;
    }
    return;
  }

  if (emptyRow) emptyRow.style.display = 'none';

  // Build rows (replace only non-empty rows)
  const existingIds = new Set(
    [...tbody.querySelectorAll('tr[data-result-id]')].map(tr => tr.dataset.resultId)
  );
  const newIds = new Set(rows.map(r => r.id));

  // Remove stale rows
  tbody.querySelectorAll('tr[data-result-id]').forEach(tr => {
    if (!newIds.has(tr.dataset.resultId)) tr.remove();
  });

  // Add / update rows
  rows.forEach((r, idx) => {
    const existingRow = tbody.querySelector(`tr[data-result-id="${r.id}"]`);
    const html = _buildRow(r);
    if (existingRow) {
      existingRow.outerHTML = html;
    } else {
      tbody.insertAdjacentHTML('beforeend', html);
    }
  });
}

function _buildRow(r) {
  const statusIcon = {
    pass:    '<i class="fa-solid fa-circle-check text-success me-1"></i>',
    fail:    '<i class="fa-solid fa-circle-xmark text-danger me-1"></i>',
    warning: '<i class="fa-solid fa-triangle-exclamation text-warning me-1"></i>',
    error:   '<i class="fa-solid fa-circle-minus text-secondary me-1"></i>',
  }[r.status] || '';

  const severityBadge = `<span class="badge badge-${escapeHtml(r.severity || 'unknown')} px-2 py-1">${escapeHtml(r.severity || '?')}</span>`;
  const testLabel = escapeHtml((r.test_name || '').replace(/_/g, ' '));
  const duration = r.duration != null ? r.duration + ' ms' : '—';
  const ts = r.timestamp ? new Date(r.timestamp).toLocaleString() : '—';
  const message = r.details && r.details.message ? escapeHtml(r.details.message.slice(0, 60)) : '—';

  return `<tr data-result-id="${escapeHtml(r.id)}">
    <td class="fw-medium">${testLabel}</td>
    <td>${statusIcon}<span class="status-${escapeHtml(r.status)}">${escapeHtml(r.status || '?')}</span></td>
    <td>${severityBadge}</td>
    <td class="font-monospace text-secondary">${escapeHtml(duration)}</td>
    <td class="text-secondary small">${escapeHtml(ts)}</td>
    <td class="text-muted small text-truncate" style="max-width:160px;">${message}</td>
    <td>
      <button class="btn btn-sm btn-outline-secondary py-0 px-2 me-1"
              onclick="showResultDetail('${escapeHtml(r.id)}')" title="Details">
        <i class="fa-solid fa-eye"></i>
      </button>
      <button class="btn btn-sm btn-outline-danger py-0 px-2"
              onclick="deleteResult('${escapeHtml(r.id)}')" title="Delete">
        <i class="fa-solid fa-trash"></i>
      </button>
    </td>
  </tr>`;
}

// ---------------------------------------------------------------------------
// Sorting and filtering
// ---------------------------------------------------------------------------

function sortTable(column) {
  if (_sortColumn === column) {
    _sortAsc = !_sortAsc;
  } else {
    _sortColumn = column;
    _sortAsc = false;
  }
  renderResultsTable(window._cachedResults || []);
}

function filterResults(status) {
  _filterStatus = status;
  renderResultsTable(window._cachedResults || []);
}

// ---------------------------------------------------------------------------
// Detail modal
// ---------------------------------------------------------------------------

async function showResultDetail(id) {
  const results = window._cachedResults || [];
  let record = results.find(r => r.id === id);

  if (!record) {
    try {
      const res = await fetch('/api/security/results/' + encodeURIComponent(id));
      if (res.ok) record = await res.json();
    } catch (_) { return; }
  }

  if (!record) return;

  const titleEl = document.getElementById('detailModalTitle');
  const bodyEl = document.getElementById('detailModalBody');
  if (titleEl) titleEl.textContent = (record.test_name || '').replace(/_/g, ' ') + ' — Details';
  if (bodyEl) bodyEl.textContent = JSON.stringify(record, null, 2);

  const modalEl = document.getElementById('detailModal');
  if (modalEl) {
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
  }
}
