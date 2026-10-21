export const statuses = [
  ['ready', 'Ready'], ['in_progress', 'In progress'], ['blocked', 'Blocked'],
  ['resolved', 'Resolved'], ['attention', 'Needs attention'],
];

export function filterIssues(issues, { query = '', epic = '', status = '' } = {}) {
  const terms = query.toLowerCase().trim().split(/\s+/).filter(Boolean);
  return issues.filter(issue => (!epic || issue.epic_id === epic)
    && (!status || issue.status === status)
    && terms.every(term => `${issue.title} ${issue.body} ${issue.epic_id}`.toLowerCase().includes(term)));
}

export function safeLink(value) {
  if (typeof value !== 'string') return null;
  const text = value.trim();
  const compact = text.replace(/[\u0000-\u0020\u007f]/g, '');
  if (!text || compact.startsWith('//') || text.includes('\\')) return null;
  const scheme = compact.match(/^([a-z][a-z0-9+.-]*):/i);
  if (scheme && !/^https?:\/\//i.test(compact)) return null;
  if (/[\u0000-\u001f\u007f]/.test(text)) return null;
  if (scheme) {
    try { if (!['https:', 'http:'].includes(new URL(text).protocol)) return null; }
    catch { return null; }
  }
  return text;
}

export function resolveSource(value, source) {
  try {
    const url = new URL(value, `http://workspace.local/${source}`);
    if (url.origin !== 'http://workspace.local') return null;
    return decodeURIComponent(url.pathname).slice(1);
  } catch { return null; }
}

export function dependencyGraph(issues, matches = issues) {
  const lookup = new Map(issues.map(issue => [issue.id, issue]));
  const matched = new Set(matches.map(issue => issue.id)), included = new Set();
  function include(id) {
    if (included.has(id) || !lookup.has(id)) return;
    included.add(id);
    for (const blocker of lookup.get(id).blockers || []) include(blocker);
  }
  for (const id of matched) include(id);
  const ids = [...included].sort();
  const blockers = id => [...new Set(lookup.get(id).blockers || [])].filter(id => included.has(id)).sort();
  // Condense strongly connected tasks before layering: cycles remain visible,
  // and their descendants still occupy later columns.
  const indices = new Map(), low = new Map(), stack = [], active = new Set(), groups = [], groupOf = new Map();
  let index = 0;
  function visit(id) {
    indices.set(id, index); low.set(id, index++); stack.push(id); active.add(id);
    for (const source of blockers(id)) {
      if (!indices.has(source)) { visit(source); low.set(id, Math.min(low.get(id), low.get(source))); }
      else if (active.has(source)) low.set(id, Math.min(low.get(id), indices.get(source)));
    }
    if (low.get(id) === indices.get(id)) {
      const group = [];
      let member;
      do { member = stack.pop(); active.delete(member); group.push(member); groupOf.set(member, groups.length); } while (member !== id);
      groups.push(group);
    }
  }
  for (const id of ids) if (!indices.has(id)) visit(id);
  const ranks = new Map();
  function rank(group) {
    if (!ranks.has(group)) {
      const parents = groups[group].flatMap(id => blockers(id).map(id => groupOf.get(id))).filter(other => other !== group);
      ranks.set(group, parents.length ? 1 + Math.max(...parents.map(rank)) : 0);
    }
    return ranks.get(group);
  }
  const columns = new Map(), nodes = [];
  const ordered = ids.sort((a, b) => lookup.get(a).epic_id.localeCompare(lookup.get(b).epic_id) || a.localeCompare(b));
  for (const id of ordered) {
    const group = groupOf.get(id), column = rank(group), row = columns.get(column) || 0;
    columns.set(column, row + 1);
    nodes.push({ issue: lookup.get(id), context: !matched.has(id), cycle: groups[group].length > 1 || blockers(id).includes(id),
      x: 56 + column * 334, y: 36 + row * 146, width: 244, height: 116 });
  }
  const edges = ids.flatMap(target => blockers(target).map(source => ({source, target, cycle: groupOf.get(source) === groupOf.get(target)})));
  const positions = new Map(nodes.map(node => [node.issue.id, node]));
  const bottom = Math.max(204, ...nodes.map(node => node.y + node.height));
  let lanes = 0;
  for (const edge of edges) {
    const source = positions.get(edge.source), target = positions.get(edge.target);
    if (!edge.cycle && target.x - source.x > 334) {
      const startX = source.x + source.width, startY = source.y + source.height / 2;
      const endX = target.x, endY = target.y + target.height / 2, laneY = bottom + 24 + lanes++ * 14;
      edge.via = [[startX,startY], [startX+32,startY], [startX+32,laneY], [endX-32,laneY], [endX-32,endY], [endX,endY]];
    }
  }
  return {nodes, edges, width: Math.max(360, ...nodes.map(n => n.x + n.width + 56)), height: bottom + 36 + lanes * 14};
}
