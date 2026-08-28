import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {dirname, join} from 'node:path';
import {fileURLToPath} from 'node:url';

const gameSrc = readFileSync(join(dirname(fileURLToPath(import.meta.url)), '../game.mjs'), 'utf8');

test('LEVEL COMPLETE hängt an complete, complete an playerWin, nicht an despawned', () => {
  assert.match(gameSrc, /playerWin\(e\)\)complete=true/);
  assert.equal(gameSrc.includes("state==='despawned')complete=true"), false);
  const completeGate = gameSrc.indexOf('if(complete){');
  const overlay = gameSrc.indexOf("text('LEVEL COMPLETE'");
  assert.ok(completeGate >= 0 && overlay > completeGate);
});

test('Checkpoint liegt nach Heal 3350 bei x=3380, Respawn an der Markierung', () => {
  assert.match(gameSrc, /checkpoint=\{x:3380,y:414/);
  assert.match(gameSrc, /p\.x>=checkpoint\.x/);
  assert.match(gameSrc, /respawn\(p,checkpoint\.active\?checkpoint:/);
  assert.match(gameSrc, /item\(3350,438\),kind:'heal'/);
});
