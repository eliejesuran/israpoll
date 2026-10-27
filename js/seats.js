/*
 * Répartition des 120 sièges de la Knesset : seuil de 3,25 % puis méthode Bader-Ofer,
 * avec accords de surplus (heskem odafim).
 *
 *   Seats.allocate(votes, pacts) -> { seats, passed, quota, threshold, valid }
 *
 * votes : { id: nombre de voix }   pacts : [[idA, idB], ...]
 * Fonctionne dans le navigateur (window.Seats) et sous Node (require).
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.Seats = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  const TOTAL = 120;
  const THRESHOLD = 0.0325;

  function allocate(votes, pacts, opts) {
    const total = (opts && opts.total) || TOTAL;
    const threshold = (opts && opts.threshold) || THRESHOLD;
    const ids = Object.keys(votes);
    const valid = ids.reduce((s, id) => s + votes[id], 0);
    const seats = {};
    ids.forEach(id => (seats[id] = 0));
    if (!valid) return { seats, passed: [], quota: 0, threshold, valid };

    // 1. seuil électoral
    const passed = ids.filter(id => votes[id] / valid >= threshold);
    const passedVotes = passed.reduce((s, id) => s + votes[id], 0);

    // 2. quotient national : un siège par tranche entière
    const quota = passedVotes / total;
    let given = 0;
    passed.forEach(id => {
      seats[id] = Math.floor(votes[id] / quota);
      given += seats[id];
    });

    // 3. sièges restants : plus forte moyenne ; les listes liées par un accord de surplus
    //    concourent ensemble, puis le siège revient à celle des deux qui a la plus forte moyenne.
    const inPass = new Set(passed);
    const units = [];
    const paired = new Set();
    (pacts || []).forEach(([a, b]) => {
      if (inPass.has(a) && inPass.has(b) && !paired.has(a) && !paired.has(b)) {
        units.push([a, b]);
        paired.add(a);
        paired.add(b);
      }
    });
    passed.forEach(id => { if (!paired.has(id)) units.push([id]); });

    const avg = (u) => u.reduce((s, id) => s + votes[id], 0) / (u.reduce((s, id) => s + seats[id], 0) + 1);
    while (given < total) {
      let best = null;
      units.forEach(u => {
        if (!best || avg(u) > avg(best)) best = u;
      });
      let winner = best[0];
      if (best.length === 2) {
        const [a, b] = best;
        winner = votes[a] / (seats[a] + 1) >= votes[b] / (seats[b] + 1) ? a : b;
      }
      seats[winner]++;
      given++;
    }
    return { seats, passed, quota, threshold, valid };
  }

  // Arrondit des sièges fractionnaires (moyennes de sondages) à un total entier, par plus fort reste.
  function roundToTotal(frac, total) {
    total = total || TOTAL;
    const ids = Object.keys(frac);
    const out = {};
    let used = 0;
    ids.forEach(id => { out[id] = Math.floor(frac[id]); used += out[id]; });
    ids
      .map(id => [id, frac[id] - out[id]])
      .sort((a, b) => b[1] - a[1])
      .slice(0, Math.max(0, total - used))
      .forEach(([id]) => out[id]++);
    return out;
  }

  return { allocate, roundToTotal, TOTAL, THRESHOLD };
});
