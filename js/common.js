"use strict";
/* =====================================================================
   IsraPoll — code commun à toutes les pages (accueil, résultats bruts, analyse).
   Données (live.json), modèle dérivé, pastille « page actualisée », menu, pied de page, thème.
   Une page déclare PAGE = { id, sections: [[nom, fonction], …], start?() } puis appelle App.start(PAGE) :
   chaque section s'affiche indépendamment (si l'une échoue, les autres restent lisibles).
   ===================================================================== */

/* =====================================================================
   Configuration
   ===================================================================== */
const REPO = "eliejesuran/israpoll";
// Trois sources, la plus récente l'emporte. L'API GitHub est la plus fraîche (~1 min) mais limitée à 60 requêtes/h/IP ;
// raw.githubusercontent.com garde 5 min en cache ; data/live.json (version statique du site) sert de dernier recours.
const REFRESH_MS = 20000;
const LIVE_SOURCES = [
  { url: `https://api.github.com/repos/${REPO}/contents/live.json?ref=data`, headers: { Accept: "application/vnd.github.raw+json" }, api: true },
  { url: `https://raw.githubusercontent.com/${REPO}/data/live.json`, bust: true },
  { url: "data/live.json", bust: true, fallback: true },
];
const POLLS_CLOSE = new Date("2026-10-27T20:00:00Z");         // 22:00 à Jérusalem (UTC+2)
const FINAL_BY = "4 novembre 2026";
const CEC = {
  national: "https://votes26.bechirot.gov.il/nationalresults",
  csv: "https://media26.bechirot.gov.il/files/expc.csv",
};

// Relais presse NON officiel : projection qui reprend le dépouillement de la CEC (lien fixe, jamais celui du JSON).
const PRESS = { name: "The Petek", url: "https://www.thepetek.com/results" };

// Wikipédia (NON officiel) : le tableau des résultats de l'article reprend celui de la CEC. Liens fixes, jamais ceux du JSON.
const WIKI = {
  name: "Wikipédia", url: "https://en.wikipedia.org/wiki/2026_Israeli_legislative_election",
  rev: "https://en.wikipedia.org/w/index.php?title=2026_Israeli_legislative_election&oldid=",
  history: "https://en.wikipedia.org/w/index.php?title=2026_Israeli_legislative_election&action=history",
};

const BLOCS = {
  eisenkot:  { name: "Bloc Eisenkot",   sub: "Opposition « du changement »",  color: "#12b8a6" },
  arab:      { name: "Partis arabes",   sub: "Ni dans l’un, ni dans l’autre bloc", color: "#1f9d55" },
  netanyahu: { name: "Bloc Netanyahou", sub: "Coalition sortante",             color: "#2f6df6" },
  other:     { name: "Hors blocs",      sub: "Autres listes",                  color: "#8b93a1" },
};
const BLOC_ORDER = ["eisenkot", "arab", "other", "netanyahu"];

// letters = lettres de vote officielles (bulletin) ; ordre = placement dans l'hémicycle
const PARTIES = [
  { id: "democrats",  fr: "Les Démocrates",           he: "הדמוקרטים",   letters: "אמת", leader: "Yair Golan",                bloc: "eisenkot",  color: "#ec4899" },
  { id: "together",   fr: "Ensemble (Beyahad)",       he: "ביחד",        letters: "רק",  leader: "Naftali Bennett · Yair Lapid", bloc: "eisenkot", color: "#38b6ff" },
  { id: "yashar",     fr: "Yashar",                   he: "דרך / ישר",   letters: "דרך", leader: "Gadi Eisenkot",              bloc: "eisenkot",  color: "#12b8a6" },
  { id: "yb",         fr: "Israël Beiteinou",         he: "ישראל ביתנו", letters: "ל",   leader: "Avigdor Liberman",           bloc: "eisenkot",  color: "#94a3b8" },
  { id: "reservists", fr: "Réservistes–Économique",   he: "המילואימניקים", letters: "די", leader: "Yoaz Hendel · Yaron Zelekha", bloc: "eisenkot", color: "#a3d63a" },
  { id: "joint",      fr: "Liste commune",            he: "הרשימה המשותפת", letters: "ודם", leader: "Yousef Jabareen",        bloc: "arab",      color: "#1f9d55" },
  { id: "raam",       fr: "Ra’am",                    he: "רע״ם",        letters: "עם",  leader: "Mansour Abbas",              bloc: "arab",      color: "#8fd14f" },
  { id: "amcha",      fr: "Amcha Israël",             he: "עמך ישראל",   letters: "ך",   leader: "Ofer Winter",                bloc: "other",     color: "#b6a07a" },
  { id: "haredi",     fr: "Public haredi",            he: "הציבור החרדי", letters: "זך", leader: "Moti Litner",                bloc: "other",     color: "#9b8cc4" },
  { id: "noam",       fr: "Noam",                     he: "נעם",         letters: "ני",  leader: "Avi Maoz",                   bloc: "netanyahu", color: "#a0785a" },
  { id: "rzp",        fr: "Sionisme religieux–Zehut", he: "הציונות הדתית", letters: "ט", leader: "Bezalel Smotrich",           bloc: "netanyahu", color: "#f2762e" },
  { id: "otzma",      fr: "Otzma Yehudit",            he: "עוצמה יהודית", letters: "ב",  leader: "Itamar Ben-Gvir",            bloc: "netanyahu", color: "#c8322f" },
  { id: "utj",        fr: "Judaïsme unifié de la Torah", he: "יהדות התורה", letters: "ג", leader: "Yitzhak Goldknopf",         bloc: "netanyahu", color: "#7c5cf0" },
  { id: "shas",       fr: "Shas",                     he: "ש״ס",         letters: "שס",  leader: "Aryeh Deri",                 bloc: "netanyahu", color: "#f2a900" },
  { id: "likud",      fr: "Likoud",                   he: "הליכוד",      letters: "מחל", leader: "Benjamin Netanyahou",        bloc: "netanyahu", color: "#2f6df6" },
];
// Listes mineures (nom indicatif si la CEC n'en donne pas)
const MINOR = {
  "כן": "Kakhol Lavan (Gantz, retiré)", "בד": "Ensemble nous réussirons", "בי": "Tzomet–Beit Yisrael", "בקר": "Orot HaShachar",
  "ד": "Partenariat pour tous", "ה": "Gan Eden", "ז": "Bitahon (sécurité sociale)", "זץ": "Brit Olam", "י": "Israël d’abord",
  "יק": "Bloc biblique", "נף": "Shema", "נץ": "Bitahon Ishi", "נקי": "HaTikoun", "נר": "La couleur noire", "פה": "Ani VeAta",
  "צבי": "Ahi (retiré)", "צדק": "Sharshar", "צף": "Pirates", "ק": "Tekouma", "קה": "Kol HaNashim", "קך": "Nouvel ordre",
  "קץ": "Mishpat Tzedek", "רץ": "HaKahal",
};
const BY_ID = Object.fromEntries(PARTIES.map(p => [p.id, p]));
const BY_LETTERS = Object.fromEntries(PARTIES.map(p => [p.letters, p]));
// Accords de surplus déclarés (la paire Eternal Covenant–Fixing est trop petite pour compter)
const PACTS = [["together", "yb"], ["yashar", "democrats"], ["joint", "raam"], ["likud", "rzp"], ["shas", "utj"]];

/* =====================================================================
   Outils
   ===================================================================== */
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const nf = new Intl.NumberFormat("fr-FR");
const fmt = (n) => nf.format(Math.round(n));
const pc = (x, d = 1) => (x * 100).toFixed(d).replace(".", ",") + " %";
const sum = (a) => a.reduce((s, x) => s + x, 0);
const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* navigation privée */ } },
};
const tz = (d, zone) => new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit", timeZone: zone }).format(d);
const hhmmss = (d) => { d = d instanceof Date ? d : new Date(d); return isNaN(d) ? "—" : new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(d); };
const safeUrl = (u) => { try { const x = new URL(u, location.href); return /^https?:$/.test(x.protocol) ? x.href : ""; } catch { return ""; } };
const srcLine = (links, extra = "") =>
  `<span><b>Source :</b> ${links.map(l => `<a href="${esc(l.url)}" rel="noopener" target="_blank">${esc(l.label)}</a>`).join(" · ")}</span>${extra}`;

/* =====================================================================
   État
   ===================================================================== */
const state = {
  news: null,            // JSON des actualités (page d'accueil)
  live: null,            // JSON du collecteur (CEC)
  liveAt: 0,             // date du dernier chargement réussi
  apiPausedUntil: 0,     // quota de l'API GitHub presque épuisé : on l'ignore jusque-là
  loading: false, ok: null, lastTry: 0, nextAt: 0,   // pour la pastille « page actualisée »
  demo: typeof location === "undefined" ? null : new URLSearchParams(location.search).get("demo"),
  seatSource: null,      // choix manuel de la base de calcul (simulateur, analyse)
  sel: new Set(),        // partis cochés dans le simulateur
};
let model = null;        // données dérivées (voir derive)

/* =====================================================================
   Chargement des données
   ===================================================================== */
async function fetchJson(src, force) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), 8000);            // une requête qui pend ne doit pas bloquer les suivantes
  try {
    // API : cache HTTP du navigateur (60 s, revalidation gratuite par ETag) ; « Actualiser » force la revalidation.
    const r = await fetch(src.bust ? `${src.url}?t=${Date.now()}` : src.url, { cache: src.api ? (force ? "no-cache" : "default") : "no-store", headers: src.headers, signal: ctl.signal });
    if (src.api) noteRateLimit(r);
    if (!r.ok) throw new Error(r.status);
    return await r.json();
  } finally { clearTimeout(timer); }
}
function noteRateLimit(r) {
  const h = r.headers.get("x-ratelimit-remaining"), reset = Number(r.headers.get("x-ratelimit-reset"));
  const left = h === null ? NaN : Number(h);
  if (r.status === 403 || r.status === 429 || (Number.isFinite(left) && left <= 5)) state.apiPausedUntil = reset > 0 ? reset * 1000 : Date.now() + 10 * 60000;
}

// Le JSON vient d'un collecteur (et data/manual.json se modifie par PR) : on ne fait confiance ni aux types ni aux URL.
function sanitizeLive(raw) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const num = (v) => (Number.isFinite(+v) && +v >= 0 && v !== null && v !== "" ? +v : 0);
  const obj = (o) => (o && typeof o === "object" && !Array.isArray(o) ? o : {});
  const live = { ...raw };
  live.status = ["waiting", "counting", "final"].includes(raw.status) ? raw.status : "waiting";
  const t = obj(raw.totals);
  const votes = Object.fromEntries(Object.entries(obj(raw.votes)).map(([k, v]) => [String(k), num(v)]));
  live.totals = { eligible: num(t.eligible), voters: num(t.voters), valid: num(t.valid), invalid: num(t.invalid) };
  if (!live.totals.valid || !Object.keys(votes).length) { live.totals = null; live.votes = null; }   // pas de voix = pas de résultat
  else live.votes = votes;
  const seats = Object.fromEntries(Object.entries(obj(raw.official_seats)).map(([k, v]) => [String(k), Math.round(num(v))]));
  live.official_seats = Object.keys(seats).length && sum(Object.values(seats)) === 120 && live.votes ? seats : null;
  live.names = Object.fromEntries(Object.entries(obj(raw.names)).map(([k, v]) => [String(k), String(v)]));
  const pr = obj(raw.press), pct = +pr.counted_pct;
  const pseats = Object.fromEntries(Object.entries(obj(pr.seats)).filter(([id, n]) => BY_ID[id] && Number.isFinite(+n) && +n >= 0 && +n <= 120).map(([id, n]) => [id, Math.round(+n)]));
  live.press = sum(Object.values(pseats)) === 120 && Number.isFinite(pct) && pct > 0 && pct <= 100 && num(pr.valid) > 0
    ? { seats: pseats, counted_pct: pct, valid: num(pr.valid), stations: pr.stations != null ? num(pr.stations) : null, as_of: String(pr.as_of || "").slice(0, 5) }
    : null;
  // Wikipédia : voix des listes suivies (lettres de vote de la CEC) + reste des petites listes ; la somme doit retomber sur les bulletins valides
  const wk = obj(raw.wiki);
  const wvotes = Object.fromEntries(Object.entries(obj(wk.votes)).filter(([k]) => BY_LETTERS[k]).map(([k, v]) => [k, Math.round(num(v))]));
  const wvalid = Math.round(num(wk.valid)), wothers = Math.round(num(wk.others)), wpct = +wk.counted_pct;
  live.wiki = wvalid > 0 && Object.keys(wvotes).length >= 10 && Math.abs(sum(Object.values(wvotes)) + wothers - wvalid) <= Math.max(5, 0.005 * wvalid)
    ? { votes: wvotes, others: wothers, valid: wvalid, invalid: Math.round(num(wk.invalid)), eligible: Math.round(num(wk.eligible)),
        counted_pct: Number.isFinite(wpct) && wpct > 0 && wpct <= 100 ? wpct : null, as_of: String(wk.as_of || "").slice(0, 5),
        revid: Number.isInteger(+wk.revid) && +wk.revid > 0 ? +wk.revid : null }
    : null;
  const m = obj(raw.manual);
  live.manual = {
    final: m.final === true,
    final_turnout_est: Number.isFinite(+m.final_turnout_est) && +m.final_turnout_est > 20 && +m.final_turnout_est <= 100 ? +m.final_turnout_est : null,
    turnout: (Array.isArray(m.turnout) ? m.turnout : []).filter(x => x && x.pct != null && Number.isFinite(+x.pct) && +x.pct >= 0 && +x.pct <= 100)
      .map(x => ({ time: String(x.time || "").slice(0, 8), pct: +x.pct, prev2022: x.prev2022 != null && Number.isFinite(+x.prev2022) ? +x.prev2022 : null, source: String(x.source || "").slice(0, 80), url: safeUrl(x.url) })),
  };
  return live;
}

async function loadLive(force) {
  if (state.demo) { state.live = sanitizeLive(makeDemo(state.demo)); state.liveAt = Date.now(); return true; }
  const main = LIVE_SOURCES.filter(x => !x.fallback && !(x.api && Date.now() < state.apiPausedUntil));
  let res = await Promise.allSettled(main.map(x => fetchJson(x, force)));
  if (!res.some(r => r.status === "fulfilled")) res = await Promise.allSettled(LIVE_SOURCES.filter(x => x.fallback).map(x => fetchJson(x, force)));
  const ok = res.filter(r => r.status === "fulfilled").map(r => sanitizeLive(r.value)).filter(Boolean);
  if (!ok.length) return false;
  ok.sort((a, b) => String(b.checked_at || "").localeCompare(String(a.checked_at || "")));
  const cur = state.live && state.live.checked_at;
  if (!cur || String(ok[0].checked_at || "") >= cur) { state.live = ok[0]; state.liveAt = Date.now(); }   // une source en retard ne fait jamais reculer la page
  return true;
}

// Mode démo (?demo=1 | final) : chiffres SIMULÉS à partir de ce répertoire de sièges, pour tester l'interface.
const DEMO_SEATS = { yashar: 22, likud: 20, together: 14, democrats: 9, yb: 8, shas: 7, otzma: 8, utj: 7, rzp: 7, raam: 5, joint: 9, reservists: 4 };
function makeDemo(kind) {
  const avg = DEMO_SEATS;
  const quota = 37500;
  const votes = {};
  let k = 7;
  Object.entries(avg).forEach(([id, s]) => { votes[BY_ID[id].letters] = Math.round(s * quota * (0.96 + ((k = (k * 37 + 11) % 100) / 1250))); });
  votes["כן"] = 41000; votes["ך"] = 118000; votes["זך"] = 62000; votes["ני"] = 38000;
  const share = kind === "final" ? 1 : 0.58;
  Object.keys(votes).forEach(l => (votes[l] = Math.round(votes[l] * share)));
  const valid = sum(Object.values(votes));
  const live = {
    status: kind === "final" ? "final" : "counting",
    totals: { eligible: 6900000, voters: valid + 30000, valid, invalid: 30000 },
    votes,
    checked_at: new Date().toISOString(), updated_at: new Date().toISOString(),
    official_seats: null, source: { name: "DÉMO — chiffres simulés" },
    manual: {
      final: kind === "final",
      turnout: [{ time: "10:00", pct: 16.7, prev2022: 15.9, source: "démo" }, { time: "14:00", pct: 44.9, prev2022: null, source: "démo" }, { time: "20:00", pct: 66.1, prev2022: 63.4, source: "démo" }],
    },
  };
  if (kind === "final") {
    const v = {}; Object.entries(votes).forEach(([l, n]) => { const p = BY_LETTERS[l]; v[p ? p.id : "x_" + l] = n; });
    const r = Seats.allocate(v, PACTS).seats;
    live.official_seats = {}; Object.entries(r).forEach(([id, n]) => { if (n) live.official_seats[id.startsWith("x_") ? id.slice(2) : BY_ID[id].letters] = n; });
  }
  return live;
}

/* =====================================================================
   Modèle dérivé
   ===================================================================== */
function derive() {
  const live = state.live || {};
  const manual = live.manual || {};
  const cecTotals = live.totals && live.totals.valid > 0 ? live.totals : null;
  const wk = live.wiki || null;
  const names = live.names || {};
  const turnRef = (manual.final_turnout_est || 68) / 100;
  const clamp01 = (x) => Math.max(0, Math.min(Number.isFinite(x) ? x : 0, 1));

  // listes à partir de voix par lettre de vote (« ? » = reste des petites listes que Wikipédia ne détaille pas)
  const listsOf = (votes, valid) => {
    const out = Object.entries(votes).map(([letters, n]) => {
      const p = BY_LETTERS[letters];
      if (p) return { ...p, votes: n, letters };
      if (letters === "?") return { id: "x_others", fr: "Autres listes", he: "", letters: "—", leader: "", bloc: "other", color: "#8b93a1", votes: n };
      return { id: "x_" + letters, fr: MINOR[letters] || names[letters] || `Liste ${letters}`, he: names[letters] || "", letters, leader: "", bloc: "other", color: "#8b93a1", votes: n };
    }).sort((a, b) => b.votes - a.votes);
    out.forEach(l => (l.pct = valid ? l.votes / valid : 0));
    return out;
  };
  const cecLists = live.votes && cecTotals ? listsOf(live.votes, cecTotals.valid) : [];
  const wkLists = wk ? listsOf({ ...wk.votes, ...(wk.others > 0 ? { "?": wk.others } : {}) }, wk.valid) : [];
  const allocate = (lists) => { const v = {}; lists.forEach(l => (v[l.id] = l.votes)); return Seats.allocate(v, PACTS); };

  const sources = {};
  const cecLinks = [{ label: "CEC — résultats nationaux", url: CEC.national }];
  // 1. sièges officiels
  if (live.official_seats) {
    const seats = {};
    Object.entries(live.official_seats).forEach(([letters, n]) => { const p = BY_LETTERS[letters]; seats[p ? p.id : "x_" + letters] = n; });
    sources.official = { key: "official", label: "Sièges attribués par la CEC", chip: "Officiel", cls: "official", seats, links: cecLinks };
  }
  // 2. estimation Bader-Ofer sur les voix comptées de la CEC
  if (cecLists.length) {
    const r = allocate(cecLists);
    const share = cecTotals && cecTotals.eligible > 0 ? cecTotals.voters / (cecTotals.eligible * turnRef) : 0;
    sources.cec = { key: "cec", label: "Estimation sur les voix CEC", chip: live.status === "final" ? "Calcul · CEC" : "Calcul · dépouillement partiel", cls: "calc", seats: r.seats, passed: r.passed, share: clamp01(share), valid: cecTotals.valid, links: cecLinks };
  }
  // 3. Wikipédia, NON officiel : les voix par liste de l'article, qui reprend le tableau de la CEC (même méthode de calcul que 2.)
  if (wk) {
    const r = allocate(wkLists);
    const share = wk.counted_pct != null ? wk.counted_pct / 100 : wk.eligible > 0 ? (wk.valid + wk.invalid) / (wk.eligible * turnRef) : 0;
    sources.wiki = {
      key: "wiki", label: `Voix ${WIKI.name} (d’après le tableau de la CEC${wk.as_of ? ` · relevé de ${wk.as_of}, heure d’Israël` : ""})`, chip: `Non officiel · ${WIKI.name}`, cls: "nonoff",
      seats: r.seats, passed: r.passed, share: clamp01(share), valid: wk.valid, asOf: wk.as_of, revid: wk.revid,
      links: [{ label: `${WIKI.name} — « 2026 Israeli legislative election »${wk.revid ? ` (révision ${wk.revid})` : ""}`, url: wk.revid ? WIKI.rev + wk.revid : WIKI.url }, ...cecLinks],
    };
  }
  // 4. relais presse NON officiel (projection de The Petek d'après le dépouillement de la CEC)
  if (live.press) {
    const pr = live.press;
    sources.press = { key: "press", label: `Projection ${PRESS.name} (relais non officiel · dépouillement CEC de ${pr.as_of || "?"}, heure d’Israël)`, chip: "Non officiel · relais presse", cls: "nonoff", seats: pr.seats, share: pr.counted_pct / 100, valid: pr.valid, asOf: pr.as_of, stations: pr.stations,
      links: [{ label: `${PRESS.name} (relais non officiel)`, url: PRESS.url }, ...cecLinks] };
  }
  // 5. rien de publié : hémicycle vide, jamais un chiffre qui ne vient pas de la CEC (ou, à défaut, d'une source étiquetée)
  sources.none = { key: "none", label: "En attente des premiers chiffres de la CEC", chip: "En attente", cls: "nonoff", seats: {}, links: cecLinks };

  // base par défaut : officiel > Wikipédia (si elle n'a pas moins de bulletins que les totaux CEC) > totaux CEC ; le relais presse ne passe
  // devant que s'il est plus avancé que cette base
  const base = sources.wiki && (!sources.cec || sources.wiki.valid >= cecTotals.valid) ? "wiki" : sources.cec ? "cec" : null;
  const baseValid = base === "wiki" ? sources.wiki.valid : base === "cec" ? cecTotals.valid : 0;
  let def = base || (sources.press ? "press" : "none");
  if (sources.press && sources.press.valid > baseValid) def = "press";
  if (sources.official) def = "official";
  const chosen = state.seatSource && sources[state.seatSource] ? state.seatSource : def;

  // voix affichées (tableau, chiffres clés, analyse) : celles de la CEC, sauf si Wikipédia est choisie ET plus avancée
  const useWiki = chosen === "wiki" && (!cecTotals || wk.valid > cecTotals.valid);
  const totals = useWiki ? { eligible: wk.eligible, voters: wk.valid + wk.invalid, valid: wk.valid, invalid: wk.invalid } : cecTotals;
  const lists = useWiki ? wkLists : cecLists;
  const voteSource = useWiki ? sources.wiki : sources.cec || null;

  return { live, manual, totals, cecTotals, lists, voteSource, sources, def, chosen, seats: sources[chosen].seats, active: sources[chosen] };
}

/* =====================================================================
   État de la soirée, pastille « page actualisée », chip de source
   ===================================================================== */
function phase() {
  const live = model.live;
  if (live.status === "final") return "final";
  if (model.totals || model.active.key === "press" || model.active.key === "wiki") return "counting";
  return Date.now() < POLLS_CLOSE.getTime() ? "voting" : "closed";
}

// d'où viennent les chiffres de la base active (pastille d'état)
function sourceNow() {
  const a = model.active, at = a.asOf ? ` (relevé de ${esc(a.asOf)}, heure d’Israël)` : "";
  if (a.key === "wiki") return `source : ${WIKI.name}, d’après le tableau de la CEC${at}`;
  if (a.key === "press") return `source : ${esc(PRESS.name)}, relais non officiel du dépouillement de la CEC${at}`;
  return "résultats partiels de la CEC, susceptibles d’évoluer";
}

// [phase, [classe, titre, détail]] : la pastille d'état est la même sur toutes les pages
function phaseInfo() {
  const ph = phase();
  const map = {
    voting: ["wait", "Bureaux de vote ouverts", `fermeture dans <b class="num" id="cd">—</b>`],
    closed: ["wait", "Bureaux fermés", "dépouillement en attente — les premiers chiffres arrivent"],
    counting: ["", "Dépouillement en cours", sourceNow()],
    final: ["", "Résultats publiés", "chiffres définitifs de la CEC"],
  };
  return { ph, info: map[ph] };
}
function renderStatusRow(el) {
  const [cls, a, b] = phaseInfo().info;
  const demo = state.demo ? ` <span class="src-chip nonoff">DÉMO · chiffres simulés</span>` : "";
  el.innerHTML = `<div class="statusrow"><span class="pill ${state.demo ? "demo" : cls}"><span class="dot"></span><span><b>${a}</b> · ${b}</span></span>${demo}<button type="button" class="livechip" id="liveChip" title="Actualiser maintenant" aria-label="Actualiser maintenant"></button></div>`;
  tickLive();
}

function tickLive() {
  const el = $("#liveChip");
  if (!el) return;
  const t0 = Date.parse((state.live || {}).checked_at);
  const age = Number.isFinite(t0) ? Math.max(0, Math.round((Date.now() - t0) / 1000)) : null;
  const ago = (s) => (s < 90 ? `${s} s` : s < 5400 ? `${Math.round(s / 60)} min` : `${Math.round(s / 3600)} h`);
  const late = age != null && age > 300;                       // le collecteur republie au moins toutes les ~2 min
  const next = Math.max(0, Math.ceil((state.nextAt - Date.now()) / 1000));
  let main;
  if (state.loading) main = `<span class="spin" aria-hidden="true"></span><b>Actualisation…</b>`;
  else if (state.ok === false) main = `⚠ <b>Connexion impossible</b> · nouvel essai dans ${next} s`;
  else if (state.lastTry) main = `<span class="spin idle" aria-hidden="true">↻</span>Page actualisée à <b>${hhmmss(new Date(state.lastTry))}</b> · prochaine dans <b class="num">${next} s</b>`;
  else main = "Chargement…";
  const data = state.demo ? "Données simulées" : age == null ? "Aucune donnée reçue" : `Dernier relevé il y a <b>${ago(age)}</b>${late ? " — en retard" : ""}`;
  el.className = "livechip" + (late || state.ok === false ? " warn" : "");
  el.innerHTML = `<span class="l1">${main}</span><span class="l2">${data}</span>`;
}
function tick() { tickCountdown(); tickLive(); }

function tickCountdown() {
  const el = $("#cd");
  if (!el) return;
  const ms = Math.max(0, POLLS_CLOSE - Date.now());
  const h = Math.floor(ms / 3.6e6), m = Math.floor((ms % 3.6e6) / 6e4), s = Math.floor((ms % 6e4) / 1e3);
  el.textContent = [h, m, s].map(x => String(x).padStart(2, "0")).join(":");
  if (ms === 0) render();
}

function chipFor(src) { return `<span class="src-chip ${src.cls}">${esc(src.chip)}</span>`; }

/* =====================================================================
   Menu, pied de page, thème
   ===================================================================== */
const NAV = [
  { id: "home", label: "Accueil", href: "index.html" },
  { id: "coalitions", label: "Coalitions", href: "index.html#coalitions" },
  { id: "resultats", label: "Résultats bruts", href: "resultats.html" },
  { id: "analyse", label: "2026 vs 2022", href: "analyse.html" },
  { id: "actus", label: "À lire", href: "index.html#actus" },
  { id: "sources", label: "Sources", href: "index.html#sources" },
];
function mountChrome(pageId) {
  const local = pageId === "home";                       // sur l'accueil, les ancres restent dans la page
  const href = (h) => (local && h.startsWith("index.html#") ? h.slice("index.html".length) : h);
  const head = $("#siteHeader");
  if (head) head.innerHTML = `<div class="wrap">
    <a class="brand" href="${local ? "#top" : "index.html"}" aria-label="IsraPoll — accueil">
      <svg viewBox="0 0 64 64" aria-hidden="true"><rect width="64" height="64" rx="15" fill="var(--card)" stroke="var(--line)"/><path d="M10 46a22 22 0 0 1 44 0" fill="none" stroke="var(--accent)" stroke-width="6" stroke-linecap="round"/><path d="M19 46a13 13 0 0 1 26 0" fill="none" stroke="var(--accent2)" stroke-width="6" stroke-linecap="round"/></svg>
      IsraPoll
    </a>
    <nav class="nav" aria-label="Pages et sections">${NAV.map(n => `<a href="${esc(href(n.href))}"${n.id === pageId ? ' class="on" aria-current="page"' : ""}>${esc(n.label)}</a>`).join("")}</nav>
    <button class="icon-btn" id="theme" title="Changer de thème" aria-label="Changer de thème">◐</button>
  </div>`;
  const foot = $("#siteFooter");
  if (foot) foot.innerHTML = `<div class="wrap"><div class="cols">
      <div><h4>IsraPoll</h4>Projet indépendant, <b>non affilié</b> à la Commission électorale centrale ni à un parti. Code libre (MIT)&nbsp;: <a href="https://github.com/${REPO}" rel="noopener">github.com/${REPO}</a>. Les contributions sont bienvenues.</div>
      <div><h4>Vérifier soi-même</h4><ul><li><a href="${CEC.national}" rel="noopener">Résultats nationaux (CEC)</a></li><li><a href="https://votes26.bechirot.gov.il/cityresults" rel="noopener">Par localité (CEC)</a></li><li><a href="https://www.bechirot.gov.il/" rel="noopener">bechirot.gov.il</a></li><li><a href="${WIKI.url}" rel="noopener">Article Wikipédia (voix par liste)</a></li></ul></div>
      <div><h4>Cette page</h4><div id="footStatus"></div></div>
    </div></div>`;
  const th = store.get("theme"); if (th) document.documentElement.dataset.theme = th;
}
function toggleTheme() {
  const cur = document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  const next = cur === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next; store.set("theme", next);
}

function renderFoot() {
  const l = model.live;
  const t0 = Date.parse(l.checked_at);
  const age = Number.isFinite(t0) ? Math.max(0, Math.round((Date.now() - t0) / 1000)) : null;
  const stale = age != null && age > 300;
  $("#footStatus").innerHTML = age != null
    ? `Dernier relevé du collecteur : <b>${hhmmss(l.checked_at)}</b> (il y a ${age < 90 ? age + " s" : Math.round(age / 60) + " min"}). ${stale ? '<span style="color:var(--warn)">Le collecteur semble en pause — vérifie directement sur le site de la CEC.</span>' : "Actualisation automatique toutes les 20 s."} <button class="btn" id="refresh" style="margin-left:6px">Actualiser</button>`
    : `Données du collecteur indisponibles : aucun résultat à afficher. <button class="btn" id="refresh">Réessayer</button>`;
}

/* =====================================================================
   Rendu, actualisation, démarrage
   ===================================================================== */
let PAGE = { sections: [] };
// Chaque section s'affiche indépendamment : si l'une échoue, les autres restent lisibles et un bandeau le dit.
function render() {
  const errs = [];
  try { model = derive(); }
  catch (e) { console.error("derive", e); errs.push("données"); state.live = sanitizeLive({}); model = derive(); }
  [...PAGE.sections, ["pied de page", renderFoot]].forEach(([name, fn]) => {
    try { fn(); } catch (e) { console.error(name, e); errs.push(name); }
  });
  const box = $("#appError");
  if (box) box.innerHTML = errs.length
    ? `<div class="notice bad" style="margin-top:14px"><b>Une partie de la page n’a pas pu s’afficher</b> (${esc(errs.join(", "))}). Les résultats officiels restent consultables sur <a href="${CEC.national}" rel="noopener">le site de la CEC</a>.</div>` : "";
}

let inflight = null;
function refresh(force = false) {
  if (inflight) return inflight;                    // jamais deux relevés en parallèle
  state.loading = true; tickLive();
  inflight = (async () => {
    let ok = false;
    try { ok = await loadLive(force); } catch (e) { /* on garde l'état précédent */ }
    state.ok = ok; state.loading = false; state.lastTry = Date.now(); state.nextAt = state.lastTry + REFRESH_MS;
    render(); tick();
  })().finally(() => { inflight = null; });
  return inflight;
}

const App = {
  start(page) {
    PAGE = page;
    state.live = state.live || {};
    mountChrome(page.id);
    document.addEventListener("click", (e) => {
      const t = e.target.closest("button");
      if (!t) return;
      if (t.id === "refresh" || t.id === "liveChip") refresh(true);
      else if (t.id === "theme") toggleTheme();
    });
    if (page.start) page.start();
    render();
    tick();
    refresh();
    setInterval(tick, 1000);
    setInterval(() => { if (!document.hidden) refresh(); }, REFRESH_MS);
    document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
  },
};
