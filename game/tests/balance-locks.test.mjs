import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {dirname, join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {RULES, applyPageUnlock} from '../rules.mjs';
import {ENEMY_DESCRIPTORS} from '../level-data.mjs';

const gameSrc = readFileSync(join(dirname(fileURLToPath(import.meta.url)), '../game.mjs'), 'utf8');
const byType = type => ENEMY_DESCRIPTORS.filter(e => e.type === type);

test('Farmer lockt 70 HP und 12 Kontakt', () => {
  const farmers = byType('farmer');
  assert.equal(farmers.length, 2);
  for (const e of farmers) {
    assert.equal(e.hp, 70, e.id);
    assert.equal(e.damage, 12, e.id);
  }
});

test('Animal lockt 60 HP und 10 Kontakt', () => {
  const animals = byType('animal');
  assert.equal(animals.length, 2);
  for (const e of animals) {
    assert.equal(e.hp, 60, e.id);
    assert.equal(e.damage, 10, e.id);
  }
});

test('Brute lockt 115 HP und 20 Kontakt', () => {
  const [brute] = byType('brute');
  assert.equal(brute.hp, 115);
  assert.equal(brute.damage, 20);
});

test('Boss lockt 260 HP und 26 Kontakt', () => {
  const bosses = byType('boss');
  assert.equal(bosses.length, 1);
  assert.equal(bosses[0].hp, 260);
  assert.equal(bosses[0].damage, 26);
});

test('Nahkampf bleibt 28, Energie-Cap 100', () => {
  assert.equal(RULES.meleeDamage, 28);
  assert.equal(RULES.maxEnergy, 100);
});

test('Flaschen-Istwerte frost/ember/confusion', () => {
  assert.deepEqual(RULES.bottles, {
    frost: {damage: 12, duration: 3},
    ember: {damage: 38, duration: 2},
    confusion: {damage: 14, duration: 5}
  });
});

test('Flaschen-Start ist 4/4/4 bei Cap 4', () => {
  assert.match(gameSrc, /bottles:\{frost:4,ember:4,confusion:4\}/);
  assert.match(gameSrc, /bottleCapacity\|\|4/);
});

test('Seiten-Unlock hebt Flaschen-Cap von 4 auf 5', () => {
  const before = {pages: 3, pageUnlock: false, bottleCapacity: 4, bottles: {frost: 4, ember: 4, confusion: 4}};
  const after = applyPageUnlock(before);
  assert.equal(after.bottleCapacity, 5);
  assert.deepEqual(after.bottles, {frost: 5, ember: 5, confusion: 5});
});
