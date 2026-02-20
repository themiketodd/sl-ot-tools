const { invoke } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;
const { open } = window.__TAURI__.dialog;

// ── State ──────────────────────────────────────────────────────────────────
let cy = null;
let companyData = null;
let repoPath = null;

// ── Node styling ───────────────────────────────────────────────────────────
const levelColors = {
  ceo:        { bg: '#1a2744', border: '#2a4a7a' },
  c_suite:    { bg: '#1e3054', border: '#2e5580' },
  vp:         { bg: '#243a64', border: '#3a6090' },
  director:   { bg: '#2a4474', border: '#4670a0' },
  manager:    { bg: '#304e84', border: '#5080b0' },
  ic:         { bg: '#365894', border: '#6090c0' },
  contractor: { bg: '#2a2d40', border: '#4a4d60' },
  unknown:    { bg: '#3a3520', border: '#6a6040' },
  external:   { bg: '#3a2a1a', border: '#8a6a3a' },
  workstream: { bg: '#1a3a2a', border: '#3a7a5a' },
};

function getNodeColor(node) {
  if (node.type === 'workstream') return levelColors.workstream;
  const level = (node.level || 'unknown').toLowerCase().replace(/[\s-]/g, '_');
  return levelColors[level] || levelColors.unknown;
}

// ── Build graph ────────────────────────────────────────────────────────────
function buildGraph(data) {
  const elements = [];
  const nodeIds = new Set();
  const orgChart = data.org_chart || {};

  function makeId(name) {
    return (name || '').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
  }

  function addPerson(person, section) {
    const id = makeId(person.name);
    if (!id || nodeIds.has(id)) return;
    nodeIds.add(id);

    const colors = getNodeColor(person);
    elements.push({
      group: 'nodes',
      data: {
        id,
        label: person.name,
        title: person.title || '',
        level: person.level || 'Unknown',
        org: person.org || '',
        email: person.email || '',
        section,
        bgColor: colors.bg,
        borderColor: colors.border,
        ...person,
      },
    });
  }

  for (const section of ['leadership', 'people', 'team']) {
    const people = orgChart[section] || [];
    for (const person of people) {
      addPerson(person, section);
    }
  }

  const ext = orgChart.external_ecosystem || {};
  const extEntries = Array.isArray(ext) ? ext : Object.values(ext);
  for (const org of extEntries) {
    const contacts = org.key_contacts || [];
    for (const person of contacts) {
      person.org = person.org || org.org || org.name;
      person.level = person.level || 'external';
      addPerson(person, 'external');
    }
  }

  for (const el of elements) {
    if (el.group !== 'nodes') continue;
    const d = el.data;
    if (d.reports_to) {
      const targetId = makeId(d.reports_to.replace(/\s*\(.*?\)\s*$/, ''));
      if (nodeIds.has(targetId) && targetId !== d.id) {
        elements.push({
          group: 'edges',
          data: { source: d.id, target: targetId, edgeType: 'reporting' },
        });
      }
    }
    if (d.dotted_to) {
      const targetId = makeId(d.dotted_to.replace(/\s*\(.*?\)\s*$/, ''));
      if (nodeIds.has(targetId) && targetId !== d.id) {
        elements.push({
          group: 'edges',
          data: { source: d.id, target: targetId, edgeType: 'dotted' },
        });
      }
    }
  }

  const registry = data.engagement_registry || {};
  const engagements = registry.engagements || {};
  for (const [engKey, eng] of Object.entries(engagements)) {
    const workstreams = eng.workstreams || {};
    for (const [wsKey, ws] of Object.entries(workstreams)) {
      const wsId = `ws_${engKey}_${wsKey}`;
      if (nodeIds.has(wsId)) continue;
      nodeIds.add(wsId);

      const colors = levelColors.workstream;
      elements.push({
        group: 'nodes',
        data: {
          id: wsId,
          label: ws.label || wsKey,
          type: 'workstream',
          engagement: eng.label || engKey,
          status: ws.status || 'unknown',
          bgColor: colors.bg,
          borderColor: colors.border,
        },
      });

      const raci = ws.raci || {};
      for (const role of ['responsible', 'accountable', 'consulted', 'informed']) {
        for (const name of raci[role] || []) {
          const personId = makeId(name);
          if (nodeIds.has(personId)) {
            elements.push({
              group: 'edges',
              data: { source: personId, target: wsId, edgeType: 'workstream', raciRole: role },
            });
          }
        }
      }
    }
  }

  return elements;
}

// ── Init Cytoscape ─────────────────────────────────────────────────────────
function initCytoscape(elements) {
  if (cy) cy.destroy();
  document.getElementById('landing').style.display = 'none';

  cy = cytoscape({
    container: document.getElementById('cy'),
    elements,
    style: [
      {
        selector: 'node',
        style: {
          'label': 'data(label)',
          'text-valign': 'center',
          'text-halign': 'center',
          'font-size': '10px',
          'color': '#e8eaf0',
          'text-wrap': 'wrap',
          'text-max-width': '80px',
          'background-color': 'data(bgColor)',
          'border-width': 2,
          'border-color': 'data(borderColor)',
          'width': 90,
          'height': 36,
          'shape': 'round-rectangle',
        },
      },
      {
        selector: 'node[type="workstream"]',
        style: { 'shape': 'round-rectangle', 'border-style': 'dashed' },
      },
      {
        selector: 'edge[edgeType="reporting"]',
        style: {
          'line-color': '#2a4a7a',
          'target-arrow-color': '#2a4a7a',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          'width': 1.5,
        },
      },
      {
        selector: 'edge[edgeType="dotted"]',
        style: {
          'line-color': '#4a4d60',
          'line-style': 'dashed',
          'target-arrow-color': '#4a4d60',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          'width': 1,
        },
      },
      {
        selector: 'edge[edgeType="workstream"]',
        style: {
          'line-color': '#3a7a5a',
          'line-style': 'dashed',
          'target-arrow-shape': 'none',
          'curve-style': 'bezier',
          'width': 1,
          'opacity': 0.6,
        },
      },
    ],
    layout: { name: 'preset' },
    wheelSensitivity: 0.3,
  });

  runLayout();
  cy.on('tap', 'node', (evt) => showDetail(evt.target.data()));
}

function runLayout() {
  if (!cy) return;
  try {
    cy.layout({
      name: 'fcose',
      animate: true,
      animationDuration: 500,
      nodeRepulsion: 8000,
      idealEdgeLength: 120,
      edgeElasticity: 0.1,
      gravity: 0.25,
      gravityRange: 2.0,
      nodeSeparation: 60,
    }).run();
  } catch {
    cy.layout({ name: 'cose', animate: true, animationDuration: 500 }).run();
  }
}

// ── Detail panel ───────────────────────────────────────────────────────────
function showDetail(data) {
  const panel = document.getElementById('detail-panel');
  panel.classList.add('open');

  if (data.type === 'workstream') {
    panel.innerHTML = `
      <button class="close-detail" onclick="closeDetail()">&times;</button>
      <h2 style="color: var(--accent-green)">${data.label}</h2>
      <div class="subtitle">${data.engagement || ''}</div>
      ${field('Status', data.status)}
      ${knowledgeSection(data)}
    `;
  } else {
    panel.innerHTML = `
      <button class="close-detail" onclick="closeDetail()">&times;</button>
      <h2>${data.label}</h2>
      <div class="subtitle">${data.title || ''}</div>
      ${field('Level', data.level)}
      ${field('Organization', data.org)}
      ${field('Email', data.email)}
      ${field('Reports to', data.reports_to)}
      ${field('Dotted to', data.dotted_to)}
      ${field('Location', data.location)}
      ${field('Start date', data.start_date)}
      ${field('Background', data.background)}
      ${field('Notes', data.notes)}
    `;
  }
}

function field(label, value) {
  if (!value) return '';
  return `<div class="detail-field"><label>${label}</label><div class="value">${value}</div></div>`;
}

function knowledgeSection(wsData) {
  if (!companyData || !companyData.knowledge) return '';
  const entries = companyData.knowledge.filter(
    (k) => wsData.label && wsData.label.includes(k.workstream)
  );
  if (!entries.length) return '';

  const typeColors = {
    DECISION: '#4a9eff', TECHNICAL: '#4ae08c', STATUS: '#e8a44a',
    ACTION: '#e05050', BLOCKER: '#e05050', TIMELINE: '#9a7ae0',
    BUDGET: '#e0a04a', RISK: '#e07070',
  };

  return `
    <div class="detail-field">
      <label>Knowledge Log</label>
      ${entries.slice(0, 20).map((k) => `
        <div style="margin: 6px 0; padding: 6px 8px; background: var(--bg-tertiary); border-radius: 4px; font-size: 12px;">
          <span style="color: ${typeColors[k.type] || '#999'}; font-weight: 600; font-size: 10px;">${k.type || 'NOTE'}</span>
          <span style="color: var(--text-secondary); font-size: 10px; margin-left: 8px;">${k.date}</span>
          <div style="margin-top: 2px;">${k.summary}</div>
          ${k.detail ? `<div style="color: var(--text-secondary); margin-top: 2px;">${k.detail}</div>` : ''}
        </div>
      `).join('')}
    </div>
  `;
}

window.closeDetail = function () {
  document.getElementById('detail-panel').classList.remove('open');
};

// ── Sidebar ────────────────────────────────────────────────────────────────
function buildSidebar(data) {
  const sidebar = document.getElementById('sidebar');
  let html = '';

  const orgChart = data.org_chart || {};
  const totalPeople =
    (orgChart.leadership || []).length +
    (orgChart.people || []).length +
    (orgChart.team || []).length;
  html += `<h3>People</h3>`;
  html += `<div class="sidebar-item">${data.company_config?.company || 'Company'} <span class="badge">${totalPeople}</span></div>`;

  const registry = data.engagement_registry || {};
  const engagements = registry.engagements || {};
  if (Object.keys(engagements).length) {
    html += `<h3>Engagements</h3>`;
    for (const [key, eng] of Object.entries(engagements)) {
      html += `<div class="sidebar-item">
        <span class="status-dot status-${eng.status === 'active' ? 'active' : 'inactive'}"></span>
        ${eng.label || key}
      </div>`;
      const workstreams = eng.workstreams || {};
      for (const [wsKey, ws] of Object.entries(workstreams)) {
        html += `<div class="sidebar-item" style="padding-left: 24px; font-size: 12px;">
          <span class="status-dot status-${ws.status === 'active' ? 'active' : 'inactive'}"></span>
          ${ws.label || wsKey}
        </div>`;
      }
    }
  }

  const knowledge = data.knowledge || [];
  if (knowledge.length) {
    html += `<h3>Knowledge</h3>`;
    html += `<div class="sidebar-item">Entries <span class="badge">${knowledge.length}</span></div>`;
  }

  sidebar.innerHTML = html;
}

// ── Terminal ───────────────────────────────────────────────────────────────
let term = null;
let termLineBuf = '';

function initTerminal() {
  const container = document.getElementById('terminal-container');
  term = new Terminal({
    fontFamily: 'JetBrains Mono, Consolas, monospace',
    fontSize: 13,
    theme: {
      background: '#0c0e1a',
      foreground: '#e8eaf0',
      cursor: '#4a9eff',
      selectionBackground: '#2a4a7a',
    },
    cursorBlink: true,
    convertEol: true,
  });

  const fitAddon = new FitAddon.FitAddon();
  term.loadAddon(fitAddon);
  term.open(container);
  fitAddon.fit();
  window.addEventListener('resize', () => fitAddon.fit());

  // Listen for output from the Rust backend
  listen('terminal-output', (event) => {
    if (term && event.payload) {
      term.write(event.payload);
    }
  });

  // Send keystrokes to the backend
  term.onData((data) => {
    invoke('write_terminal', { data }).catch(() => {});
  });

  // Auto-spawn the terminal process
  term.writeln('\x1b[90mConnecting to shell...\x1b[0m\r\n');
  invoke('spawn_terminal').then(() => {
    // Terminal spawned — output will arrive via events
  }).catch((err) => {
    term.writeln(`\x1b[31mFailed to start shell: ${err}\x1b[0m`);
    term.writeln('\x1b[90mThis feature requires WSL on Windows.\x1b[0m');
  });
}

// ── Resize handle ──────────────────────────────────────────────────────────
function initResizeHandle() {
  const handle = document.getElementById('resize-handle');
  const termPane = document.getElementById('terminal-pane');
  let startY, startHeight;

  handle.addEventListener('mousedown', (e) => {
    startY = e.clientY;
    startHeight = termPane.offsetHeight;
    document.addEventListener('mousemove', onDrag);
    document.addEventListener('mouseup', onRelease);
    e.preventDefault();
  });

  function onDrag(e) {
    const delta = startY - e.clientY;
    termPane.style.height = Math.max(100, startHeight + delta) + 'px';
  }

  function onRelease() {
    document.removeEventListener('mousemove', onDrag);
    document.removeEventListener('mouseup', onRelease);
  }

  document.getElementById('btn-toggle-terminal').addEventListener('click', () => {
    const isHidden = termPane.style.display === 'none';
    termPane.style.display = isHidden ? 'flex' : 'none';
    handle.style.display = isHidden ? 'block' : 'none';
  });
}

// ── Open repo ──────────────────────────────────────────────────────────────
async function openRepo(path) {
  try {
    companyData = await invoke('read_company_data', { repoPath: path });
    repoPath = path;

    const companyName = companyData.company_config?.company || 'Company';
    document.getElementById('app-title').textContent = `${companyName.toUpperCase()} — OT VIEWER`;

    buildSidebar(companyData);
    const elements = buildGraph(companyData);
    initCytoscape(elements);
  } catch (err) {
    alert('Error loading repo: ' + err);
  }
}

async function promptOpenRepo() {
  const selected = await open({ directory: true, title: 'Select Company Repo' });
  if (selected) openRepo(selected);
}

// ── Test: read local JSON ──────────────────────────────────────────────────
async function testLocalJson() {
  try {
    const data = await invoke('read_local_json', { filename: 'test-data.json' });
    const msg = `Local file read OK!\n\n${JSON.stringify(data, null, 2)}`;
    alert(msg);
    console.log('test-data.json:', data);
  } catch (err) {
    alert('Failed to read local file: ' + err);
  }
}

// ── Init ───────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  document.getElementById('btn-open-repo').addEventListener('click', promptOpenRepo);
  document.getElementById('btn-landing-open').addEventListener('click', promptOpenRepo);
  document.getElementById('btn-test-local').addEventListener('click', testLocalJson);
  document.getElementById('btn-fit').addEventListener('click', () => cy?.fit());
  document.getElementById('btn-relayout').addEventListener('click', runLayout);

  initTerminal();
  initResizeHandle();

  const argPath = await invoke('get_repo_from_args');
  if (argPath) {
    openRepo(argPath);
  }
});
