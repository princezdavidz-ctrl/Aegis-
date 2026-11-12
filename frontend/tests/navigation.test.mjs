import assert from 'node:assert/strict';
import test from 'node:test';
import { navigationItems } from '../src/data/navigation.js';

test('navigation exposes each planned workspace module once', () => {
  const ids = navigationItems.map(({ id }) => id);

  assert.deepEqual(ids, [
    'overview',
    'assets',
    'investigations',
    'agents',
    'integrations',
    'memory',
    'audit',
  ]);
  assert.equal(new Set(ids).size, ids.length);
});

test('every navigation item has a human-readable label and description', () => {
  for (const item of navigationItems) {
    assert.ok(item.label.trim().length > 0, `${item.id} should have a label`);
    assert.ok(item.description.trim().length > 0, `${item.id} should have a description`);
  }
});
