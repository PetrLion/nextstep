/* ============================================================
   topology.js – Cytoscape.js network topology visualization
   ============================================================ */

'use strict';

let _cy = null;

// ---------------------------------------------------------------------------
// Initialization
// ---------------------------------------------------------------------------

function initTopology() {
  const container = document.getElementById('cy');
  if (!container || _cy) return;

  _cy = cytoscape({
    container,
    style: _cytoscapeStyle(),
    layout: { name: 'preset' },
    userZoomingEnabled: true,
    userPanningEnabled: true,
    boxSelectionEnabled: false,
    minZoom: 0.1,
    maxZoom: 4,
  });

  _cy.on('tap', 'node', (evt) => {
    const node = evt.target;
    _showNodeInfo(node.data());
  });

  _cy.on('tap', (evt) => {
    if (evt.target === _cy) {
      _clearNodeInfo();
    }
  });
}

// ---------------------------------------------------------------------------
// Load topology data
// ---------------------------------------------------------------------------

async function loadTopology() {
  const loadingEl = document.getElementById('topo-loading');
  if (loadingEl) loadingEl.classList.remove('d-none');

  try {
    const res = await fetch('/api/security/topology');
    if (!res.ok) {
      _renderFallbackTopology();
      return;
    }
    const data = await res.json();
    _renderTopology(data);

    const legNodes = document.getElementById('leg-nodes');
    const legLinks = document.getElementById('leg-links');
    if (legNodes) legNodes.textContent = data.node_count ?? 0;
    if (legLinks) legLinks.textContent = data.link_count ?? 0;
  } catch (_) {
    _renderFallbackTopology();
  } finally {
    if (loadingEl) loadingEl.classList.add('d-none');
  }
}

function _renderTopology(data) {
  if (!_cy) initTopology();

  const elements = [];

  (data.nodes || []).forEach(n => {
    elements.push({
      data: {
        id: n.id,
        label: n.name,
        nodeType: n.node_type,
        deviceClass: _classifyDevice(n.name, n.node_type),
        x: n.x,
        y: n.y,
        status: n.status,
        console: n.console,
      },
      position: { x: n.x || 0, y: n.y || 0 },
    });
  });

  (data.links || []).forEach(l => {
    elements.push({
      data: {
        id: l.id || ('edge-' + l.source + '-' + l.target),
        source: l.source,
        target: l.target,
        label: '',
      },
    });
  });

  _cy.elements().remove();
  _cy.add(elements);

  if (elements.some(e => e.position && (e.position.x || e.position.y))) {
    _cy.fit(_cy.nodes(), 50);
  } else {
    _applyLayout();
  }
}

function _renderFallbackTopology() {
  if (!_cy) initTopology();
  // Show empty canvas with a message
  _cy.elements().remove();
}

function _applyLayout() {
  if (!_cy) return;
  _cy.layout({
    name: 'cose',
    animate: true,
    animationDuration: 600,
    nodeRepulsion: 4500,
    idealEdgeLength: 120,
    padding: 40,
  }).run();
}

function resetTopologyLayout() {
  if (!_cy) return;
  _applyLayout();
}

// ---------------------------------------------------------------------------
// Device classification
// ---------------------------------------------------------------------------

function _classifyDevice(name, nodeType) {
  if (!name) return 'router';
  const n = name.toLowerCase();
  if (n.startsWith('pc') || n.includes('workstation')) return 'pc';
  if (n.startsWith('srv') || n.includes('server') || n.includes('web') || n.includes('db') || n.includes('redis')) return 'server';
  return 'router';
}

// ---------------------------------------------------------------------------
// Node info panel
// ---------------------------------------------------------------------------

function _showNodeInfo(data) {
  const panel = document.getElementById('node-info-panel');
  if (!panel) return;

  panel.innerHTML = `
    <dl class="mb-0">
      <dt>Name</dt><dd>${escapeHtml(data.label || data.id)}</dd>
      <dt>Type</dt><dd>${escapeHtml(data.nodeType || '—')}</dd>
      <dt>Class</dt><dd>${escapeHtml(data.deviceClass || '—')}</dd>
      <dt>Status</dt><dd>${escapeHtml(data.status || '—')}</dd>
      <dt>Console</dt><dd>${data.console ? escapeHtml(String(data.console)) : '—'}</dd>
      <dt>Position</dt><dd>x=${Math.round(data.x || 0)}, y=${Math.round(data.y || 0)}</dd>
    </dl>`;
}

function _clearNodeInfo() {
  const panel = document.getElementById('node-info-panel');
  if (panel) panel.innerHTML = '<p class="text-muted small">Click a node to see details</p>';
}

// ---------------------------------------------------------------------------
// Cytoscape stylesheet
// ---------------------------------------------------------------------------

function _cytoscapeStyle() {
  return [
    {
      selector: 'node',
      style: {
        'label': 'data(label)',
        'color': '#e6edf3',
        'font-size': '11px',
        'text-valign': 'bottom',
        'text-margin-y': 6,
        'text-outline-width': 2,
        'text-outline-color': '#0d1117',
        'width': 36,
        'height': 36,
        'border-width': 2,
        'border-color': '#30363d',
      },
    },
    {
      selector: 'node[deviceClass="router"]',
      style: {
        'background-color': '#58a6ff',
        'shape': 'rectangle',
      },
    },
    {
      selector: 'node[deviceClass="pc"]',
      style: {
        'background-color': '#3fb950',
        'shape': 'ellipse',
      },
    },
    {
      selector: 'node[deviceClass="server"]',
      style: {
        'background-color': '#f78166',
        'shape': 'diamond',
      },
    },
    {
      selector: 'node:selected',
      style: {
        'border-color': '#ffffff',
        'border-width': 3,
      },
    },
    {
      selector: 'edge',
      style: {
        'line-color': '#484f58',
        'width': 2,
        'curve-style': 'bezier',
        'target-arrow-shape': 'none',
        'opacity': 0.8,
      },
    },
    {
      selector: 'edge:selected',
      style: {
        'line-color': '#58a6ff',
        'width': 3,
      },
    },
  ];
}
