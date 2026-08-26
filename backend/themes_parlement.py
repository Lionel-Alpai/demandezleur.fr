# themes_parlement.py — thèmes LISIBLES pour les sujets du feed parlementaire.
"""
Le feed porte des intitulés de séquence (« Discussion générale », « Motion de rejet préalable »)
inutilisables comme sujet de débat. Ce module dérive un `theme` (4-9 mots) et une `question`
d'ouverture, par règle puis par le modèle, et les met en cache dans parlement/themes.json
(fichier SIDECAR : parlement.json est écrasé par le collecteur, pas ce cache).
"""
import asyncio
import json
import logging
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

import llm

logger = logging.getLogger(__name__)
BASE = Path(__file__).resolve().parent
CACHE = BASE / "parlement" / "themes.json"
PROMPT = BASE / "prompts" / "debat" / "theme_parlement.txt"
_verrou = threading.Lock()
_cache = None
RUBRIQUES = re.compile(r"^(discussion (générale|des articles).*|motion de rejet.*|explications? de vote.*|présentation|vote.*|question(s)? au gouvernement.*|suite de la discussion.*)$", re.I)


def cle_sujet(s: dict) -> str:
    return f"{s.get('cr_uid', '')}#{s.get('segment', '')}"


def _charger() -> dict:
    global _cache
    with _verrou:
        if _cache is None:
            try:
                _cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
            except Exception:
                _cache = {}
        return _cache


def _sauver():
    with _verrou:
        CACHE.parent.mkdir(exist_ok=True)
        CACHE.write_text(json.dumps(_cache, ensure_ascii=False, indent=1), encoding="utf-8")


def _nettoyer(libelle: str) -> str:
    t = re.sub(r"^(projet|proposition) de loi( constitutionnelle| organique)?\s*(visant à|relative? (à|aux?)|portant|pour|tendant à)?\s*", "", libelle or "", flags=re.I)
    t = re.sub(r"\s*\((suite|deuxième lecture|nouvelle lecture)\)\s*", " ", t, flags=re.I)
    t = re.sub(r"\s*[—–-]\s*(discussion (générale|des articles).*|explications? de vote.*|motion de rejet.*|présentation|vote.*|suite.*)$", "", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip(" .;:—-")
    if t:
        t = t[0].upper() + t[1:]
    return t[:80].rstrip(" ,;:") if len(t) > 80 else t


_VIDES_SIGLE = {"des", "les", "aux", "pour", "dans", "par", "sur", "une", "des", "que", "qui", "leur", "avec", "sans", "sous", "vers", "chez", "entre", "visant", "relative", "relatif", "portant", "loi", "projet", "proposition", "tendant", "faire", "offrir", "réponses"}


def sigle_heuristique(libelle: str) -> str:
    """Initiales des mots significatifs du libellé : « Réponses Immédiates aux Phénomènes troublant l'Ordre public,
    la Sécurité et la Tranquillité » → RIPOST (mots ≥ 4 lettres hors mots-outils, 'réponses' compris via la majuscule)."""
    import unicodedata as _u
    mots = re.findall(r"[A-Za-zÀ-ÿ']+", libelle or "")
    init = []
    for m in mots:
        m2 = m.split("'")[-1]
        bas = m2.lower()
        if len(m2) >= 4 and (bas not in _VIDES_SIGLE or m2[0].isupper()) and not bas.endswith(("ant", "ent", "ique", "ic", "ale", "aux", "ive", "ives", "ifs", "if")):
            init.append(_u.normalize("NFKD", m2[0]).encode("ascii", "ignore").decode().upper())
    sig = "".join(init)
    return sig if 3 <= len(sig) <= 8 else ""


def alias_de(s: dict, cache_entree: dict = None) -> list:
    out = []
    for a in (cache_entree or {}).get("alias", []) or []:
        if a and a not in out: out.append(a)
    h = sigle_heuristique(s.get("libelle") or s.get("section", ""))
    if h and h not in out: out.append(h)
    return out


def trouver_sujet(sujet_debat: str, sujets: list) -> dict:
    """Le sujet du feed qui correspond à un sujet de débat : sigle/alias exact d'abord, sinon recouvrement de racines
    (libellé + thème + question + alias) via l'analyseur de preuves. None si rien ne dépasse le seuil."""
    import preuves as _p
    cache = _charger()
    q = (sujet_debat or "").strip()
    q_maj = {m for m in re.findall(r"\b[A-ZÉÈ]{3,8}\b", q)}                     # sigles tapés en capitales (RIPOST)
    q_norm = " " + re.sub(r"\W+", " ", _re_sans_accents(q).lower()) + " "
    rq_brut = set(_p.analyser(q))                                   # racines de la question telle quelle (dénominateur)
    rq = set(_p.analyser(_p.etendre_requete(q)))                     # + expansion (numérateur : ce qui peut accrocher)
    meilleur, score_max = None, 0.0
    for s in sujets:
        ce = cache.get(cle_sujet(s), {})
        alias = alias_de(s, ce)
        # 1) alias / sigle exact → prioritaire
        if any(a.upper() in q_maj for a in alias) or any(" " + re.sub(r"\W+", " ", _re_sans_accents(a).lower()).strip() + " " in q_norm for a in alias if len(a) > 3):
            return s
        # 2) recouvrement de racines
        txt = " ".join([s.get("libelle", ""), s.get("section", ""), ce.get("theme", ""), ce.get("question", "")] + alias)
        en = set(_p.analyser(txt))
        sc = len(rq & en) / max(1, len(rq_brut)) if rq_brut else 0
        if sc > score_max:
            meilleur, score_max = s, sc
    return meilleur if score_max >= 0.25 else None


def _re_sans_accents(t: str) -> str:
    import unicodedata as _u
    return _u.normalize("NFKD", t or "").encode("ascii", "ignore").decode()


def theme_deterministe(s: dict) -> dict:
    """Règle : QAG → le titre (la question) ; sinon le libellé du texte, nettoyé."""
    section, titre, libelle = s.get("section", ""), s.get("titre", ""), s.get("libelle", "")
    if re.match(r"^questions? au gouvernement", section or "", re.I):
        base = titre or libelle
    else:
        base = libelle or section or titre
    theme = _nettoyer(base)
    return {"theme": theme, "question": f"Que proposez-vous concernant : {theme[0].lower() + theme[1:]} ?" if theme else "", "methode": "regle"}


async def theme_llm(s: dict, extraits: list) -> dict:
    prompt = (PROMPT.read_text(encoding="utf-8")
              .replace("{libelle}", s.get("libelle") or s.get("section", ""))
              .replace("{titre}", s.get("titre", ""))
              .replace("{extraits}", "\n\n".join(e[:500] for e in extraits[:2]) or "(aucun)"))
    txt = await llm.completer_texte([{"role": "user", "content": prompt}], cle_demo=("theme", cle_sujet(s)), max_tokens=200,
                                    temperature=0.2, extra={"response_format": {"type": "json_object"}})
    try:
        d = json.loads(txt[txt.find("{"): txt.rfind("}") + 1])
        theme, question = (d.get("theme") or "").strip(" .»«\"'"), (d.get("question") or "").strip()
        alias = [str(a).strip(" .«»\"'") for a in (d.get("alias") or []) if isinstance(a, str) and 2 <= len(str(a).strip()) <= 40][:6]
        if 3 <= len(theme) <= 90 and question:
            return {"theme": theme, "question": question[:160], "alias": alias, "methode": "llm"}
    except Exception:
        pass
    return {}


def enrichir(sujets: list, dedup: bool = True) -> list:
    """Ajoute cle/theme/question depuis le cache (règle en repli). Dédoublonne par thème."""
    cache = _charger()
    vus, out = set(), []
    for s in sujets:
        k = cle_sujet(s)
        t = cache.get(k) or theme_deterministe(s)
        s2 = dict(s, cle=k, theme=t.get("theme", ""), question=t.get("question", ""), alias=alias_de(s, t), theme_methode=t.get("methode", "regle"))
        norme = re.sub(r"\W+", " ", _nettoyer(s.get("libelle") or s.get("section") or s2["theme"]).lower()).strip()
        if dedup and (not norme or norme in vus):
            continue
        vus.add(norme)
        out.append(s2)
    return out


async def precalculer(sujets_bruts: list, extraits_par_cle: dict):
    """Calcule (par le modèle) les thèmes manquants, purge les clés orphelines. Démo : règle seule."""
    cache = _charger()
    presentes = {cle_sujet(s) for s in sujets_bruts}
    for k in [k for k in cache if k not in presentes]:
        cache.pop(k, None)
    for s in sujets_bruts:
        k = cle_sujet(s)
        if k in cache and cache[k].get("methode") == "llm":
            continue
        t = {}
        if llm.MODE != "demo":
            try:
                t = await theme_llm(s, extraits_par_cle.get(k, []))
            except Exception as e:
                logger.warning("theme_llm %s : %s", k, e)
        if not t:
            t = theme_deterministe(s)
        t["genere_le"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        cache[k] = t
        _sauver()
    logger.info("themes_parlement : %d thèmes en cache", len(cache))
