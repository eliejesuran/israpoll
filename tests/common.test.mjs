// Logique de js/common.js testée hors navigateur : validation du JSON du collecteur, choix de la source des sièges (Wikipédia par défaut).
import { createRequire } from 'node:module';
import vm from 'node:vm';
import fs from 'node:fs';
import assert from 'node:assert/strict';

const require = createRequire(import.meta.url);
const ctx = vm.createContext({
  console, Intl, URL, URLSearchParams, Date, Math, JSON, Object, Array, Number, String, Set, Map, Promise, setTimeout, clearTimeout, AbortController,
  location: { search: '', href: 'https://example.test/' }, localStorage: { getItem: () => null, setItem() {} },
  matchMedia: () => ({ matches: false }), document: {}, Seats: require('../js/seats.js'),
});
vm.runInContext(fs.readFileSync(new URL('../js/common.js', import.meta.url), 'utf8'), ctx);
const run = (code) => vm.runInContext(code, ctx);

const PRESS = { as_of: '10:58', counted_pct: 76.89, valid: 4006695, stations: 9224,
  seats: { yashar: 20, together: 11, democrats: 8, yb: 8, joint: 13, raam: 6, likud: 27, otzma: 7, shas: 7, utj: 7, rzp: 6 } };
const VOTES = { 'מחל': 828972, 'דרך': 640000, 'רק': 350000, 'אמת': 250000, 'ל': 240000, 'ודם': 400000, 'עם': 210000, 'ב': 270000, 'ט': 240000, 'ג': 250000, 'שס': 280000 };
const valid = Object.values(VOTES).reduce((a, b) => a + b, 0);
const LIVE = { status: 'counting', votes: VOTES, totals: { eligible: 7331981, voters: valid + 10000, valid, invalid: 10000 } };
const WIKI = { valid, invalid: 10000, eligible: 7331981, counted_pct: 93.2, as_of: '14:32', revid: 1382415353, others: 0, votes: VOTES };
const wikiAt = (drop) => ({ ...WIKI, valid: valid - drop, votes: { ...VOTES, 'מחל': VOTES['מחל'] - drop } });   // même tableau, un peu moins avancé
const derive = (live, seatSource) => { run('state.seatSource = ' + JSON.stringify(seatSource ?? null)); run('state.live = sanitizeLive(' + JSON.stringify(live) + ')'); return JSON.parse(run('JSON.stringify((model = derive(), { def: model.def, active: model.active.key, sources: Object.keys(model.sources), phase: phase(), vote: model.voteSource && model.voteSource.key, valid: model.totals && model.totals.valid, links: model.active.links.map(l => l.url) }))')); };

// 1. Validation du JSON : jamais de plantage, jamais de chiffre inventé
assert.equal(run('sanitizeLive(null)'), null);
assert.equal(run('sanitizeLive([])'), null);
assert.equal(run('sanitizeLive({ votes: { a: "x" }, totals: { valid: "abc" } }).totals'), null);              // pas de voix = pas de résultat
assert.equal(run('sanitizeLive({ status: "bizarre" }).status'), 'waiting');
assert.equal(run(`sanitizeLive({ press: ${JSON.stringify({ ...PRESS, seats: { ...PRESS.seats, likud: 40 } })} }).press`), null);   // 133 sièges : rejeté
assert.equal(run(`sanitizeLive({ press: ${JSON.stringify({ ...PRESS, seats: { ...PRESS.seats, inconnu: 3, likud: 24 } })} }).press`), null); // parti inconnu écarté -> somme ≠ 120
assert.equal(run(`sanitizeLive({ press: ${JSON.stringify(PRESS)} }).press.valid`), 4006695);
assert.equal(run(`sanitizeLive({ official_seats: { 'מחל': 120 } }).official_seats`), null);                     // sièges officiels sans voix : ignorés
assert.equal(run(`sanitizeLive({ manual: { turnout: [{ pct: 50, time: '10:00', url: 'javascript:alert(1)' }, { pct: 'x' }, null] } }).manual.turnout[0].url`), '');
assert.equal(run(`sanitizeLive({ manual: { turnout: [{ pct: 50, time: '10:00' }, { pct: 'x' }, null, { pct: 130 }] } }).manual.turnout.length`), 1);

// 2. Choix de la source : officiel > totaux CEC > relais ; le relais ne passe devant que s'il est plus avancé
assert.equal(derive({}).active, 'none');
assert.equal(derive({ press: PRESS }).active, 'press');                                  // à défaut de tout total CEC
assert.equal(derive({ press: PRESS }).phase === 'counting' || derive({ press: PRESS }).phase === 'closed', true);
assert.equal(derive({ ...LIVE }).active, 'cec');
assert.equal(derive({ ...LIVE, press: { ...PRESS, valid: valid - 1 } }).active, 'cec');   // CEC plus avancé
assert.equal(derive({ ...LIVE, press: { ...PRESS, valid: valid + 1 } }).active, 'press'); // relais plus avancé
assert.equal(derive({ ...LIVE, press: { ...PRESS, valid: valid + 1 } }, 'cec').active, 'cec');   // choix manuel respecté
assert.equal(derive({ ...LIVE, official_seats: { 'מחל': 30, 'דרך': 20, 'רק': 12, 'אמת': 8, 'ל': 8, 'ודם': 11, 'עם': 6, 'ב': 7, 'ט': 6, 'ג': 6, 'שס': 6 } }).active, 'official');
assert.ok(derive({ ...LIVE, press: PRESS }).sources.includes('press'));
assert.equal(derive({ ...LIVE }).phase, 'counting');
assert.equal(derive({ ...LIVE, status: 'final' }).phase, 'final');

// 2 bis. Wikipédia (non officiel) : validée, puis base par défaut tant qu'elle n'a pas moins de bulletins que les totaux CEC
assert.equal(run(`sanitizeLive({ wiki: ${JSON.stringify(WIKI)} }).wiki.valid`), valid);
assert.equal(run(`sanitizeLive({ wiki: ${JSON.stringify({ ...WIKI, valid: valid + 90000 })} }).wiki`), null);           // somme des listes ≠ bulletins valides
assert.equal(run(`sanitizeLive({ wiki: ${JSON.stringify({ ...WIKI, votes: { 'מחל': 1, 'דרך': 2 } })} }).wiki`), null);   // trop peu de listes
assert.equal(run(`sanitizeLive({ wiki: ${JSON.stringify({ ...WIKI, votes: { ...VOTES, 'inconnue': 5 } })} }).wiki.votes.inconnue`), undefined);
assert.equal(run(`sanitizeLive({ wiki: ${JSON.stringify({ ...WIKI, counted_pct: 140, revid: 'x' })} }).wiki.counted_pct`), null);
assert.equal(run(`sanitizeLive({ wiki: ${JSON.stringify({ ...WIKI, revid: 'x' })} }).wiki.revid`), null);
assert.equal(derive({ wiki: WIKI }).active, 'wiki');                                       // à défaut de tout total CEC
assert.equal(derive({ wiki: WIKI }).phase, 'counting');
assert.equal(derive({ ...LIVE, wiki: WIKI }).active, 'wiki');                              // à égalité, Wikipédia est la base par défaut
assert.equal(derive({ ...LIVE, wiki: WIKI }).vote, 'cec');                                 // ... mais le tableau détaillé reste celui de la CEC
assert.equal(derive({ ...LIVE, wiki: wikiAt(10) }).active, 'cec');                         // totaux CEC plus avancés : ils reprennent la main
assert.equal(derive({ ...LIVE, press: { ...PRESS, valid: valid + 1 }, wiki: WIKI }).active, 'press');   // relais plus avancé que la base
assert.equal(derive({ ...LIVE, press: { ...PRESS, valid: valid - 1 }, wiki: WIKI }).active, 'wiki');
assert.equal(derive({ ...LIVE, wiki: WIKI }, 'cec').active, 'cec');                        // choix manuel respecté
assert.equal(derive({ wiki: WIKI, press: PRESS }, 'press').active, 'press');
const lead = derive({ ...LIVE, totals: { ...LIVE.totals, valid: valid - 10, voters: valid }, wiki: WIKI });   // Wikipédia plus avancée que la CEC
assert.deepEqual([lead.active, lead.vote, lead.valid], ['wiki', 'wiki', valid]);           // ses voix alimentent alors tableau et analyse
assert.equal(derive({ ...LIVE, official_seats: { 'מחל': 30, 'דרך': 20, 'רק': 12, 'אמת': 8, 'ל': 8, 'ודם': 11, 'עם': 6, 'ב': 7, 'ט': 6, 'ג': 6, 'שס': 6 }, wiki: WIKI }).active, 'official');
assert.ok(derive({ wiki: WIKI }).links.includes('https://en.wikipedia.org/w/index.php?title=2026_Israeli_legislative_election&oldid=1382415353'));   // sourcée, révision précise
assert.ok(derive({ ...LIVE, wiki: WIKI }).sources.includes('wiki'));

// 3. Les sièges estimés somment toujours 120
run('state.live = sanitizeLive(' + JSON.stringify(LIVE) + '); state.seatSource = null; model = derive()');
assert.equal(run('Object.values(model.seats).reduce((a, b) => a + b, 0)'), 120);
run('state.live = sanitizeLive(' + JSON.stringify({ wiki: WIKI }) + '); state.seatSource = null; model = derive()');
assert.equal(run('model.active.key'), 'wiki');
assert.equal(run('Object.values(model.seats).reduce((a, b) => a + b, 0)'), 120);                 // y compris sur les voix de Wikipédia

console.log('common.test.mjs : OK');
