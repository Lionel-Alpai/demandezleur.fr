#!/usr/bin/env python3
"""Juge d'effet mécanique des fiches de style (brique dl-style-fiche-pilote).

Pour chaque fiches/<id>.yaml : 8-12 traits ; chaque trait a >= 2 preuves retrouvées MOT POUR MOT
dans verbatims/<id>.*.jsonl, sur >= 2 lignes distinctes ; aucun trait ne parle du fond politique ;
4 réactions ; tics plafonnés ; 3-5 exemples réels et courts ; « ne fait jamais » vérifié en fréquence.
Sortie : une ligne VERT/ROUGE par fiche, code retour 1 si une fiche est rouge.
Une fiche VERTE est compilée en fiches/<id>.json (le backend n'a pas PyYAML : seule une fiche
validée par ce juge peut entrer dans un prompt).
Usage : python3 outils/verif_fiche.py [id ...]
"""
import json, re, sys
from pathlib import Path
import yaml

RACINE = Path(__file__).resolve().parent.parent
REACTIONS = 4
# Le fond appartient au corpus : un trait de STYLE ne nomme aucun thème de programme.
FOND = re.compile(r"immigr|retraite|impôt|fiscal|dette|europ|nucléaire|police|sécurit|islam|"
                  r"salaire|smic|chômage|santé|écolog|climat|agricult|guerre|ukrain|israël|gaza|"
                  r"\bnation|frontière|laïcit|vaccin|logement|école|justice|délinqu", re.I)


def norm(s):
    s = s.replace("’", "'").replace(" ", " ").replace(" ", " ")
    return re.sub(r"\s+", " ", s).strip().lower()


def charger(cid):
    lignes = []
    for f in sorted((RACINE / "verbatims").glob(f"{cid}.*.jsonl")):
        for l in f.open(encoding="utf-8"):
            lignes.append(norm(json.loads(l)["texte"]))
    return lignes


def lignes_contenant(lignes, extrait):
    e = norm(extrait)
    return {i for i, t in enumerate(lignes) if e in t}


def verifier(cid):
    fiche = yaml.safe_load((RACINE / "fiches" / f"{cid}.yaml").read_text(encoding="utf-8"))
    lignes = charger(cid)
    texte = " ".join(lignes)
    nb_mots = len(texte.split())
    fautes = []
    traits = fiche.get("traits") or []
    if not 8 <= len(traits) <= 12:
        fautes.append(f"{len(traits)} traits (attendu 8-12)")
    for t in traits:
        preuves = t.get("preuves") or []
        trouvees = [lignes_contenant(lignes, p) for p in preuves]
        absentes = [p for p, l in zip(preuves, trouvees) if not l]
        for p in absentes:
            fautes.append(f"trait {t['id']} : preuve introuvable « {p[:60]} »")
        vues = set().union(*trouvees) if trouvees else set()
        if len(preuves) - len(absentes) < 2 or len(vues) < 2:
            fautes.append(f"trait {t['id']} : moins de 2 preuves sur 2 lignes distinctes")
        if FOND.search(t.get("trait", "")):
            fautes.append(f"trait {t['id']} : parle du fond ({FOND.search(t['trait']).group(0)})")
    if len(fiche.get("reactions") or {}) != REACTIONS:
        fautes.append("réactions : 4 situations attendues")
    for r, txt in (fiche.get("reactions") or {}).items():
        if FOND.search(txt):
            fautes.append(f"réaction {r} : parle du fond")
    for tic in fiche.get("tics") or []:
        if not isinstance(tic.get("plafond_par_debat"), int) or tic["plafond_par_debat"] > 1:
            fautes.append(f"tic « {tic.get('forme')} » : plafond absent ou > 1 par débat")
    exemples = fiche.get("exemples") or []
    if not 3 <= len(exemples) <= 5:
        fautes.append(f"{len(exemples)} exemples (attendu 3-5)")
    for e in exemples:
        if not lignes_contenant(lignes, e):
            fautes.append(f"exemple introuvable « {e[:60]} »")
        if len(e.split()) > 30:
            fautes.append(f"exemple trop long ({len(e.split())} mots)")
    for j in fiche.get("ne_fait_jamais") or []:
        k = len(re.findall(j["motif"], texte, re.I))
        taux = 1000 * k / nb_mots
        if taux > j["max_pour_1000"]:
            fautes.append(f"« ne fait jamais » démenti : {j['quoi']} = {taux:.3f}/1000 > {j['max_pour_1000']}")
    return fautes, len(traits), nb_mots


def main():
    ids = sys.argv[1:] or sorted(p.stem for p in (RACINE / "fiches").glob("*.yaml"))
    rouge = False
    for cid in ids:
        fautes, n, mots = verifier(cid)
        if fautes:
            rouge = True
            print(f"ROUGE {cid} ({n} traits, {mots} mots)")
            for f in fautes:
                print(f"  - {f}")
        else:
            fiche = yaml.safe_load((RACINE / "fiches" / f"{cid}.yaml").read_text(encoding="utf-8"))
            (RACINE / "fiches" / f"{cid}.json").write_text(json.dumps(fiche, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"VERT {cid} : {n} traits prouvés, réactions, tics plafonnés, exemples réels ({mots} mots de corpus)")
    sys.exit(1 if rouge else 0)


if __name__ == "__main__":
    main()
