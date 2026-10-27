#!/usr/bin/env python3
"""Saisie de secours des totaux nationaux de la CEC dans data/manual.json (clé « cec »).

À utiliser quand le collecteur est bloqué par le défi anti-bot du site de la CEC (HTTP 202 vide) : on lit le tableau
sur https://votes26.bechirot.gov.il/nationalresults dans un navigateur et on le recopie ici. Les mêmes contrôles que le
collecteur s'appliquent (liste inconnue, totaux incohérents, somme des listes) : en cas d'erreur, rien n'est écrit.

  scripts/cec_manual.py --as-of 23:40 --eligible 7000000 --voters 1500000 --valid 1480000 \\
      likud=380000 yashar=350000 together=190000 ...        # identifiants de PARTIES (index.html) ou lettres de vote CEC
  scripts/cec_manual.py --clear                              # retire la saisie (le flux automatique reprend seul)

Ne touche ni au reste de manual.json ni à git : relire `git diff`, puis commit + push (le collecteur relit le fichier
depuis `main` à chaque tour, ~30 s).
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # le script est lancé avec -I : on ajoute explicitement son dossier
import fetch_cec  # noqa: E402

MANUAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "manual.json")
BLOCK = re.compile(r',?\s*"cec"\s*:.*(?=\n\}\s*$)', re.S)      # la clé « cec » est toujours la dernière du fichier


def number(text):
    digits = re.sub(r"[\s,._]", "", text)
    if not digits.isdigit():
        raise SystemExit(f"nombre illisible : {text!r}")
    return int(digits)


def write(path, cec):
    """Remplace (ou retire) la clé « cec », dernière du fichier : le reste de manual.json reste identique à l'octet près."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    json.loads(text)
    head = BLOCK.sub("", text).rstrip()                                 # sans l'ancienne saisie ni la virgule qui la précède
    if not head.endswith("}"):
        raise SystemExit(f"{path} : objet JSON attendu")
    head = head[:-1].rstrip()                                           # sans l'accolade finale
    body = "" if cec is None else ',\n  "cec": ' + json.dumps(cec, ensure_ascii=False, indent=2).replace("\n", "\n  ")
    out = f"{head}{body}\n}}\n"
    json.loads(out)                                                     # ne jamais écrire un fichier invalide
    with open(path, "w", encoding="utf-8") as f:
        f.write(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("votes", nargs="*", help="liste=voix (ex. likud=380000)")
    ap.add_argument("--as-of", default="", help="heure d'Israël du relevé lu sur le site de la CEC (affichée sur la page), ex. 23:40")
    ap.add_argument("--eligible", help="inscrits (בזב)")
    ap.add_argument("--voters", help="votants (מצביעים)")
    ap.add_argument("--valid", help="bulletins valides (כשרים)")
    ap.add_argument("--invalid", help="bulletins nuls (פסולים) ; par défaut votants − valides")
    ap.add_argument("--url", default=fetch_cec.HTML_URL)
    ap.add_argument("--clear", action="store_true", help="retire la saisie de secours")
    ap.add_argument("--file", default=MANUAL)
    a = ap.parse_args()

    if a.clear:
        write(a.file, None)
        print("saisie « cec » retirée")
        return
    if not (a.eligible and a.voters and a.valid and a.votes):
        ap.error("--eligible, --voters, --valid et au moins une liste (liste=voix) sont requis")
    votes = {}
    for item in a.votes:
        key, sep, n = item.partition("=")
        if not sep:
            ap.error(f"« {item} » : attendu liste=voix")
        if key in votes:
            ap.error(f"{key} saisi deux fois")
        votes[key] = number(n)
    totals = {"eligible": number(a.eligible), "voters": number(a.voters), "valid": number(a.valid)}
    if a.invalid:
        totals["invalid"] = number(a.invalid)
    cec = {"as_of": a.as_of, "url": a.url, "totals": totals, "votes": votes}
    try:
        res = fetch_cec.parse_manual_cec(cec)
    except ValueError as e:
        raise SystemExit(f"saisie refusée, rien n'a été écrit : {e}")
    write(a.file, cec)
    v, t = res["votes"], res["totals"]
    letters = {l: i for i, l in fetch_cec.PARTY_LETTERS.items()}
    print(f"saisie enregistrée : {t['valid']:,} bulletins valides, {t['voters']:,} votants ({100 * t['voters'] / t['eligible']:.1f} %), {sum(v.values()) / t['valid']:.1%} des voix réparties sur {len(v)} listes")
    for l, n in sorted(v.items(), key=lambda kv: -kv[1]):
        print(f"  {letters.get(l, l):<11} {n:>10,}  {n / t['valid']:6.2%}")
    print("puis : git diff data/manual.json && git commit -am 'Totaux CEC (saisie manuelle)' && git push")


if __name__ == "__main__":
    main()
