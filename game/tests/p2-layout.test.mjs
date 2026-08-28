import test from 'node:test';
import assert from 'node:assert/strict';
import {createEnemies, updateEnemyActivation, ENEMY_DESCRIPTORS} from '../level-data.mjs';

const byId = id => createEnemies().find(e => e.id === id);
const at = (e, playerX, viewLeft = playerX - 336, viewWidth = 960) => updateEnemyActivation(e, playerX, viewLeft, viewWidth);

test('farmer-1 sits on the pit landing and cannot wake at x<=820', () => {
  const d = ENEMY_DESCRIPTORS.find(e => e.id === 'farmer-1');
  assert.equal(d.x, 900);
  assert.ok(d.minPlayerX > 820);
  const e = byId('farmer-1');
  assert.equal(at(e, 530).active, false);
  assert.equal(at(e, 700).active, false);
  assert.equal(at(e, 820).active, false);
  assert.equal(at(e, 820).visible, false);
  const after = at(e, 900);
  assert.equal(after.active, true);
  assert.equal(after.visible, true);
});

test('pack 2480-3000 does not share one wake window', () => {
  assert.equal(at(byId('brute-1'), 1920).active, false);
  assert.equal(at(byId('brute-1'), 2300).active, true);
  assert.equal(at(byId('farmer-2'), 2300).active, false);
  assert.equal(at(byId('farmer-2'), 2680).active, true);
  assert.equal(at(byId('animal-2'), 2680).active, false);
  assert.equal(at(byId('animal-2'), 2920).active, true);
});

test('boss stays quiet on pit lip 4130 until arenaGate 4300', () => {
  const boss = byId('boss-1');
  assert.equal(boss.arenaGate, 4300);
  const lip = at(boss, 4130, 3800, 960);
  assert.equal(lip.active, false);
  assert.equal(lip.visible, false);
  const pre = at(boss, 4299, 4000, 960);
  assert.equal(pre.active, false);
  const inArena = at(boss, 4300, 4000, 960);
  assert.equal(inArena.active, true);
  assert.equal(inArena.visible, true);
});