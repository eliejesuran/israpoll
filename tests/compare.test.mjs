import { createRequire } from 'node:module';
import assert from 'node:assert/strict';

const require = createRequire(import.meta.url);
const Compare = require('../js/compare.js');
const R22 = require('../js/data2022.js');

const near = (a, b, eps = 1e-9) => assert.ok(Math.abs(a - b) <= eps, `${a} ≠ ${b}`);

// 1. 2022 seul (aucun chiffre 2026) : les camps de 2022 et leurs totaux
const only22 = Compare.build({ r22: R22, votes26: null, valid26: 0, seats26: {}, hasSeats: false });
const g = Object.fromEntries(only22.groups.map(x => [x.id, x]));
assert.equal(g.netanyahu.tot.seats22, 64);          // Likoud 32 + Sionisme religieux/Otzma/Noam 14 + Shas 11 + UTJ 7
assert.equal(g.eisenkot.tot.seats22, 46);           // Yesh Atid 24 + Union nationale 12 + Israël Beiteinou 6 + Travaillistes 4
assert.equal(g.arab.tot.seats22, 10);               // Ra'am 5 + Hadash-Ta'al 5
assert.equal(only22.others.seats22, 0);
assert.equal(only22.total.seats22, 120);
near(only22.total.pct22, 1);                        // toutes les voix sont rattachées (autres comprises)
assert.equal(g.netanyahu.rows[0].votes22, 1115336);
near(g.netanyahu.rows[0].pct22, 0.2341, 5e-5);      // 23,41 % (tableau CEC)
assert.equal(only22.hasVotes, false);
assert.equal(g.netanyahu.rows[0].pct26, null);
assert.equal(g.netanyahu.rows[0].dPct, null);
assert.equal(g.netanyahu.rows[0].seats26, null);
near(only22.wasted22, 0.0876, 5e-4);                // ≈ 8,8 % des voix 2022 sans siège (Meretz, Balad, Foyer juif…)

// 2. Un scénario 2026 complet : écarts, listes fusionnées et reste
const votes26 = { likud: 800000, shas: 280000, utj: 280000, otzma: 280000, rzp: 250000, noam: 40000, yashar: 700000, together: 450000,
                  yb: 300000, democrats: 300000, joint: 450000, raam: 190000 };
const valid26 = 4000000;
const seats26 = { likud: 27, shas: 7, utj: 7, otzma: 7, rzp: 6, yashar: 20, together: 11, yb: 8, democrats: 8, joint: 13, raam: 6 };
const r = Compare.build({ r22: R22, votes26, valid26, seats26, hasSeats: true, wasted26: 120000 });
const h = Object.fromEntries(r.groups.map(x => [x.id, x]));
const rz = h.netanyahu.rows.find(x => x.id === 'rz');
assert.equal(rz.seats22, 14);
assert.equal(rz.seats26, 13);                       // rzp 6 + otzma 7 + noam 0 (absent de seats26)
assert.equal(rz.dSeats, -1);
near(rz.pct26, 570000 / valid26);
assert.equal(h.netanyahu.tot.seats26, 27 + 7 + 7 + 13);
assert.equal(h.eisenkot.tot.seats26, 20 + 11 + 8 + 8);
assert.equal(h.arab.tot.seats26, 19);
assert.equal(r.others.seats26, 120 - 54 - 47 - 19);  // le reste (ici 0)
assert.equal(r.total.seats26, 120);
near(r.wasted26, 0.03);
// « Réservistes » est nouvelle : 0 voix en 2022, jamais de division par zéro
const res = h.eisenkot.rows.find(x => x.id === 'reservists');
assert.equal(res.votes22, 0);
assert.equal(res.dSeats, 0);
// les voix des autres listes = reste
near(r.others.votes26, valid26 - Object.values(votes26).reduce((a, b) => a + b, 0));

// 3. Des sièges mais pas de voix (relais presse) : les parts restent absentes, les sièges comparables
const seatsOnly = Compare.build({ r22: R22, votes26: null, valid26: 0, seats26, hasSeats: true });
assert.equal(seatsOnly.total.seats26, 120 - seatsOnly.others.seats26 + seatsOnly.others.seats26);
assert.equal(seatsOnly.groups[0].rows[0].pct26, null);
assert.equal(seatsOnly.groups[0].rows[0].dSeats, 27 - 32);

// 4. Chaque identifiant 2022 est rattaché à une seule ligne (pas de double compte)
const seen = new Set();
Compare.GROUPS.flatMap(x => x.rows).flatMap(x => x.from).forEach(id => { assert.ok(!seen.has(id), `double compte : ${id}`); seen.add(id); });
Object.values(R22.lists).filter(l => l.votes > 100000).forEach(l => assert.ok(seen.has(l.id), `liste 2022 non rattachée : ${l.id}`));

console.log('compare.test.mjs : OK');
