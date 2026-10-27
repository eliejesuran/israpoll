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

// 4. Entrées dégradées : pas de sièges « Infinity », pas de boucle infinie.
const none = Seats.allocate({ a: 10, b: 10, c: 10, d: 10, e: 10, f: 10, g: 10, h: 10, i: 10, j: 10, k: 10, l: 10, m: 10, n: 10, o: 10, p: 10, q: 10, r: 10, s: 10, t: 10, u: 10, v: 10, w: 10, x: 10, y: 10, z: 10, aa: 10, bb: 10, cc: 10, dd: 10, ee: 10 }, []);
assert.equal(Object.values(none.seats).reduce((a, b) => a + b, 0), 0);          // aucune liste au-dessus de 3,25 %
const junk = Seats.allocate({ a: NaN, b: -5, c: 'x', d: 600, e: 400 }, []);
assert.equal(Object.values(junk.seats).reduce((a, b) => a + b, 0), 120);
assert.equal(junk.seats.d, 72);
assert.deepEqual(Seats.allocate({}, []).seats, {});

console.log('seats.test.mjs : OK');
