/*
 * Résultats officiels de la 25e Knesset (élections du 1er novembre 2022), tels que publiés par la Commission électorale centrale :
 * https://votes25.bechirot.gov.il/nationalresults  (voix = somme du fichier par localité, qui reproduit exactement le tableau national).
 * Les listes de moins de 1 % sont regroupées dans `otherVotes`. Fonctionne dans le navigateur (RESULTS_2022) et sous Node (require).
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.RESULTS_2022 = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  return {
    election: "25e Knesset · 1er novembre 2022",
    source: { name: "Commission électorale centrale — résultats nationaux 2022", url: "https://votes25.bechirot.gov.il/nationalresults" },
    totals: { eligible: 6788804, voters: 4794593, valid: 4764742, invalid: 29851 },
    lists: {
    "מחל": { id: "likud22", fr: "Likoud", votes: 1115336, seats: 32 },
    "פה": { id: "ya22", fr: "Yesh Atid", votes: 847435, seats: 24 },
    "ט": { id: "rz22", fr: "Sionisme religieux – Otzma Yehudit – Noam (liste commune)", votes: 516470, seats: 14 },
    "כן": { id: "nu22", fr: "Union nationale (Gantz – Sa’ar – Eisenkot)", votes: 432482, seats: 12 },
    "שס": { id: "shas22", fr: "Shas", votes: 392964, seats: 11 },
    "ג": { id: "utj22", fr: "Judaïsme unifié de la Torah", votes: 280194, seats: 7 },
    "ל": { id: "yb22", fr: "Israël Beiteinou", votes: 213687, seats: 6 },
    "עם": { id: "raam22", fr: "Ra’am", votes: 194047, seats: 5 },
    "ום": { id: "hadash22", fr: "Hadash–Ta’al", votes: 178735, seats: 5 },
    "אמת": { id: "labor22", fr: "Parti travailliste", votes: 175992, seats: 4 },
    "מרצ": { id: "meretz22", fr: "Meretz", votes: 150793, seats: 0 },
    "ד": { id: "balad22", fr: "Balad", votes: 138617, seats: 0 },
    "ב": { id: "jh22", fr: "Foyer juif (Ayelet Shaked)", votes: 56775, seats: 0 },
    },
    otherVotes: 71215,
  };
});
