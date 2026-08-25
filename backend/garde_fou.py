# garde_fou.py — Arène : aucune affirmation sur un adversaire sans pièce.
"""
A.2  verifier_faits()  : garde DÉTERMINISTE (regex + faits.json) — bilan gouvernemental prêté à
                         qui n'a jamais gouverné, votes prêtés à qui n'est pas député.
A.3  juger()           : juge en MONDE CLOS (modèle, température 0) — chaque affirmation sur un
                         adversaire doit être ancrée dans ses pièces, ses faits, la pièce Assemblée
                         ou l'historique ; sinon la phrase est retirée.
     generer_replique_validee() : génération → A.2 → A.3 → retrait → régénération (≤ 2) → repli.
Testable sans FastAPI (voir tests/test_garde_fou.py).
"""
import json
import logging
import re
import time
import unicodedata
from pathlib import Path

import llm

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent
PROMPT_JUGE = BASE_DIR / "prompts" / "debat" / "juge_arene.txt"
REPLI = "Sur ce point, je vous renvoie à mon programme."
MAX_REGENERATIONS = 2


def sans_accents(t: str) -> str:
    return unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()


def decouper_phrases(texte: str) -> list:
    """Découpe en phrases sur . ! ? … suivis d'une majuscule ou d'un guillemet ouvrant."""
    t = re.sub(r"\s+", " ", (texte or "").strip())
    if not t:
        return []
    parts = re.split(r"(?<=[.!?…])\s+(?=[A-ZÀ-ÝÉÈÊÂÎÔÛ«\"“])", t)
    return [p.strip() for p in parts if p.strip()]


def _noms_cibles(adversaires: list) -> dict:
    """id -> variantes de nom (nom complet, nom de famille), sans accents."""
    out = {}
    for a in adversaires:
        nom = a.get("nom", "")
        variantes = {sans_accents(nom)}
        morceaux = nom.split()
        if len(morceaux) >= 2:
            variantes.add(sans_accents(" ".join(morceaux[1:])))  # « Le Pen », « Dupont-Aignan »
            variantes.add(sans_accents(morceaux[-1]))
        out[a["id"]] = {v for v in variantes if len(v) >= 3}
    return out


def cibles_dans_phrase(phrase: str, adversaires: list, cible_par_defaut: str = None) -> list:
    """Adversaires visés par une phrase : nommés, sinon « vous/votre » → cible par défaut."""
    p = sans_accents(phrase)
    noms = _noms_cibles(adversaires)
    cibles = [cid for cid, vs in noms.items() if any(re.search(r"\b" + re.escape(v) + r"\b", p) for v in vs)]
    if not cibles and cible_par_defaut and re.search(r"\b(vous|votre|vos)\b", p):
        cibles = [cible_par_defaut]
    return cibles


# A.2 — motifs déterministes
MOTIFS_GOUVERNEMENT = re.compile(
    r"\b(votre|vos|ton|tes)\s+(gouvernement|gouvernements|majorite|majorites|bilan|ministere|ministeres|quinquennat|passage au pouvoir|annees? au pouvoir|annees? a matignon|annees? a bercy)\b"
    r"|\bquand vous etiez\s+(ministre|premier ministre|premiere ministre|au pouvoir|au gouvernement|a matignon|a bercy)\b"
    r"|\bvous avez (gouverne|dirige le pays|ete ministre|ete premier ministre|ete premiere ministre)\b"
    r"|\bsous votre (gouvernement|mandat|ministere|quinquennat)\b"
    r"|\bpendant que vous etiez (au pouvoir|au gouvernement|a matignon|a bercy|ministre)\b"
)
MOTIFS_VOTE = re.compile(r"\bvous avez vote\b|\bvotre vote\b|\bvous n'?avez pas vote\b|\bvous avez refuse de voter\b|\bvous refusez de voter\b|\ba l'assemblee,? vous\b")


def verifier_faits(texte: str, adversaires: list, faits: dict, cible_par_defaut: str = None) -> tuple:
    """Retire les phrases qui prêtent à un adversaire un bilan gouvernemental ou un vote qu'il ne peut pas avoir.
    Retourne (texte_nettoye, revisions[{type:'faits', phrase, cible, raison}])."""
    phrases = decouper_phrases(texte)
    gardees, revisions = [], []
    derniere_cible = cible_par_defaut
    for ph in phrases:
        cibles = cibles_dans_phrase(ph, adversaires, derniere_cible)
        if cibles:
            derniere_cible = cibles[0]
        p = sans_accents(ph)
        retiree = False
        for cid in cibles:
            f = faits.get(cid) or {}
            nom = next((a["nom"] for a in adversaires if a["id"] == cid), cid)
            if MOTIFS_GOUVERNEMENT.search(p) and not f.get("a_gouverne", False):
                revisions.append({"type": "faits", "phrase": ph, "cible": cid, "raison": f"{nom} n’a jamais été membre d’un gouvernement : aucun bilan gouvernemental ne peut lui être prêté."})
                retiree = True
                break
            if MOTIFS_VOTE.search(p) and not f.get("depute", False):
                revisions.append({"type": "faits", "phrase": ph, "cible": cid, "raison": f"{nom} n’est pas député(e) : aucun vote à l’Assemblée ne peut lui être prêté."})
                retiree = True
                break
        if not retiree:
            gardees.append(ph)
    return " ".join(gardees), revisions


# A.3 — juge en monde clos
def _formater_pieces(preuves: list) -> str:
    lignes = []
    for p in preuves:
        if p.get("type") == "adversaire":
            lignes.append(f"[{p.get('candidat_id')}] {p.get('titre', '')} {('(' + str(p.get('page')) + ')') if p.get('page') else ''} : « {p.get('extrait', '')} »")
    return "\n".join(lignes) or "(aucune pièce sur les adversaires)"


def _formater_faits(adversaires: list, faits: dict) -> str:
    lignes = []
    for a in adversaires:
        f = faits.get(a["id"]) or {}
        lignes.append(f"[{a['id']}] {a['nom']} : " + ("a été membre d'un gouvernement (" + ", ".join(f.get("fonctions_passees") or []) + ")" if f.get("a_gouverne") else "n'a jamais été au gouvernement")
                      + " ; " + ("député(e) en exercice" if f.get("depute") else "pas député(e)") + (" ; mandats : " + ", ".join(f.get("mandats")) if f.get("mandats") else ""))
    return "\n".join(lignes) or "(aucun)"


def _formater_piece_assemblee(preuves: list) -> str:
    for p in preuves:
        if p.get("type") == "piece":
            return f"{p.get('orateur', '')}, {p.get('date_lisible', '')} : « {p.get('extrait', '')} »"
    return "(aucune)"


def _formater_historique(historique: list, adversaires: list) -> str:
    ids = {a["id"] for a in adversaires}
    lignes = []
    for tour in historique or []:
        for i in tour.get("interventions", []):
            if i.get("candidat_id") in ids:
                lignes.append(f"[{i.get('candidat_id')}] {i.get('texte', '')[:400]}")
    return "\n".join(lignes) or "(rien encore)"


def _extraire_json(txt: str) -> dict:
    try:
        return json.loads(txt)
    except Exception:
        pass
    try:
        return json.loads(txt[txt.find("{"): txt.rfind("}") + 1])
    except Exception:
        return {}


async def juger(texte: str, orateur: dict, adversaires: list, preuves: list, faits: dict, historique: list, cle_demo) -> list:
    """Affirmations non ancrées : [{type:'juge', phrase, cible, raison}]. Vide en démo ou si le juge est muet."""
    if not adversaires or not texte.strip():
        return []
    prompt = (PROMPT_JUGE.read_text(encoding="utf-8")
              .replace("{orateur}", f"{orateur.get('nom', '')} ({orateur.get('id', '')})")
              .replace("{adversaires}", ", ".join(f"{a['id']} → {a['nom']}" for a in adversaires))
              .replace("{pieces}", _formater_pieces(preuves))
              .replace("{faits}", _formater_faits(adversaires, faits))
              .replace("{piece}", _formater_piece_assemblee(preuves))
              .replace("{historique}", _formater_historique(historique, adversaires))
              .replace("{replique}", texte))
    debut = time.time()
    txt = await llm.completer_texte([{"role": "user", "content": prompt}], cle_demo=cle_demo, max_tokens=600, temperature=0,
                                    extra={"response_format": {"type": "json_object"}})
    d = _extraire_json(txt)
    out = []
    for a in d.get("affirmations", []) if isinstance(d, dict) else []:
        if isinstance(a, dict) and a.get("ancree") is False and a.get("phrase"):
            out.append({"type": "juge", "phrase": str(a["phrase"]), "cible": str(a.get("cible", "")), "raison": str(a.get("raison", ""))[:200]})
    logger.info("juge arène : %d non ancrée(s) en %.1fs", len(out), time.time() - debut)
    return out


def _retirer_phrases(texte: str, revisions: list) -> str:
    """Retire les phrases contenant une affirmation non ancrée (appariement souple)."""
    phrases = decouper_phrases(texte)
    mauvaises = [sans_accents(r["phrase"]) for r in revisions if r.get("phrase")]
    gardees = []
    for ph in phrases:
        p = sans_accents(ph)
        if any(m and (m in p or p in m or _recouvrement(m, p) > 0.6) for m in mauvaises):
            continue
        gardees.append(ph)
    return " ".join(gardees)


def _recouvrement(a: str, b: str) -> float:
    wa, wb = set(re.findall(r"\w{4,}", a)), set(re.findall(r"\w{4,}", b))
    return len(wa & wb) / max(1, min(len(wa), len(wb)))


async def generer_replique_validee(messages: list, *, params: dict, orateur: dict, adversaires: list, preuves: list,
                                   faits: dict, historique: list, cle_demo, juger_actif: bool = True,
                                   cible_par_defaut: str = None) -> tuple:
    """(texte_final, revisions, meta). meta = {regenerations, fallback, brut, usage}."""
    usage = {"in": 0, "out": 0}

    def _cb(p, c):
        usage["in"] += p; usage["out"] += c

    async def _generer(msgs, cle):
        morceaux = []
        async for d in llm.completer(msgs, cle_demo=cle, usage_cb=_cb, **params):
            morceaux.append(d)
        return "".join(morceaux)

    brut = await _generer(messages, cle_demo)
    texte, revisions = brut, []
    regenerations, fallback = 0, False
    while True:
        texte_nettoye, rev_faits = verifier_faits(texte, adversaires, faits, cible_par_defaut)
        rev_juge = []
        if juger_actif and llm.MODE != "demo":
            try:
                rev_juge = await juger(texte_nettoye, orateur, adversaires, preuves, faits, historique, tuple(cle_demo) + ("juge", regenerations))
            except Exception:
                logger.warning("juge arène en échec — garde déterministe seule", exc_info=True)
        texte_final = _retirer_phrases(texte_nettoye, rev_juge) if rev_juge else texte_nettoye
        revisions = rev_faits + rev_juge
        nb_avant, nb_apres = len(decouper_phrases(texte)), len(decouper_phrases(texte_final))
        trop_ampute = nb_apres < 2 or (nb_avant and (nb_avant - nb_apres) / nb_avant > 0.4)
        if not revisions or not trop_ampute or regenerations >= MAX_REGENERATIONS:
            break
        regenerations += 1
        rappel = ("Ta précédente prise de parole contenait des affirmations non fondées sur tes adversaires : "
                  + " / ".join("« " + r["phrase"][:160] + " »" for r in revisions[:3])
                  + ". Réécris-la ENTIÈREMENT en ne t'appuyant que sur les PIÈCES fournies (leur programme, les faits, la pièce au dossier). Pas de chiffre, de vote ni de bilan hors pièces.")
        texte = await _generer(messages + [{"role": "assistant", "content": texte}, {"role": "user", "content": rappel}], tuple(cle_demo) + ("regen", regenerations))
    if revisions and len(decouper_phrases(texte_final)) < 2:
        texte_final = (texte_final + " " + REPLI).strip()
        fallback = True
    return texte_final, revisions, {"regenerations": regenerations, "fallback": fallback, "brut": brut, "usage": usage}
