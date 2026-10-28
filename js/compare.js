/*
 * Comparaison 2026 / 2022 par famille politique (« obédience »).
 *
 *   Compare.build({ r22, votes26, valid26, seats26, hasSeats, wasted26 }) -> { groups, total, others, wasted22, wasted26 }
 *
 * r22      : RESULTS_2022 (js/data2022.js)
 * votes26  : { idParti: voix } (identifiants de PARTIES) ou null si la CEC n'a rien publié ; valid26 = bulletins valides comptés
 * seats26  : { idParti: sièges } de la source active (sièges CEC, estimation Bader-Ofer ou relais) ; hasSeats = false si vide
 * wasted26 : voix des listes sous le seuil de 3,25 % (ou null)
 *
 * La correspondance 2022 -> 2026 est une LECTURE ÉDITORIALE : fusions et scissions rendent certaines comparaisons approximatives ;
 * chaque ligne l'explique dans `note`. Fonctionne dans le navigateur (window.Compare) et sous Node (require).
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.Compare = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  const TOTAL_SEATS = 120;

  // from = listes de 2022 (RESULTS_2022.lists[*].id) ; to = listes de 2026 (PARTIES[*].id)
  const GROUPS = [
    { id: "netanyahu", name: "Droite, extrême droite et ultra-orthodoxes", sub: "Bloc Netanyahou (coalition sortante)", color: "#2f6df6", rows: [
      { id: "likud", name: "Likoud", from: ["likud22"], to: ["likud"],
        note: "Nouvel Espoir (Gideon Sa’ar), allié de l’Union nationale en 2022, n’a pas de liste propre en 2026 (fusion annoncée avec le Likoud)." },
      { id: "rz", name: "Sionisme religieux · Otzma Yehudit · Noam", from: ["rz22"], to: ["rzp", "otzma", "noam"],
        note: "Une seule liste commune en 2022 ; trois listes distinctes en 2026." },
      { id: "shas", name: "Shas", from: ["shas22"], to: ["shas"], note: "Ultra-orthodoxes séfarades." },
      { id: "utj", name: "Judaïsme unifié de la Torah", from: ["utj22"], to: ["utj"], note: "Ultra-orthodoxes ashkénazes." },
    ] },
    { id: "eisenkot", name: "Centre, gauche et droite laïque", sub: "Bloc Eisenkot (opposition)", color: "#12b8a6", rows: [
      { id: "together", name: "Yesh Atid → Ensemble", from: ["ya22"], to: ["together"],
        note: "Ensemble réunit Yesh Atid (Yair Lapid) et Naftali Bennett, qui n’avait pas de liste en 2022." },
      { id: "yashar", name: "Union nationale → Yashar", from: ["nu22"], to: ["yashar"],
        note: "En 2022, Gantz, Sa’ar et Eisenkot partageaient une liste. En 2026 Gantz s’est retiré (19 octobre), Sa’ar n’a pas de liste propre : Yashar (Eisenkot) n’en recueille qu’une partie." },
      { id: "yb", name: "Israël Beiteinou", from: ["yb22"], to: ["yb"], note: "Droite laïque, dans l’opposition." },
      { id: "left", name: "Travaillistes + Meretz → Démocrates", from: ["labor22", "meretz22"], to: ["democrats"],
        note: "Fusion de deux listes ; Meretz (3,16 %) était sous le seuil de 3,25 % en 2022." },
      { id: "reservists", name: "Réservistes–Économique", from: [], to: ["reservists"], note: "Nouvelle liste (Yoaz Hendel, Yaron Zelekha)." },
    ] },
    { id: "arab", name: "Partis arabes", sub: "Ni dans l’un, ni dans l’autre bloc", color: "#1f9d55", rows: [
      { id: "raam", name: "Ra’am", from: ["raam22"], to: ["raam"], note: "Liste arabe islamiste (Mansour Abbas)." },
      { id: "joint", name: "Hadash–Ta’al + Balad → Liste commune", from: ["hadash22", "balad22"], to: ["joint"],
        note: "Réunification ; Balad (2,91 %) était sous le seuil en 2022." },
    ] },
  ];

  const sumOf = (map, ids) => ids.reduce((s, id) => s + ((map && map[id]) || 0), 0);

  function build(o) {
    const r22 = o.r22, votes26 = o.votes26 || null, valid26 = o.valid26 || 0, seats26 = o.seats26 || {};
    const hasVotes = !!votes26 && valid26 > 0, hasSeats = !!o.hasSeats;
    const v22 = {}, s22 = {};
    Object.values(r22.lists).forEach(l => { v22[l.id] = l.votes; s22[l.id] = l.seats; });
    const valid22 = r22.totals.valid;
    const used22 = new Set(), used26 = new Set();

    const mk = (id, name, note, from, to, extra) => {
      const row = { id, name, note, from, to, votes22: extra ? extra.votes22 : sumOf(v22, from), seats22: extra ? extra.seats22 : sumOf(s22, from) };
      row.pct22 = row.votes22 / valid22;
      row.votes26 = hasVotes ? (extra ? extra.votes26 : sumOf(votes26, to)) : null;
      row.pct26 = hasVotes ? row.votes26 / valid26 : null;
      row.seats26 = hasSeats ? (extra ? extra.seats26 : sumOf(seats26, to)) : null;
      row.dPct = hasVotes ? row.pct26 - row.pct22 : null;       // en fraction (0,01 = 1 point)
      row.dSeats = hasSeats ? row.seats26 - row.seats22 : null;
      return row;
    };
    const total = (rows) => {
      const t = { votes22: 0, seats22: 0, votes26: 0, seats26: 0 };
      rows.forEach(r => { t.votes22 += r.votes22; t.seats22 += r.seats22; t.votes26 += r.votes26 || 0; t.seats26 += r.seats26 || 0; });
      t.pct22 = t.votes22 / valid22;
      t.pct26 = hasVotes ? t.votes26 / valid26 : null;
      t.seats26 = hasSeats ? t.seats26 : null;
      t.votes26 = hasVotes ? t.votes26 : null;
      t.dPct = hasVotes ? t.pct26 - t.pct22 : null;
      t.dSeats = hasSeats ? t.seats26 - t.seats22 : null;
      return t;
    };

    const groups = GROUPS.map(g => {
      const rows = g.rows.map(r => { r.from.forEach(i => used22.add(i)); r.to.forEach(i => used26.add(i)); return mk(r.id, r.name, r.note, r.from, r.to); });
      return { id: g.id, name: g.name, sub: g.sub, color: g.color, rows, tot: total(rows) };
    });

    // « autres listes » : tout ce qui n'est rattaché à aucune ligne (reste des voix, reste des sièges)
    const mapped = groups.flatMap(g => g.rows);
    const sum22v = mapped.reduce((s, r) => s + r.votes22, 0), sum22s = mapped.reduce((s, r) => s + r.seats22, 0);
    const sum26v = mapped.reduce((s, r) => s + (r.votes26 || 0), 0), sum26s = mapped.reduce((s, r) => s + (r.seats26 || 0), 0);
    const others = mk("others", "Autres listes", "Listes mineures, Foyer juif (1,19 % en 2022), Amcha Israël, Public haredi… ; en 2026 aussi Kakhol Lavan (Gantz, retiré).", [], [], {
      votes22: valid22 - sum22v, seats22: TOTAL_SEATS - sum22s,
      votes26: hasVotes ? valid26 - sum26v : null, seats26: hasSeats ? Math.max(0, TOTAL_SEATS - sum26s) : null,
    });
    const allRows = [...mapped, others];
    const grand = total(allRows);

    // voix sans siège (listes sous le seuil) : 2022 = tout ce qui n'a obtenu aucun siège
    const wasted22 = (valid22 - Object.values(r22.lists).filter(l => l.seats > 0).reduce((s, l) => s + l.votes, 0)) / valid22;
    const wasted26 = hasVotes && o.wasted26 != null ? o.wasted26 / valid26 : null;
    return { groups, others, total: grand, wasted22, wasted26, hasVotes, hasSeats, valid22, valid26 };
  }

  return { GROUPS, build };
});
