import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';

const require = createRequire(import.meta.url);
const Seats = require('../js/seats.js');
const fx = JSON.parse(readFileSync(new URL('./fixture-2022.json', import.meta.url)));

// 1. Les résultats officiels de 2022 sont reproduits exactement avec l'accord de surplus Likoud–Sionisme religieux.
const { seats } = Seats.allocate(fx.votes, [['מחל', 'ט']]);
const nonZero = (o) => Object.fromEntries(Object.entries(o).filter(([, n]) => n > 0));
assert.deepEqual(nonZero(seats), fx.expected_seats);
assert.equal(Object.values(seats).reduce((a, b) => a + b, 0), 120);

// 2. Sans accord, le dernier siège change de main (Likoud -> Avoda) : l'accord de surplus compte vraiment.
const bare = Seats.allocate(fx.votes, []).seats;
assert.equal(bare['מחל'], 31);
assert.equal(bare['אמת'], 5);
// Un accord avec une liste sous le seuil est ignoré.
const void_ = Seats.allocate(fx.votes, [['מחל', 'ט'], ['נץ', 'ד']]);
assert.equal(void_.seats['נץ'], 0);
assert.equal(Object.values(void_.seats).reduce((a, b) => a + b, 0), 120);

// 3. Arrondi de moyennes de sondages à 120.
const r = Seats.roundToTotal({ a: 50.4, b: 40.3, c: 29.3 });
assert.equal(r.a + r.b + r.c, 120);

console.log('seats.test.mjs : OK');
