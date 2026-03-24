/**
 * topology.js — D3.js v7 topology graph renderer
 * Called from topology.html as: renderTopology(NODES, LINKS)
 */
function renderTopology(nodes, links) {
  const container = document.getElementById('topology-svg');
  const W = container.clientWidth || 860;
  const H = 520;

  const svg = d3.select('#topology-svg')
    .attr('viewBox', `0 0 ${W} ${H}`)
    .attr('preserveAspectRatio', 'xMidYMid meet');

  // ── Zone colour palette ──────────────────────────────────────────────
  const zoneColor = {
    core:      '#9b59b6',
    access:    '#3498db',
    perimeter: '#f39c12',
    dmz:       '#e74c3c',
  };

  // ── Compute static positions ─────────────────────────────────────────
  // Layout: Perimeter (top-centre), Core (centre), Access (bottom-left), DMZ (bottom-right)
  const cx = W / 2, cy = H / 2;

  const zoneCenter = {
    core:      { x: cx,           y: cy },
    access:    { x: cx * 0.35,    y: cy + 140 },
    perimeter: { x: cx,           y: cy - 160 },
    dmz:       { x: cx * 1.65,    y: cy + 140 },
  };

  // Group nodes by zone
  const byZone = {};
  nodes.forEach(n => { (byZone[n.zone] = byZone[n.zone] || []).push(n); });

  const pos = {};

  Object.entries(byZone).forEach(([zone, zNodes]) => {
    const zc = zoneCenter[zone] || { x: cx, y: cy };
    const routers = zNodes.filter(n => n.type === 'router');
    const hosts   = zNodes.filter(n => n.type !== 'router');

    // Router sits at zone centre
    routers.forEach(n => { pos[n.id] = { x: zc.x, y: zc.y }; });

    // Hosts spread below (or above for perimeter)
    const spread = 110;
    const dir = zone === 'perimeter' ? -1 : 1;
    hosts.forEach((n, i) => {
      const offset = (i - (hosts.length - 1) / 2) * spread;
      pos[n.id] = { x: zc.x + offset, y: zc.y + dir * 110 };
    });
  });

  // ── Zone background ellipses ─────────────────────────────────────────
  const zoneData = Object.entries(byZone).map(([zone, zNodes]) => {
    const xs = zNodes.map(n => pos[n.id].x);
    const ys = zNodes.map(n => pos[n.id].y);
    return {
      zone,
      cx: (Math.min(...xs) + Math.max(...xs)) / 2,
      cy: (Math.min(...ys) + Math.max(...ys)) / 2,
      rx: Math.max(60, (Math.max(...xs) - Math.min(...xs)) / 2 + 60),
      ry: Math.max(50, (Math.max(...ys) - Math.min(...ys)) / 2 + 60),
    };
  });

  svg.selectAll('.zone-bg')
    .data(zoneData)
    .enter()
    .append('ellipse')
    .attr('class', 'zone-bg')
    .attr('cx', d => d.cx)
    .attr('cy', d => d.cy)
    .attr('rx', d => d.rx)
    .attr('ry', d => d.ry)
    .attr('fill',   d => zoneColor[d.zone] + '18')
    .attr('stroke', d => zoneColor[d.zone] + '55')
    .attr('stroke-width', 1.5)
    .attr('stroke-dasharray', '6,3');

  // Zone label
  svg.selectAll('.zone-label')
    .data(zoneData)
    .enter()
    .append('text')
    .attr('class', 'zone-label')
    .attr('x', d => d.cx)
    .attr('y', d => d.cy - d.ry + 18)
    .attr('text-anchor', 'middle')
    .attr('fill', d => zoneColor[d.zone])
    .attr('font-size', '11px')
    .attr('font-family', 'Courier New')
    .text(d => d.zone.toUpperCase() + ' ZONE');

  // ── Links ────────────────────────────────────────────────────────────
  const linkSel = svg.selectAll('.link')
    .data(links)
    .enter()
    .append('g')
    .attr('class', 'link');

  linkSel.append('line')
    .attr('x1', d => pos[d.source] ? pos[d.source].x : 0)
    .attr('y1', d => pos[d.source] ? pos[d.source].y : 0)
    .attr('x2', d => pos[d.target] ? pos[d.target].x : 0)
    .attr('y2', d => pos[d.target] ? pos[d.target].y : 0)
    .attr('stroke', '#4a4a6a')
    .attr('stroke-width', 2);

  linkSel.append('text')
    .attr('x', d => pos[d.source] && pos[d.target]
      ? (pos[d.source].x + pos[d.target].x) / 2 : 0)
    .attr('y', d => pos[d.source] && pos[d.target]
      ? (pos[d.source].y + pos[d.target].y) / 2 - 5 : 0)
    .attr('fill', '#555')
    .attr('font-size', '9px')
    .attr('text-anchor', 'middle')
    .attr('font-family', 'Courier New')
    .text(d => d.label);

  // ── Nodes ────────────────────────────────────────────────────────────
  const R = 22; // circle radius

  const nodeG = svg.selectAll('.node')
    .data(nodes)
    .enter()
    .append('g')
    .attr('class', 'node')
    .attr('transform', d => `translate(${pos[d.id] ? pos[d.id].x : 0},${pos[d.id] ? pos[d.id].y : 0})`)
    .style('cursor', 'pointer');

  // Circle
  nodeG.append('circle')
    .attr('r', R)
    .attr('fill',         d => zoneColor[d.zone] + '33')
    .attr('stroke',       d => zoneColor[d.zone])
    .attr('stroke-width', 2);

  // Icon text
  nodeG.append('text')
    .attr('text-anchor', 'middle')
    .attr('dy', '0.38em')
    .attr('font-size', d => d.type === 'router' ? '14px' : '12px')
    .attr('fill', d => zoneColor[d.zone])
    .text(d => d.type === 'router' ? '⬡' : d.type === 'server' ? '▪' : '◉');

  // Name label
  nodeG.append('text')
    .attr('text-anchor', 'middle')
    .attr('dy', R + 14 + 'px')
    .attr('fill', '#e0e0e0')
    .attr('font-size', '11px')
    .attr('font-family', 'Courier New')
    .attr('font-weight', 'bold')
    .text(d => d.name);

  // IP label
  nodeG.append('text')
    .attr('text-anchor', 'middle')
    .attr('dy', R + 26 + 'px')
    .attr('fill', '#666')
    .attr('font-size', '9px')
    .attr('font-family', 'Courier New')
    .text(d => d.ip);

  // Status badge (updated dynamically)
  nodeG.append('circle')
    .attr('class', d => 'status-dot status-dot-' + d.id)
    .attr('cx', R - 4)
    .attr('cy', -(R - 4))
    .attr('r', 6)
    .attr('fill', '#888')
    .attr('stroke', '#0a0a1a')
    .attr('stroke-width', 1.5);

  // Hover highlight
  nodeG
    .on('mouseover', function () {
      d3.select(this).select('circle').attr('stroke-width', 4);
    })
    .on('mouseout', function () {
      d3.select(this).select('circle').attr('stroke-width', 2);
    });
}

/**
 * Update status dots based on host status array from /api/hosts
 */
function updateTopologyStatus(hosts) {
  const colorMap = { UP: '#2ecc71', DOWN: '#e74c3c', UNKNOWN: '#888' };
  hosts.forEach(h => {
    d3.selectAll('.status-dot-' + h.id)
      .attr('fill', colorMap[h.status] || '#888');
  });
}
