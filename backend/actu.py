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
FENETRE_JOURS = 14  # fenêtre du tiroir (pièces) ; le bandeau « Ça chauffe » lit les fiches des FENETRE_BANDEAU derniers jours


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


def _non_citees(entrees: list, cle: str, textes_debat: list) -> list:
    """Écarte les pièces déjà citées dans le débat (dossiers.deja_cite, comme les pièces parlementaires) ;
    s'il ne reste rien, garde la moins citée : jamais une liste vide quand elle ne l'était pas."""
    import dossiers as _d
    if not entrees:
        return entrees
    nb = [sum(1 for t in textes_debat if _d.deja_cite(e.get(cle) or "", [t], seuil=4)) for e in entrees]
    libres = [e for e, c in zip(entrees, nb) if c == 0]
    return libres or [entrees[nb.index(min(nb))]]


def pieces_pour(sujet: str, orateur: dict, adversaires: list, requete_adverse: str = "", max_decl: int = 3, max_faits: int = 2, textes_debat: list = None) -> tuple:
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
    if textes_debat:  # une pièce déjà citée dans le débat n'est pas resservie (la moins citée si tout l'est)
        decl_adv = _non_citees(decl_adv, "verbatim", textes_debat)
        decl_moi = _non_citees(decl_moi, "verbatim", textes_debat)
        faits = _non_citees(faits, "fait", textes_debat)
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


FENETRE_BANDEAU = 7
REPLI_MIN = 3  # moins de REPLI_MIN fiches récentes : le bandeau se complète par le compteur d'étiquettes (ancien comportement)


def _date_fiche(f: dict) -> str:
    """Date ISO d'une fiche : sa date établie (JJ/MM/AAAA) sinon le jour de son tiroir."""
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", (f.get("date") or "").strip())
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return (f.get("jour") or f.get("verifie_le") or "")[:10]


def _nomme_candidat(titre: str) -> bool:
    """Le titre nomme un candidat de candidats.json (nom complet ou nom de famille) : règle mécanique de neutralité."""
    import actu_fiches
    t = actu_fiches.sans(titre)
    try:
        noms = [actu_fiches.sans(c["nom"]) for c in candidats_publics()]
    except Exception:
        return False
    return any(n in t or (len(n.split()[-1]) >= 4 and n.split()[-1] in t) for n in noms if n)


def _fiches_bandeau(n: int) -> list:
    """Fiches événement des FENETRE_BANDEAU derniers jours : doublons (≥ 2 clés communes) écartés, événements sans candidat nommé d'abord, date décroissante."""
    import actu_fiches
    _, fiches = actu_fiches.charger_fiches()
    limite = (date.today() - timedelta(days=FENETRE_BANDEAU)).isoformat()
    vues, gardees = [], []
    for f in sorted(fiches, key=lambda f: (_date_fiche(f), f.get("titre", "")), reverse=True):
        d = _date_fiche(f)
        if d < limite or not f.get("titre"):
            continue
        cles = set(f.get("cles") or [])
        if any(len(cles & k) >= 2 for k in vues):
            continue
        vues.append(cles)
        gardees.append((d, f["titre"]))
    neutres = [x for x in gardees if not _nomme_candidat(x[1])]
    nommes = [x for x in gardees if _nomme_candidat(x[1])]
    return [{"theme": t, "titre": t, "date": d} for d, t in (neutres + nommes)[:n]]


def sujets_chauds(n: int = 6) -> list:
    """Puces « Ça chauffe cette semaine » : les fiches événement récentes (titre mécanique, jamais reformulé) ; repli compteur si trop peu."""
    try:
        out = _fiches_bandeau(n)
    except Exception:
        out = []
    if len(out) < REPLI_MIN:
        out += _sujets_compteur(n)[: n - len(out)]
    return out


def _sujets_compteur(n: int = 6) -> list:
    """Thèmes les plus présents dans l'actu récente → puces « Ça chauffe cette semaine »."""
    from collections import Counter
    c = Counter()
    for e in charger():
        for t in (e.get("themes") or [])[:4]:
            t = t.strip().lower()
            if t in THEMES_GENERIQUES:
                continue
            c[t] += 1
    return [{"theme": t, "n": k} for t, k in c.most_common(n)]


THEMES_GENERIQUES = {"politique", "élection", "élections", "election", "elections", "présidentielle", "presidentielle",
                     "présidentielle 2027", "campagne", "primaire", "primaires"}
_CAND_CACHE = {"t": 0.0, "v": None}


def candidats_publics(ttl: int = 3600) -> list:
    """Liste publique {id, nom} des candidats (backend/candidats.json), cache memoire 1 h : source du collecteur ACTU."""
    import time
    if _CAND_CACHE["v"] is not None and time.time() - _CAND_CACHE["t"] < ttl:
        return _CAND_CACHE["v"]
    brut = json.loads((BASE.parent / "candidats.json").read_text(encoding="utf-8"))
    v = [{"id": c["id"], "nom": c["nom"]} for c in brut if c.get("id") and c.get("nom")]
    _CAND_CACHE["t"], _CAND_CACHE["v"] = time.time(), v
    return v
