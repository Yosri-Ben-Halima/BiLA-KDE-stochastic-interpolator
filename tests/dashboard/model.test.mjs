import test from 'node:test';
import assert from 'node:assert/strict';
import { filterIssues, safeLink, resolveSource } from '../../dashboard/model.mjs';

const rows = [
  {id:'one', title:'Density repair', body:'Numerical scales', epic_id:'validation', status:'blocked'},
  {id:'two', title:'Input contracts', body:'NumPy arrays', epic_id:'implementation', status:'resolved'},
  {id:'three', title:'Density repair', body:'Design review', epic_id:'monitor', status:'ready'},
];

test('filters intersect and preserve stable identities without mutating source', () => {
  assert.deepEqual(filterIssues(rows, {query:'SCALES', epic:'validation', status:'blocked'}).map(x=>x.id), ['one']);
  assert.deepEqual(filterIssues(rows, {query:'density'}).map(x=>x.id), ['one','three']);
  assert.equal(filterIssues(rows, {epic:'monitor', status:'blocked'}).length, 0);
  assert.equal(filterIssues(rows, {}).length, 3);
  assert.equal(rows.length, 3);
});

test('links allow documented references and reject executable or protocol-relative values', () => {
  for (const value of ['javascript:alert(1)', 'data:text/html,bad', '//example.com', 'file:///secret', 'vbscript:msgbox(1)']) {
    assert.equal(safeLink(value), null);
  }
  assert.equal(safeLink('https://example.com'), 'https://example.com');
  assert.equal(safeLink('../map.md'), '../map.md');
  assert.equal(safeLink('javascript\n:alert(1)'), null);
});

test('malformed percent escapes cannot break issue details', () => {
  assert.equal(resolveSource('%E0%A4%A', '.scratch/epic/issues/01.md'), null);
  assert.equal(resolveSource('../map.md', '.scratch/epic/issues/01.md'), '.scratch/epic/map.md');
  assert.equal(resolveSource('https://example.com', '.scratch/epic/issues/01.md'), null);
});
