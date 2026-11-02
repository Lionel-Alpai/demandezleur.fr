# actu.py — le tiroir ACTU : déclarations verbatim des candidats et faits d'actualité, datés, sourcés, périssables.
"""
Fichiers : actu/AAAA-MM-JJ.json  {"jour", "entrees": [ {id, type: declaration|fait, candidat_id?, verbatim?|fait?, date, ou?,
           media, url, sources[{url, media, titre}], themes[], statut: verifie_auto|a_valider|valide|refuse, verifie_le, preuve} ]}
Servi à l'Arène seulement (fenêtre FENETRE_JOURS), comme pièces de type « actu » ; une déclaration est ancrée COMME DÉCLARATION.
"""
import json
import re
from datetime import date, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent / "actu"
STATUTS_SERVIS = {"verifie_auto", "valide"}
FENETRE_JOURS = 90  # prototype : 90 j (recherche sans filtre de date) ; en prod, 14 j avec collecte quotidienne


def charger(fenetre_jours: int = FENETRE_JOURS) -> list:
    BASE.mkdir(exist_ok=True)
    limite = (date.today() - timedelta(days=fenetre_jours)).isoformat()
    out = []
    for p in sorted(BASE.glob("*.json")):
        if p.stem < limite:
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for e in d.get("entrees", []):
            if e.get("statut") not in STATUTS_SERVIS or not (e.get("verbatim") or e.get("fait")):
                continue
            if e.get("date") and len(e["date"]) >= 10 and e["date"][:10] < limite:
                continue  # la date de la déclaration/du fait compte, pas celle de la collecte
            out.append(dict(e, jour=d.get("jour", p.stem)))
    out.sort(key=lambda e: e.get("date") or e.get("jour", ""), reverse=True)
    return out


def _texte(e: dict) -> str:
    return (e.get("verbatim") or e.get("fait") or "") + " " + " ".join(e.get("themes") or [])


def pieces_pour(sujet: str, orateur: dict, adversaires: list, requete_adverse: str = "", max_decl: int = 3, max_faits: int = 2) -> tuple:
    """(texte_prompt, preuves) : déclarations récentes des ADVERSAIRES présents (priorité) et de l'orateur, faits d'actualité — pertinents au sujet."""
    import dossiers as _d
    entrees = charger()
    if not entrees:
        return "", []
    ids_adv = {a["id"]: a["nom"] for a in adversaires}
    decl_adv = [e for e in entrees if e.get("type") == "declaration" and e.get("candidat_id") in ids_adv and _d.pertinent(_texte(e), e.get("themes"), sujet, requete_adverse)]
    decl_moi = [e for e in entrees if e.get("type") == "declaration" and e.get("candidat_id") == orateur["id"] and _d.pertinent(_texte(e), e.get("themes"), sujet, requete_adverse)]
    faits = [e for e in entrees if e.get("type") == "fait" and _d.pertinent(_texte(e), e.get("themes"), sujet, requete_adverse)]
    if not (decl_adv or decl_moi or faits):
        return "", []
    lignes, preuves = [], []
    for e in decl_adv[:max_decl]:
        nom = ids_adv[e["candidat_id"]]
        lignes.append(f"— DÉCLARATION de {nom}, {e.get('date', '')}{(' (' + e['ou'] + ')') if e.get('ou') else ''} : « {e['verbatim']} » — source : {e.get('media', '')}")
        preuves.append({"type": "actu", "candidat_id": e["candidat_id"], "titre": f"Déclaration de {nom}", "page": e.get("date", ""), "theme": ", ".join(e.get("themes") or [])[:60],
                        "extrait": e["verbatim"], "texte_integral": e["verbatim"], "url": e.get("url", ""), "orateur": e.get("media", ""), "date_lisible": e.get("date", "")})
    for e in decl_moi[:1]:
        lignes.append(f"— TA PROPRE DÉCLARATION, {e.get('date', '')} : « {e['verbatim']} » (tu peux la reprendre, tu ne la contredis pas)")
    for e in faits[:max_faits]:
        lignes.append(f"— FAIT D'ACTUALITÉ, {e.get('date', '')} : {e['fait']} — sources : {e.get('media', '')}")
        preuves.append({"type": "actu", "candidat_id": orateur["id"], "titre": "Fait d'actualité", "page": e.get("date", ""), "theme": ", ".join(e.get("themes") or [])[:60],
                        "extrait": e["fait"], "texte_integral": e["fait"], "url": e.get("url", ""), "orateur": e.get("media", ""), "date_lisible": e.get("date", "")})
    texte = ("\n\nPIÈCES D'ACTUALITÉ (derniers jours, verbatims et faits vérifiés — tu peux les citer telles quelles, avec leur date ; une déclaration d'un adversaire "
             "se lui oppose comme DÉCLARATION (« vous avez déclaré le … que … »), jamais comme un fait établi sur le fond) :\n" + "\n".join(lignes))
    return texte, preuves


def sujets_chauds(n: int = 6) -> list:
    """Thèmes les plus présents dans l'actu récente → puces « Ça chauffe cette semaine »."""
    from collections import Counter
    c = Counter()
    for e in charger():
        for t in (e.get("themes") or [])[:4]:
            c[t.strip().lower()] += 1
    return [{"theme": t, "n": k} for t, k in c.most_common(n)]
