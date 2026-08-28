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

# ── Acte parlementaire prêté à un adversaire ────────────────────────────────
# MOTIFS_VOTE ci-dessus énumère des tournures EXACTES : « vous n'avez même pas
# daigné voter » ne matche aucune (les mots ne sont pas collés), et quand une
# tournure matche, être député(e) suffisait à laisser passer — on vérifiait que
# le vote était POSSIBLE, jamais qu'il avait EU LIEU. Le 28/08/2026 une réplique
# a ainsi reproché à Marine Le Pen de n'avoir pas voté une résolution du RN,
# alors qu'aucune des 8 pièces fournies ne mentionnait ni cette résolution ni
# 1968 : le fait était inventé de bout en bout.
#
# On détecte donc l'acte par un VERBE d'acte + un OBJET parlementaire dans la
# même phrase, et on exige que l'objet soit ANCRÉ dans une pièce réellement
# fournie au modèle. Un acte parlementaire est un fait vérifiable : s'il n'est
# dans aucune pièce, il n'est pas « non étayé », il est fabriqué — donc retiré,
# pas annoté.
VERBES_ACTE = re.compile(
    r"\b(?:vote|voter|votez|votent|votait|voterez|abstenu|abstenue|abstention|"
    r"depose|deposee|cosigne|cosignee|soutenu|soutenue|rejete|rejetee|adopte|adoptee|"
    r"ratifie|ratifiee|censure|censuree|approuve|approuvee|bloque|bloquee)\b")
OBJETS_PARLEMENTAIRES = re.compile(
    r"\b(resolution|resolutions|proposition de loi|projet de loi|amendement|amendements|"
    r"motion|motions|texte|textes|loi|lois|budget|budgets|scrutin|scrutins|"
    r"hemicycle|assemblee|senat|niche parlementaire)\b")
_MOTS_VIDES = {
    "vous", "votre", "vos", "nous", "notre", "avez", "avoir", "etes", "etre", "meme",
    "cette", "cettes", "leurs", "leur", "dans", "pour", "avec", "sans", "mais", "donc",
    "alors", "quand", "parce", "aujourd", "hui", "jamais", "toujours", "encore", "plus",
    "moins", "tout", "tous", "toute", "toutes", "faire", "fait", "dire", "pretendez",
    "pretend", "souvenez", "souvenir", "daigne", "daignez",
}


def _tokens_utiles(texte: str) -> set:
    """Mots distinctifs d'une phrase : ≥ 5 lettres, hors mots vides, hors verbes d'acte."""
    mots = re.findall(r"[a-z0-9]{5,}", sans_accents(texte))
    return {m for m in mots if m not in _MOTS_VIDES and not VERBES_ACTE.fullmatch(m)}


def acte_parlementaire_ancre(phrase: str, preuves: list, cible: dict) -> tuple:
    """(est_un_acte, est_ancre, objet). Un acte est ancré si l'objet parlementaire
    dont il parle se retrouve dans une pièce fournie : le nom de l'objet ET au moins
    un de ses qualificatifs distinctifs. Sinon la phrase affirme un fait que rien ne
    porte."""
    p = sans_accents(phrase)
    if not (VERBES_ACTE.search(p) and OBJETS_PARLEMENTAIRES.search(p)):
        return False, True, None
    objet = OBJETS_PARLEMENTAIRES.search(p).group(0)
    pieces = sans_accents(" ".join(
        (x.get("texte_integral") or x.get("extrait") or "") + " " + (x.get("titre") or "")
        for x in (preuves or [])))
    # Le nom de la cible et de son parti ne sont pas des qualificatifs de l'objet.
    bruit = _tokens_utiles((cible.get("nom") or "") + " " + (cible.get("parti") or ""))
    qualificatifs = _tokens_utiles(phrase) - bruit - {objet}
    if not qualificatifs:
        return True, False, objet
    ancres = {q for q in qualificatifs if q in pieces}
    return True, (objet in pieces and len(ancres) >= 1), objet


def reproche_a_son_propre_camp(phrase: str, cible: dict) -> bool:
    """Reprocher à quelqu'un de n'avoir pas soutenu un texte de SON PROPRE parti est
    incohérent par construction — et la donnée est dans candidats.json, sous les yeux
    du modèle. Cas du 28/08 : « Madame Le Pen, vous n'avez pas voté la résolution RN »."""
    p = sans_accents(phrase)
    if not re.search(r"\bn'?(?:avez|a|ont|aviez)\b|\brefus|\bpas\b", p):
        return False
    parti = cible.get("parti") or ""
    # Le sigle est rarement écrit tel quel dans candidats.json : le parti y figure
    # en toutes lettres (« Rassemblement National »), alors qu'une réplique dit
    # « la résolution RN ». On accepte donc les deux formes — le sigle écrit
    # explicitement, ET celui reconstruit à partir des initiales.
    sigles = set(re.findall(r"[A-Z]{2,}", parti))
    initiales = "".join(m[0] for m in re.findall(r"\b[A-ZÀ-Ý][\w'-]*", parti))
    if len(initiales) >= 2:
        sigles.add(initiales)
    mots = _tokens_utiles(parti)                                    # rassemblement, national…
    dit_son_parti = any(re.search(r"\b" + re.escape(sans_accents(s)) + r"\b", p) for s in sigles) \
        or (len(mots) > 0 and all(m in p for m in mots))
    return dit_son_parti and bool(OBJETS_PARLEMENTAIRES.search(p))


def verifier_faits(texte: str, adversaires: list, faits: dict, cible_par_defaut: str = None,
                   preuves: list = None) -> tuple:
    """Retire les phrases qui prêtent à un adversaire un bilan gouvernemental, un vote
    qu'il ne peut pas avoir, ou un ACTE PARLEMENTAIRE que rien dans les pièces ne porte.
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
            adv = next((a for a in adversaires if a["id"] == cid), {})
            if reproche_a_son_propre_camp(ph, adv):
                revisions.append({"type": "faits", "phrase": ph, "cible": cid,
                                  "raison": f"Incohérent : on reproche à {nom} de n’avoir pas soutenu un texte de son propre parti ({adv.get('parti', '')})."})
                retiree = True
                break
            est_acte, ancre, objet = acte_parlementaire_ancre(ph, preuves, adv)
            if est_acte and not ancre:
                revisions.append({"type": "faits", "phrase": ph, "cible": cid,
                                  "raison": f"Acte parlementaire prêté à {nom} ({objet}) qu’aucune pièce fournie ne mentionne : un vote est un fait vérifiable, il ne s’affirme pas sans pièce."})
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
            lignes.append(f"[{p.get('candidat_id')}] PROGRAMME {p.get('titre', '')} {('(' + str(p.get('page')) + ')') if p.get('page') else ''} : « {p.get('texte_integral') or p.get('extrait', '')} »")
        elif p.get("type") == "dossier":
            lignes.append(f"[{p.get('candidat_id')}] FAIT VÉRIFIÉ ({p.get('titre', '')}, {p.get('date_lisible', '')}) : {p.get('texte_integral') or p.get('extrait', '')}")
        elif p.get("type") == "actu":
            lignes.append(f"[{p.get('candidat_id')}] ACTUALITÉ VÉRIFIÉE ({p.get('titre', '')}, {p.get('date_lisible', '')}, {p.get('orateur', '')}) : « {p.get('texte_integral') or p.get('extrait', '')} »")
        elif p.get("type") == "reproche":
            lignes.append(f"[{p.get('candidat_id')}] REPROCHE DOCUMENTÉ (ce que le camp de l'orateur dit publiquement de lui, pas un fait) : {p.get('texte_integral') or p.get('extrait', '')}")
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
            return f"{p.get('orateur', '')}, {p.get('date_lisible', '')} : « {p.get('texte_integral') or p.get('extrait', '')} »"
    return "(aucune)"


def _formater_historique(historique: list, adversaires: list) -> str:
    ids = {a["id"] for a in adversaires}
    lignes = []
    for tour in historique or []:
        for i in tour.get("interventions", []):
            if i.get("candidat_id") in ids:
                lignes.append(f"[{i.get('candidat_id')}] {i.get('texte', '')[:900]}")
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
    sans_extrait = [a for a in adversaires if not any(p.get("type") == "adversaire" and p.get("candidat_id") == a["id"] for p in preuves)]
    pieces_txt = _formater_pieces(preuves) + "".join(f"\n[{a['id']}] PROGRAMME : aucun extrait sur ce sujet — dire que son programme n'en parle pas est ANCRÉ." for a in sans_extrait)
    prompt = (PROMPT_JUGE.read_text(encoding="utf-8")
              .replace("{orateur}", f"{orateur.get('nom', '')} ({orateur.get('id', '')})")
              .replace("{adversaires}", ", ".join(f"{a['id']} → {a['nom']}" for a in adversaires))
              .replace("{pieces}", pieces_txt)
              .replace("{faits}", _formater_faits(adversaires, faits))
              .replace("{piece}", _formater_piece_assemblee(preuves))
              .replace("{historique}", _formater_historique(historique, adversaires))
              .replace("{replique}", texte))
    debut = time.time()
    txt = await llm.completer_texte([{"role": "user", "content": prompt}], cle_demo=cle_demo, max_tokens=600, temperature=0,
                                    extra={"response_format": {"type": "json_object"}})
    d = _extraire_json(txt)
    out = []
    ids_adv = {x["id"] for x in adversaires}
    for a in d.get("affirmations", []) if isinstance(d, dict) else []:
        cible = str(a.get("cible", "")).strip().lower() if isinstance(a, dict) else ""
        if cible in (str(orateur.get("id", "")).lower(), "orateur", "moi", "soi", "lui-meme", "lui-même", "self") or (cible and cible not in ids_adv and cible != "sujet"):
            continue  # jamais ce que l'orateur dit de lui-même ; cibles inconnues ignorées
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
    """(texte_final, revisions, annotations, meta).
    - revisions   : phrases FAUSSES par construction (A.2), RETIRÉES du texte, conservées pour affichage replié.
    - annotations : affirmations NON ÉTAYÉES (A.3), LAISSÉES dans le texte, à marquer (astérisque) et expliquer.
    Décision Lionel 25/08 : le juge annote, il ne coupe plus ; pas de régénération, pas de repli."""
    usage = {"in": 0, "out": 0}

    def _cb(p, c):
        usage["in"] += p; usage["out"] += c

    morceaux = []
    async for d in llm.completer(messages, cle_demo=cle_demo, usage_cb=_cb, **params):
        morceaux.append(d)
    brut = "".join(morceaux)
    texte_final, revisions = verifier_faits(brut, adversaires, faits, cible_par_defaut, preuves)
    annotations = []
    if juger_actif and llm.MODE != "demo":
        try:
            annotations = await juger(texte_final, orateur, adversaires, preuves, faits, historique, tuple(cle_demo) + ("juge",))
        except Exception:
            logger.warning("juge arène en échec — garde déterministe seule", exc_info=True)
    return texte_final, revisions, annotations, {"regenerations": 0, "fallback": False, "brut": brut, "usage": usage}
