import { dependencyGraph, filterIssues, resolveSource, safeLink, statuses } from './model.mjs';

const $ = id => document.getElementById(id);
const labels = Object.fromEntries(statuses);
const palette = ['#55a68c', '#8a76bd', '#6e66d0', '#bd8a59', '#578faf'];
const narrow = window.matchMedia('(max-width: 700px)');
const view = { query: '', epic: '', status: '', mode: narrow.matches ? 'list' : 'board', history: false };
let chosenView = false;
const campaignThreads = new Map();
const epicCards = new Map();
let graphScale = 1, graphKey = '', currentGraph = null;
let data = null, busy = false, selected = null, lastTrigger = null, backStack = [], lastSuccess = null;
const dialog = $('detail');
const resultsDialog = $('epic-results-dialog');
let resultsEpic = null, resultsSignature = null;

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = String(text);
  return node;
}
function button(className, text, action) {
  const node = el('button', className, text);
  node.type = 'button';
  node.addEventListener('click', action);
  return node;
}
function epicFor(issue) { return data.epics.find(epic => epic.id === issue.epic_id); }
function color(epic) { return palette[Math.max(0, data.epics.indexOf(epic)) % palette.length]; }
function dot(className = 'status-dot') { return el('span', className); }
function pill(status) {
  const node = el('span', `pill state-${status}`);
  node.append(dot(), document.createTextNode(labels[status] || 'Needs attention'));
  return node;
}
function meter(value, name, className = 'track') {
  const node = el('div', className), bar = el('span');
  const finite = Number.isFinite(value);
  bar.style.width = `${finite ? Math.min(100, Math.max(0, value)) : 0}%`;
  node.setAttribute('role', 'progressbar');
  node.setAttribute('aria-label', name);
  node.setAttribute('aria-valuemin', '0'); node.setAttribute('aria-valuemax', '100');
  if (finite) node.setAttribute('aria-valuenow', Math.min(100, Math.max(0, value)).toFixed(1));
  else node.setAttribute('aria-valuetext', 'Unavailable');
  node.append(bar); return node;
}
function owner(name) {
  const node = el('span', 'owner');
  const assigned = !['unassigned', 'none', '—', '-'].includes(name.toLowerCase());
  node.append(el('span', 'avatar', assigned ? name.slice(0, 1).toUpperCase() : '–'),
    document.createTextNode(assigned ? name : 'Unassigned'));
  return node;
}
function changeEpic(id) {
  view.epic = view.epic === id ? '' : id;
  $('epic-filter').value = view.epic;
  renderEpics(); renderTasks();
}

function renderEpics() {
  $('nav-total').textContent = data.issues.length;
  $('epic-total').textContent = data.epics.length;
  $('workspace-summary').textContent = `${data.issues.length} issues · ${data.counts.resolved} resolved`;
  $('overview').classList.toggle('selected', !view.epic);
  const nav = [], cards = [];
  for (const epic of data.epics) {
    const navButton = button(`epic-nav-button${view.epic === epic.id ? ' selected' : ''}`, '', () => changeEpic(epic.id));
    navButton.style.setProperty('--epic-color', color(epic));
    navButton.append(dot('epic-dot'), el('span', '', epic.title), el('span', 'nav-ratio', `${epic.resolved}/${epic.total}`));
    nav.push(navButton);
    let nodes = epicCards.get(epic.id);
    if (!nodes) {
      const card = el('article', 'epic-card');
      const filter = button('epic-filter-button', '', () => changeEpic(epic.id));
      const results = button('epic-results-button', 'Results & conclusions ↗', () => openResults(epic.id));
      results.setAttribute('aria-haspopup', 'dialog');
      results.setAttribute('aria-controls', 'epic-results-dialog');
      card.append(filter, results);
      nodes = { card, filter, results };
      epicCards.set(epic.id, nodes);
    }
    const { card, filter } = nodes;
    card.classList.toggle('selected', view.epic === epic.id);
    filter.setAttribute('aria-label', `Filter epic: ${epic.title}`);
    filter.setAttribute('aria-pressed', String(view.epic === epic.id));
    card.style.setProperty('--epic-color', color(epic));
    const top = el('div', 'epic-card-top');
    const done = epic.total > 0 && epic.resolved === epic.total;
    top.append(el('span', 'epic-symbol', done ? '✓' : '◇'), el('span', `epic-state${done ? ' done' : ''}`, done ? 'Resolved' : 'Open'));
    const caption = el('div', 'progress-caption');
    const percent = epic.total ? Math.round(100 * epic.resolved / epic.total) : null;
    caption.append(el('span', '', `${epic.resolved} of ${epic.total} resolved`), el('strong', '', percent === null ? '—' : `${percent}%`));
    const bottom = el('div', 'epic-bottom');
    if (done) bottom.append(el('span', '', 'Completed history'));
    else {
      bottom.append(el('span', '', `${epic.counts.in_progress} in progress`));
      if (epic.counts.blocked) bottom.append(el('span', 'blocked-number', `${epic.counts.blocked} blocked`));
    }
    filter.replaceChildren(top, el('h3', '', epic.title), caption, meter(percent, `${epic.title} issue completion`), bottom);
    cards.push(card);
  }
  $('epic-nav').replaceChildren(...nav);
  const root = $('epic-cards');
  for (const child of [...root.children]) if (!cards.includes(child)) child.remove();
  cards.forEach((card, index) => {
    if (root.children[index] !== card) root.insertBefore(card, root.children[index] || null);
  });
  for (const id of epicCards.keys()) if (!data.epics.some(epic => epic.id === id)) epicCards.delete(id);
  const current = [...$('epic-filter').options].slice(1).map(option => `${option.value}:${option.text}`).join('|');
  if (current !== data.epics.map(epic => `${epic.id}:${epic.title}`).join('|')) {
    const first = el('option', '', 'All epics'); first.value = '';
    $('epic-filter').replaceChildren(first, ...data.epics.map(epic => {
      const option = el('option', '', epic.title); option.value = epic.id; return option;
    }));
  }
  $('epic-filter').value = view.epic;
}

function renderResults() {
  const epic = data.epics.find(item => item.id === resultsEpic);
  if (!epic) { if (resultsDialog.open) resultsDialog.close(); return; }
  $('epic-results-title').textContent = epic.title;
  const signature = JSON.stringify(epic.summary);
  if (signature !== resultsSignature) {
    const body = $('epic-results-body'), scroll = body.scrollTop;
    body.replaceChildren(epic.summary
      ? markdown(epic.summary.body, epic.summary.source)
      : el('p', '', 'No results summary recorded for this epic yet.'));
    body.scrollTop = scroll;
    resultsSignature = signature;
  }
}
function openResults(id) {
  resultsEpic = id; resultsSignature = null;
  renderResults();
  $('epic-results-body').scrollTop = 0;
  if (!resultsDialog.open) resultsDialog.showModal();
  $('epic-results-close').focus();
}
$('epic-results-close').addEventListener('click', () => resultsDialog.close());
resultsDialog.addEventListener('close', () => {
  epicCards.get(resultsEpic)?.results.focus();
  resultsEpic = null; resultsSignature = null;
});
let backdropStart = false;
function outsideResults(event) {
  const rect = resultsDialog.getBoundingClientRect();
  return event.target === resultsDialog && (event.clientX < rect.left || event.clientX > rect.right
    || event.clientY < rect.top || event.clientY > rect.bottom);
}
resultsDialog.addEventListener('pointerdown', event => { backdropStart = outsideResults(event); });
resultsDialog.addEventListener('click', event => {
  if (backdropStart && outsideResults(event)) resultsDialog.close();
  backdropStart = false;
});

function duration(seconds) {
  if (!Number.isFinite(seconds)) return '—';
  const minutes = Math.floor(seconds / 60);
  return minutes >= 60 ? `${Math.floor(minutes / 60)}h ${String(minutes % 60).padStart(2, '0')}m` : `${minutes}m`;
}
function campaignThread(campaign) {
  const key = campaign.source || 'unavailable';
  let nodes = campaignThreads.get(key);
  if (!nodes) {
    const details = el('details', 'campaign-thread');
    details.open = campaign.status === 'running';
    const summary = el('summary'), label = el('span', '', 'Campaign thread');
    const count = el('span', 'thread-count');
    summary.append(label, count, el('span', 'thread-chevron', '⌄'));
    const body = el('div', 'thread-body');
    details.append(summary, body);
    nodes = { details, summary, count, body };
    campaignThreads.set(key, nodes);
  }
  const entries = campaign.activity || [];
  nodes.scrollTop = nodes.body.querySelector('.thread-timeline')?.scrollTop || 0;
  nodes.count.textContent = `${entries.length} update${entries.length === 1 ? '' : 's'}`;
  const latest = el('div', 'thread-latest');
  latest.append(el('span', 'thread-eyebrow', 'Latest recorded application'));
  if (campaign.last_case) {
    const outcome = campaign.last_status === 'success' ? 'Succeeded' : campaign.last_status === 'time_limit' ? 'Reached its time limit' : campaign.last_status === 'untested' ? 'Not attempted within the campaign budget' : campaign.last_status || 'Outcome unavailable';
    latest.append(el('p', '', `${campaign.last_case} · ${campaign.last_method || 'Unknown method'} — ${outcome}.`));
  } else latest.append(el('p', '', 'No completed application has been recorded yet.'));
  latest.append(el('small', '', 'This is a recorded outcome, not a live execution trace; the source does not identify the method currently executing.'));
  const timeline = el('ol', 'thread-timeline');
  for (const entry of [...entries].reverse()) {
    const item = el('li'), stamp = el('time');
    stamp.dateTime = entry.at;
    stamp.title = new Date(entry.at).toLocaleString();
    stamp.textContent = new Date(entry.at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    item.append(stamp, el('h3', '', entry.title), el('p', '', entry.detail));
    const explanation = el('dl', 'thread-narrative');
    for (const [key, label] of [['testing', 'Testing'], ['why', 'Why'], ['observed', 'Observed'], ['meaning', 'Meaning so far']]) {
      if (entry[key]) explanation.append(el('dt', `narrative-${key}`, label), el('dd', '', entry[key]));
    }
    if (explanation.children.length) item.append(explanation);
    if (entry.next) {
      const next = el('p', 'thread-next');
      next.append(el('strong', '', 'Next: '), document.createTextNode(entry.next));
      item.append(next);
    }
    timeline.append(item);
  }
  if (!entries.length) timeline.append(el('li', 'thread-empty', 'No explanatory updates recorded yet. Progress above still refreshes automatically.'));
  nodes.body.replaceChildren(latest, timeline);
  nodes.timeline = timeline;
  return nodes;
}
function renderCampaign() {
  const root = $('campaign'), campaign = data.campaign;
  root.hidden = !campaign;
  if (!campaign) return;
  const summary = el('div'), heading = el('div', 'campaign-heading');
  const status = campaign.status === 'running' ? 'Running' : campaign.status === 'awaiting_decision' ? 'Awaiting decision' : campaign.status === 'prepared' ? 'Prepared' : campaign.status === 'complete' ? 'Complete' : campaign.status === 'interrupted' ? 'Interrupted' : campaign.status === 'incomplete' ? 'Incomplete' : 'Unavailable';
  const badge = el('span', `live-tag${campaign.stale || campaign.status === 'interrupted' ? ' warning' : ''}`, campaign.stale ? 'Update stale' : status);
  badge.title = `Status recorded in the campaign manifest: ${campaign.status}. This is not independent process-health verification.`;
  heading.append(el('h2', '', 'Research campaign'), badge);
  const context = campaign.last_case ? `${campaign.last_case} · ${campaign.last_method || '—'}` : 'Waiting for recorded progress';
  summary.append(heading, el('div', 'campaign-context', context));
  const progress = el('div', 'campaign-progress'), caption = el('div', 'progress-caption');
  const percent = Number.isFinite(campaign.budget_percent) ? `${campaign.budget_percent.toFixed(1)}%` : '—';
  caption.append(el('span', '', 'Time budget used'), el('strong', '', percent));
  progress.append(caption, meter(campaign.budget_percent, 'Research time budget used'),
    el('div', 'campaign-note', `${duration(campaign.elapsed_seconds)} elapsed / ${duration(campaign.budget_seconds)} cap`));
  const counts = el('div', 'campaign-count');
  counts.append(el('strong', '', campaign.attempted ?? '—'), el('span', '', `/ ${campaign.planned ?? '—'}`),
    el('small', '', 'applications attempted'));
  const age = Number.isFinite(campaign.age_seconds) ? `${Math.floor(campaign.age_seconds)}s since last record` : 'Source update time unavailable';
  counts.append(el('small', campaign.stale ? 'warning' : '', age));
  if (campaign.warnings?.length) summary.append(el('div', 'campaign-note warning', campaign.warnings.join(' · ')));
  const thread = campaignThread(campaign);
  const restoreFocus = document.activeElement === thread.summary;
  if (thread.details.parentElement === root) {
    // Keep native details attached during polling so its open content retains
    // layout and reading position while the progress cells are replaced.
    const previous = [...root.children].filter(node => node !== thread.details);
    thread.details.before(summary, progress, counts);
    previous.forEach(node => node.remove());
  } else root.replaceChildren(summary, progress, counts, thread.details);
  thread.timeline.scrollTop = thread.scrollTop;
  if (restoreFocus) thread.summary.focus({ preventScroll: true });
}

function issueButton(issue, className = 'task-card') {
  const epic = epicFor(issue);
  const node = button(`${className} state-${issue.status}`, '', () => openIssue(issue.id));
  node.dataset.issue = issue.id;
  node.style.setProperty('--epic-color', color(epic));
  if (className === 'issue-link') { node.textContent = issue.title; return node; }
  const top = el('div', 'task-top'); top.append(dot('epic-dot'), document.createTextNode(`${issue.type} · ${issue.mode}`));
  const footer = el('div', 'task-footer');
  footer.append(owner(issue.assignee));
  if (issue.blockers.length) footer.append(el('span', 'dependency-count', `${issue.blockers.length} dependenc${issue.blockers.length === 1 ? 'y' : 'ies'}`));
  else footer.append(el('span', '', issue.status === 'resolved' ? 'Completed' : 'No blockers'));
  node.append(top, el('span', 'task-title', issue.title), el('span', 'task-epic', epic?.title || 'Unknown epic'), footer);
  return node;
}
function svg(tag, attributes = {}) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
  return node;
}
function scaleGraph() {
  if (!currentGraph) return;
  $('graph-canvas').style.transform = `scale(${graphScale})`;
  $('graph-size').style.width = `${currentGraph.width * graphScale}px`;
  $('graph-size').style.height = `${currentGraph.height * graphScale}px`;
  $('graph-viewport').style.height = `${Math.max(narrow.matches ? 320 : 360, Math.min(narrow.matches ? 440 : 620, currentGraph.height * graphScale + 32))}px`;
  $('graph-scale').value = `${Math.round(graphScale * 100)}%`;
  $('graph-zoom-out').disabled = graphScale <= .2;
  $('graph-zoom-in').disabled = graphScale >= 1.6;
}
function renderGraph(rows) {
  const viewport = $('graph-viewport'), canvas = $('graph-canvas');
  const key = JSON.stringify([view.query, view.epic, view.status, rows.map(row => row.id)]);
  const scroll = key === graphKey ? [viewport.scrollLeft, viewport.scrollTop] : [0, 0];
  graphKey = key;
  const focused = document.activeElement?.classList.contains('graph-node') ? document.activeElement.dataset.issue : null;
  const graph = dependencyGraph(data.issues, rows); currentGraph = graph;
  canvas.style.width = `${graph.width}px`; canvas.style.height = `${graph.height}px`;
  const paths = svg('svg', {width:graph.width, height:graph.height, 'aria-hidden':'true', class:'graph-connections'});
  const defs = svg('defs');
  for (const [id, fill] of [['graph-arrow', '#b6b4c9'], ['graph-cycle-arrow', '#c57979']]) {
    const marker = svg('marker', {id, viewBox:'0 0 10 10', refX:'9', refY:'5', markerWidth:'7', markerHeight:'7', orient:'auto-start-reverse'});
    marker.append(svg('path', {d:'M 0 0 L 10 5 L 0 10 z', fill})); defs.append(marker);
  }
  paths.append(defs);
  const positions = new Map(graph.nodes.map(node => [node.issue.id, node]));
  for (const edge of graph.edges) {
    const first = positions.get(edge.source), second = positions.get(edge.target);
    let startX = first.x + first.width, endX = second.x;
    let startY = first.y + first.height / 2, endY = second.y + second.height / 2, path;
    if (edge.via) {
      path = edge.via.map(([x,y], index) => `${index ? 'L' : 'M'}${x},${y}`).join(' ');
    } else if (first === second) {
      endX = startX; startY -= 24; endY += 24;
      path = `M${startX},${startY} C${startX+44},${startY-20} ${endX+44},${endY+20} ${endX},${endY}`;
    } else if (edge.cycle) {
      startX = first.x; endX = second.x;
      path = `M${startX},${startY} C${startX-40},${startY} ${endX-40},${endY} ${endX},${endY}`;
    } else {
      const middle = (startX + endX) / 2;
      path = `M${startX},${startY} C${middle},${startY} ${middle},${endY} ${endX},${endY}`;
    }
    paths.append(svg('path', {d:path, class:`graph-edge${edge.cycle ? ' cycle' : ''}`, 'data-source':edge.source, 'data-target':edge.target,
      'marker-end':`url(#${edge.cycle ? 'graph-cycle-arrow' : 'graph-arrow'})`}));
  }
  const cards = graph.nodes.map(node => {
    const issue = node.issue, epic = epicFor(issue);
    const card = button(`graph-node state-${issue.status}${node.context ? ' context' : ''}`, '', () => openIssue(issue.id));
    card.dataset.issue = issue.id; card.style.left = `${node.x}px`; card.style.top = `${node.y}px`;
    card.style.width = `${node.width}px`; card.style.height = `${node.height}px`;
    card.style.setProperty('--epic-color', color(epic)); card.title = issue.title;
    const top = el('div', 'graph-node-top');
    top.append(pill(issue.status));
    if (node.cycle) top.append(el('span', 'graph-cycle-label', 'Cycle'));
    else if (node.context) top.append(el('span', 'graph-context-label', 'Prerequisite'));
    const group = el('span', 'graph-epic'); group.append(dot('epic-dot'), document.createTextNode(epic?.title || 'Unknown epic'));
    card.append(top, el('span', 'graph-title', issue.title), group);
    const highlight = active => {
      for (const edge of paths.querySelectorAll('.graph-edge')) edge.classList.toggle('highlight', active && [edge.dataset.source, edge.dataset.target].includes(issue.id));
    };
    card.addEventListener('mouseenter', () => highlight(true)); card.addEventListener('mouseleave', () => highlight(false));
    card.addEventListener('focus', () => highlight(true)); card.addEventListener('blur', () => highlight(false));
    return card;
  });
  canvas.replaceChildren(paths, ...cards);
  const context = graph.nodes.filter(node => node.context).length, cycles = graph.nodes.filter(node => node.cycle).length;
  $('graph-caption').textContent = `${rows.length} matching task${rows.length === 1 ? '' : 's'} · ${context} prerequisite${context === 1 ? '' : 's'} for context · ${graph.edges.length} connection${graph.edges.length === 1 ? '' : 's'}${cycles ? ' · Cycles highlighted: inspect source warnings' : ''}`;
  scaleGraph(); viewport.scrollLeft = scroll[0]; viewport.scrollTop = scroll[1];
  if (focused) cards.find(card => card.dataset.issue === focused)?.focus({preventScroll:true});
}
function renderTasks() {
  const rows = filterIssues(data.issues, view);
  $('view-count').textContent = rows.length;
  const closed = rows.filter(row => row.status === 'resolved').length;
  $('view-summary').textContent = `${rows.length - closed} active · ${closed} resolved in this view`;
  $('clear').hidden = !(view.query || view.epic || view.status);
  $('empty').hidden = rows.length !== 0;
  $('board').hidden = view.mode !== 'board' || !rows.length;
  $('list').hidden = view.mode !== 'list' || !rows.length;
  $('dependency').hidden = view.mode !== 'dependency' || !rows.length;
  $('board-view').setAttribute('aria-pressed', view.mode === 'board');
  $('list-view').setAttribute('aria-pressed', view.mode === 'list');
  $('dependency-view').setAttribute('aria-pressed', view.mode === 'dependency');
  $('issues-heading').textContent = view.mode === 'dependency' ? 'Issue dependencies' : view.mode === 'board' ? 'Issue board' : 'Issue list';
  const columns = [];
  for (const [status, title] of statuses) {
    const group = rows.filter(row => row.status === status);
    if ((view.status && status !== view.status) || (status === 'attention' && !group.length)) continue;
    const column = el('section', `column state-${status}`);
    column.setAttribute('aria-label', `${title} issues`);
    const head = el('div', 'column-head');
    head.append(dot(), el('span', '', title), el('span', 'column-count', group.length));
    column.append(head);
    if (status === 'resolved' && group.length && !view.history && !view.status && !view.query && !view.epic) {
      const history = el('div', 'history-summary');
      history.append(el('strong', '', group.length), el('p', '', 'Resolved issues, with their evidence.'),
        button('', 'Explore completed work', () => { view.history = true; renderTasks(); }));
      column.append(history);
    } else {
      column.append(...group.map(issue => issueButton(issue)));
      if (!group.length) column.append(el('div', 'empty-column', status === 'ready' ? 'Nothing ready right now.' : 'No issues in this status.'));
      if (status === 'resolved' && group.length && view.history && !view.epic && !view.query && !view.status) {
        column.append(button('hide-history', 'Collapse completed history', () => { view.history = false; renderTasks(); }));
      }
    }
    columns.push(column);
  }
  $('board').classList.toggle('has-attention', columns.length > 4);
  $('board').replaceChildren(...columns);
  if (view.mode === 'list') {
    const table = el('table'), header = el('tr');
    for (const name of ['Issue', 'Epic', 'Status', 'Assignee', 'Dependencies']) header.append(el('th', '', name));
    const thead = el('thead'); thead.append(header);
    const tbody = el('tbody');
    for (const issue of rows) {
      const row = el('tr'), title = el('td'), status = el('td'), who = el('td');
      title.append(issueButton(issue, 'issue-link')); status.append(pill(issue.status)); who.append(owner(issue.assignee));
      row.append(title, el('td', 'muted', epicFor(issue)?.title || 'Unknown'), status, who, el('td', '', issue.blockers.length || '—'));
      tbody.append(row);
    }
    table.append(thead, tbody); $('list').replaceChildren(table);
  }
  if (view.mode === 'dependency') renderGraph(rows);
}

function inline(text, parent, source) {
  const tokens = /\[([^\]]+)\]\(([^)]+)\)|`([^`]+)`|\*\*([^*]+)\*\*/g;
  let offset = 0;
  for (const match of text.matchAll(tokens)) {
    parent.append(document.createTextNode(text.slice(offset, match.index)));
    if (match[1] !== undefined) {
      const safe = safeLink(match[2]);
      if (!safe) parent.append(document.createTextNode(match[1]));
      else {
        const link = el('a', '', match[1]);
        link.rel = 'noopener noreferrer';
        if (/^https?:/i.test(safe)) { link.href = safe; link.target = '_blank'; }
        else {
          const path = resolveSource(safe, source);
          const target = data.issues.find(issue => issue.id === path);
          if (target) {
            link.href = '#'; link.addEventListener('click', event => { event.preventDefault(); openIssue(target.id, true); });
          } else if (path !== null) { link.href = `/api/source?path=${encodeURIComponent(path)}`; link.target = '_blank'; }
        }
        parent.append(link);
      }
    } else parent.append(el(match[3] !== undefined ? 'code' : 'strong', '', match[3] ?? match[4]));
    offset = match.index + match[0].length;
  }
  parent.append(document.createTextNode(text.slice(offset)));
}
function markdown(text, source) {
  const body = el('div');
  const start = text.search(/^##\s/m);
  const content = start >= 0 ? text.slice(start) : text;
  let list = null, code = null;
  for (const line of content.split('\n')) {
    if (line.startsWith('```')) {
      if (code) { body.append(code); code = null; }
      else code = el('pre');
      list = null; continue;
    }
    if (code) { code.append(document.createTextNode(line + '\n')); continue; }
    if (!line.trim()) { list = null; continue; }
    const heading = line.match(/^(#{1,6})\s+(.+)/);
    if (heading) { body.append(el('h3', '', heading[2])); list = null; continue; }
    const item = line.match(/^\s*[-*]\s+(.+)/);
    if (item) {
      if (!list) { list = el('ul'); body.append(list); }
      const li = el('li'); inline(item[1], li, source); list.append(li);
    } else { const p = el('p'); inline(line, p, source); body.append(p); list = null; }
  }
  if (code) body.append(code);
  return body;
}
function renderDetails() {
  const issue = data.issues.find(row => row.id === selected);
  if (!issue) { if (dialog.open) dialog.close(); return; }
  const scroller = dialog.querySelector('.detail-scroll'), scroll = scroller.scrollTop;
  $('detail-epic').textContent = epicFor(issue)?.title || 'Unknown epic';
  $('detail-title').textContent = issue.title;
  $('detail-status').replaceChildren(pill(issue.status));
  const facts = [['Assignee', issue.assignee], ['Type', issue.type], ['Mode', issue.mode]];
  $('detail-facts').replaceChildren(...facts.map(([title, value]) => {
    const cell = el('div'); cell.append(el('small', '', title), document.createTextNode(value)); return cell;
  }));
  const deps = $('detail-dependencies'); deps.replaceChildren(); deps.hidden = !issue.blockers.length;
  if (issue.blockers.length) {
    deps.append(el('h3', '', 'Depends on'));
    for (const identity of issue.blockers) {
      const blocker = data.issues.find(row => row.id === identity);
      const link = button(`dependency-link state-${blocker.status}`, '', () => openIssue(identity, true));
      link.append(dot(), document.createTextNode(blocker.title)); deps.append(link);
    }
  }
  $('detail-warnings').hidden = !issue.warnings.length;
  $('detail-warnings').textContent = issue.warnings.join(' · ');
  $('detail-body').replaceChildren(markdown(issue.body, issue.source));
  $('detail-path').textContent = issue.source;
  $('detail-source').textContent = issue.body;
  $('detail-back').hidden = !backStack.length;
  scroller.scrollTop = scroll;
}
function openIssue(id, dependency = false) {
  if (id === selected && dialog.open) return;
  if (dependency && selected) backStack.push(selected);
  else { backStack = []; lastTrigger = id; }
  selected = id;
  renderDetails(); dialog.querySelector('.detail-scroll').scrollTop = 0;
  if (!dialog.open) dialog.showModal();
  $('detail-close').focus();
}
dialog.addEventListener('close', () => {
  selected = null; backStack = [];
  const trigger = [...document.querySelectorAll('[data-issue]')]
    .find(node => node.dataset.issue === lastTrigger && node.getClientRects().length > 0);
  if (trigger) trigger.focus();
});
$('detail-close').addEventListener('click', () => dialog.close());
$('detail-back').addEventListener('click', () => { selected = backStack.pop(); renderDetails(); });

function reset() {
  view.query = ''; view.epic = ''; view.status = '';
  $('search').value = ''; $('epic-filter').value = ''; $('status-filter').value = '';
  renderEpics(); renderTasks();
}
$('overview').addEventListener('click', reset);
$('clear').addEventListener('click', reset); $('empty-reset').addEventListener('click', reset);
$('search').addEventListener('input', event => { view.query = event.target.value; renderTasks(); });
$('epic-filter').addEventListener('change', event => { view.epic = event.target.value; renderEpics(); renderTasks(); });
$('status-filter').addEventListener('change', event => { view.status = event.target.value; renderTasks(); });
$('board-view').addEventListener('click', () => { chosenView = true; view.mode = 'board'; renderTasks(); });
$('list-view').addEventListener('click', () => { chosenView = true; view.mode = 'list'; renderTasks(); });
$('dependency-view').addEventListener('click', () => { chosenView = true; view.mode = 'dependency'; renderTasks(); });
for (const [id, delta] of [['graph-zoom-out', -.2], ['graph-zoom-in', .2]]) {
  $(id).addEventListener('click', () => { graphScale = Math.max(.2, Math.min(1.6, Math.round((graphScale + delta) * 10) / 10)); scaleGraph(); });
}
$('graph-reset').addEventListener('click', () => { graphScale = 1; scaleGraph(); });
$('graph-fit').addEventListener('click', () => {
  if (!currentGraph) return;
  graphScale = Math.max(.2, Math.min(1, ($('graph-viewport').clientWidth - 4) / currentGraph.width, ($('graph-viewport').clientHeight - 4) / currentGraph.height));
  scaleGraph(); $('graph-viewport').scrollTo(0, 0);
});
narrow.addEventListener('change', event => {
  if (!chosenView) { view.mode = event.matches ? 'list' : 'board'; if (data) renderTasks(); }
  else if (view.mode === 'dependency') scaleGraph();
});
document.addEventListener('keydown', event => {
  if (event.key === '/' && !dialog.open && !resultsDialog.open && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) {
    event.preventDefault(); $('search').focus();
  }
});

async function refresh() {
  if (busy) return;
  busy = true; $('refresh').disabled = true;
  try {
    const response = await fetch('/api/state', {cache: 'no-store', signal: AbortSignal.timeout(8000)});
    if (!response.ok) throw new Error(`Server returned ${response.status}`);
    data = await response.json(); lastSuccess = Date.now();
    if (!data.epics.some(epic => epic.id === view.epic)) view.epic = '';
    $('freshness').classList.remove('disconnected'); $('freshness').textContent = 'Live from Markdown';
    const warnings = [...data.warnings];
    const issueWarnings = data.issues.filter(issue => issue.warnings.length).length;
    if (issueWarnings) warnings.push(`${issueWarnings} issue${issueWarnings === 1 ? ' has' : 's have'} source warnings. Inspect details before acting.`);
    $('notice').hidden = !warnings.length; $('notice').textContent = warnings.join(' · ');
    renderEpics(); renderCampaign(); renderTasks();
    if (selected) renderDetails();
    if (resultsEpic) renderResults();
    $('footer-counts').textContent = `${data.epics.length} epics · ${data.issues.length} issues · ${data.counts.resolved} resolved`;
  } catch (error) {
    $('freshness').classList.add('disconnected'); $('freshness').textContent = 'Connection interrupted';
    $('notice').hidden = false;
    $('notice').textContent = data ? `Connection interrupted. Showing the last successful snapshot from ${new Date(lastSuccess).toLocaleTimeString()}. Refresh to retry.` : `Unable to load the workspace. Check that the local server is running. ${error.message}`;
  } finally { busy = false; $('refresh').disabled = false; }
}
$('refresh').addEventListener('click', refresh);
refresh(); setInterval(refresh, 10000);
