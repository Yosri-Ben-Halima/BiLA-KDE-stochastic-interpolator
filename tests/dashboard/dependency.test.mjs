import test from 'node:test';
import assert from 'node:assert/strict';
import { dependencyGraph } from '../../dashboard/model.mjs';

const issue = (id, blockers = [], epic_id = 'research') => ({id, blockers, epic_id, title: id, status: 'blocked'});

test('filtered graph retains recursive prerequisites and directs edges toward dependents', () => {
  const rows = [issue('a'), issue('b', ['a']), issue('c', ['a']), issue('d', ['b', 'c']), issue('unrelated')];
  const before = JSON.stringify(rows);
  const graph = dependencyGraph(rows, [rows[3]]);
  assert.deepEqual(graph.nodes.map(n => n.issue.id).sort(), ['a','b','c','d']);
  assert.deepEqual(graph.edges.map(e => `${e.source}->${e.target}`).sort(), ['a->b','a->c','b->d','c->d']);
  assert.deepEqual(graph.nodes.filter(n=>!n.context).map(n=>n.issue.id), ['d']);
  for (const edge of graph.edges) {
    const first = graph.nodes.find(n=>n.issue.id===edge.source);
    const second = graph.nodes.find(n=>n.issue.id===edge.target);
    assert.ok(first.x < second.x);
  }
  assert.equal(JSON.stringify(rows), before);
});

test('cycles, self links and descendants are finite and visibly flagged', () => {
  const rows = [issue('a',['b']),issue('b',['a']),issue('c',['b']),issue('self',['self'])];
  const graph = dependencyGraph(rows);
  assert.deepEqual(graph.nodes.filter(n=>n.cycle).map(n=>n.issue.id).sort(), ['a','b','self']);
  assert.equal(graph.edges.filter(e=>e.cycle).length, 3);
  const b = graph.nodes.find(n=>n.issue.id==='b'), c = graph.nodes.find(n=>n.issue.id==='c');
  assert.ok(b.x<c.x);
});

test('disconnected tasks and missing references have stable nonoverlapping bounded positions', () => {
  const rows = [issue('z',['missing']), issue('a',[], 'other'), issue('b')];
  const graph = dependencyGraph(rows);
  assert.equal(graph.edges.length, 0);
  assert.deepEqual(dependencyGraph([...rows].reverse()), graph);
  for (const node of graph.nodes) {
    assert.ok(Number.isFinite(node.x+node.y));
    assert.ok(node.x>=0 && node.y>=0 && node.x+node.width<=graph.width && node.y+node.height<=graph.height);
    for (const other of graph.nodes.filter(n=>n!==node)) {
      assert.ok(node.x+node.width<=other.x || other.x+other.width<=node.x || node.y+node.height<=other.y || other.y+other.height<=node.y);
    }
  }
  assert.deepEqual(dependencyGraph(rows, []).nodes, []);
});

test('a direct dependency skipping a column stays visible around intermediate cards', () => {
  const graph = dependencyGraph([issue('a'), issue('b',['a']), issue('c',['a','b'])]);
  const edge = graph.edges.find(e=>e.source==='a' && e.target==='c');
  assert.ok(edge.via?.length >= 4, 'skip-column edge needs an unobstructed route');
  const middle = graph.nodes.find(n=>n.issue.id==='b');
  for (let i=1;i<edge.via.length;i++) {
    const [x1,y1]=edge.via[i-1], [x2,y2]=edge.via[i];
    assert.ok(x1===x2 || y1===y2);
    const crosses = x1===x2 ? x1>middle.x && x1<middle.x+middle.width && Math.max(y1,y2)>middle.y && Math.min(y1,y2)<middle.y+middle.height
      : y1>middle.y && y1<middle.y+middle.height && Math.max(x1,x2)>middle.x && Math.min(x1,x2)<middle.x+middle.width;
    assert.equal(crosses, false);
    assert.ok(x2>=0 && x2<=graph.width && y2>=0 && y2<=graph.height);
  }
});
