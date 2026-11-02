# actu_fiches.py — fiches ÉVÉNEMENT et fiche SITUATION POLITIQUE du tiroir ACTU (brique dl-actu-fiches-evenement-et-situation).
"""Module PUR (aucun appel réseau, aucun LLM) partagé par le collecteur (babahargadon, construction + validation) et le backend
(cabahargadon, lecture + injection). Une fiche est stockée dans le tiroir comme une ENTRÉE ordinaire du jour
(type fiche_evenement | fiche_situation, statut verifie_auto) : l'ingest existant la fait voyager sans changement, et
actu.charger() l'ignore (ni verbatim ni fait).
RÈGLE DE CONCORDANCE (la seule validation, mécanique, aucune relecture humaine) : un champ n'est retenu que si ≥ 2 médias distincts
le portent (chaque média cité doit AVOIR la valeur dans sa pièce : mots significatifs et chiffres), ou 1 source officielle ;
sinon « non établi »."""
import hashlib
import json
import re
import unicodedata
from datetime import date, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent / "actu"
OFFICIELS = ("assemblee-nationale.fr", "senat.fr", "gouvernement.gouv.fr", "gouvernement.fr", "elysee.fr", "interieur.gouv.fr",
             "justice.gouv.fr", "vie-publique.fr", "legifrance.gouv.fr", "conseil-constitutionnel.fr", "parquet", "service-public.fr")
NON_ETABLI = "non établi"
CHAMPS_EVENEMENT = ("date", "lieu", "nature", "bilan", "enquete", "qualification", "reactions")
FENETRE_FICHES = 30
NOMBRES_MOTS = {"deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix", "onze", "douze", "quinze", "vingt", "trente", "quarante", "cinquante", "cent", "mille", "dizaines", "centaines", "millions"}
MOTS_VIDES = {"dans", "avec", "pour", "cette", "leur", "leurs", "elle", "elles", "sont", "etait", "ete", "plus", "entre", "apres", "avant", "dont", "tout", "tous", "mais", "comme", "aussi", "ainsi", "sans", "sous", "vers", "chez", "fait"}


def sans(t) -> str:
    t = unicodedata.normalize("NFD", str(t or "").lower().replace("’", "'"))
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def domaine(m: str) -> str:
    m = re.sub(r"^https?://(www\.)?", "", str(m or "").strip().lower()).split("/")[0]
    return m[4:] if m.startswith("www.") else m


def medias_piece(p: dict) -> set:
    """Médias distincts qui portent une pièce : son média + ceux de ses sources."""
    out = {domaine(x) for x in str(p.get("media") or "").split(",") if x.strip()}
    out |= {domaine(s.get("media") or s.get("url")) for s in (p.get("sources") or []) if isinstance(s, dict)}
    return {m for m in out if m}


def est_officiel(m: str) -> bool:
    return any(o in m for o in OFFICIELS)


def _mots(t: str) -> list:
    return [m for m in re.findall(r"[a-z0-9]+", sans(t)) if (len(m) >= 4 and m not in MOTS_VIDES) or m.isdigit()]


def porte(valeur: str, texte: str) -> bool:
    """La pièce PORTE la valeur : tous les nombres de la valeur y sont et ≥ 70 % de ses mots significatifs."""
    v, t = sans(valeur), sans(texte)
    mots = _mots(v)
    if not mots:
        return False
    nombres = re.findall(r"\d+", v) + [m for m in re.findall(r"[a-z]+", v) if m in NOMBRES_MOTS]
    if any(n not in t for n in nombres):
        return False  # un chiffre ou un nombre en lettres absent de la pièce n'est jamais toléré
    tm = set(_mots(t)) | {m for m in re.findall(r"[a-z0-9]+", t)}
    return sum(1 for m in mots if m in tm or any(m[:5] == x[:5] for x in tm if len(x) >= 5 and len(m) >= 5)) / len(mots) >= 0.7


def texte_piece(p: dict) -> str:
    return " ".join(str(p.get(k) or "") for k in ("verbatim", "fait", "ou", "date")) + " " + " ".join(p.get("themes") or [])


def valider_champ(valeur, refs: list, pieces: dict) -> dict:
    """{valeur, etabli, medias, pieces} : établi ssi ≥ 2 médias distincts PORTENT la valeur (pièces citées existantes), ou 1 officiel.
    Valeur à plusieurs éléments (« a ; b », « a / b ») : chaque élément est validé SEUL, on ne garde que les éléments établis
    (jamais de découpe à la virgule : une négation ou une incise ne doit pas être détachée de ce qu'elle qualifie)."""
    valeur = str(valeur or "").strip()
    if not valeur or sans(valeur) in (sans(NON_ETABLI), "inconnu", "n/a", "aucun", "null"):
        return {"valeur": NON_ETABLI, "etabli": False, "medias": [], "pieces": []}
    segments = [x.strip() for x in re.split(r"\s*;\s*|\s+/\s+", valeur) if x.strip()]
    if len(segments) > 1:
        vus = [_valider_un(x, refs, pieces) for x in segments]
        ok = [v for v in vus if v["etabli"]]
        if not ok:
            return {"valeur": NON_ETABLI, "etabli": False, "medias": sorted({m for v in vus for m in v["medias"]}), "pieces": []}
        return {"valeur": " ; ".join(v["valeur"] for v in ok), "etabli": True, "medias": sorted({m for v in ok for m in v["medias"]}),
                "pieces": list(dict.fromkeys(r for v in ok for r in v["pieces"]))}
    return _valider_un(valeur, refs, pieces)


def _valider_un(valeur: str, refs: list, pieces: dict) -> dict:
    medias, utiles = set(), []
    for r in refs or []:
        p = pieces.get(str(r))
        if p and porte(valeur, texte_piece(p)):
            utiles.append(str(r))
            medias |= medias_piece(p)
    if len(medias) >= 2 or any(est_officiel(m) for m in medias):
        return {"valeur": valeur, "etabli": True, "medias": sorted(medias), "pieces": utiles}
    return {"valeur": NON_ETABLI, "etabli": False, "medias": sorted(medias), "pieces": utiles}


def valider_fiche(brut: dict, pieces: dict, jour: str):
    """Fiche ÉVÉNEMENT validée, ou None. brut = {cle, titre, cles[], champs{nom:{valeur, pieces[]}}} issu du LLM."""
    if not isinstance(brut, dict) or not isinstance(brut.get("champs"), dict):
        return None
    # la concordance se vérifie sur TOUTES les pièces de l'événement, pas sur les seules pièces citées : le modèle sous-cite (une pièce par champ)
    def refs(n):
        cit = [str(r) for r in ((brut["champs"].get(n) or {}).get("pieces") or [])]
        return list(dict.fromkeys(cit + list(pieces)))
    champs = {n: valider_champ((brut["champs"].get(n) or {}).get("valeur"), refs(n), pieces) for n in CHAMPS_EVENEMENT}
    if not champs["nature"]["etabli"] or sum(1 for c in champs.values() if c["etabli"]) < 2:
        return None  # rien d'inventé : pas de nature établie ou nature seule -> pas de fiche ; les autres champs restent « non établi »
    utilises = sorted({r for c in champs.values() for r in c["pieces"]})
    corpus = sans(" ".join(texte_piece(pieces[r]) for r in utilises))
    cles = sorted({sans(c).strip() for c in (brut.get("cles") or []) if len(sans(c).strip()) >= 4 and sans(c).strip() in corpus})
    if not cles:
        return None
    titre = str(brut.get("titre") or champs["nature"]["valeur"]).strip()[:140]
    return {"id": "ev-" + hashlib.sha1((sans(brut.get("cle") or titre) + champs["date"]["valeur"]).encode()).hexdigest()[:10], "type": "fiche_evenement",
            "statut": "verifie_auto", "titre": titre, "cles": cles, "champs": champs, "pieces": utilises, "date": champs["date"]["valeur"] if champs["date"]["etabli"] else "",
            "verifie_le": jour, "preuve": "champs retenus par concordance (≥ 2 médias distincts ou 1 source officielle)"}


def promouvoir(entrees: list) -> list:
    """Pièces `a_valider` de type fait -> `verifie_auto` quand ≥ 2 médias distincts les portent (même règle). Retourne les entrées promues."""
    promues = []
    for e in entrees:
        if e.get("statut") == "a_valider" and e.get("type") == "fait" and e.get("fait"):
            ms = medias_piece(e)
            if len(ms) >= 2 or any(est_officiel(m) for m in ms):
                e["statut"], e["preuve"] = "verifie_auto", f"promu automatiquement : {len(ms)} média(s) concordant(s) ({', '.join(sorted(ms))[:120]})"
                promues.append(e)
    return promues


def rendre_fiche(f: dict) -> str:
    lignes = [f"FICHE ÉVÉNEMENT — {f.get('titre', '')} ({f.get('date') or 'date non établie'})"]
    for n in CHAMPS_EVENEMENT:
        c = (f.get("champs") or {}).get(n) or {}
        lignes.append(f"  · {n} : {c.get('valeur', NON_ETABLI)}")
    return "\n".join(lignes)


def rendre_situation(jour: str, gouvernement: dict, candidatures: dict, noms_candidats: list, fiches: list, max_mots: int = 400) -> str:
    """Fiche SITUATION, rendue MÉCANIQUEMENT (aucune phrase libre du LLM) et bornée à max_mots."""
    base = [f"SITUATION POLITIQUE AU {jour}", f"· Gouvernement en place : {gouvernement.get('valeur', NON_ETABLI)}",
            f"· Candidatures déclarées : {candidatures.get('valeur', NON_ETABLI)}", "· Candidats présents sur le site : " + ", ".join(noms_candidats)]
    evs = [f"  - {f['titre']} ({f.get('date') or 'date non établie'}) — {f['champs']['nature']['valeur']}" for f in fiches]
    texte = "\n".join(base)
    while evs and len((texte + "\n· Événements majeurs des 30 derniers jours (voir les fiches) :\n" + "\n".join(evs)).split()) > max_mots:
        evs.pop()
    if evs:
        texte += "\n· Événements majeurs des 30 derniers jours (voir les fiches) :\n" + "\n".join(evs)
    return texte


def _entrees_fenetre(jours: int = FENETRE_FICHES, base: Path = None):
    limite = (date.today() - timedelta(days=jours)).isoformat()
    for p in sorted((base or BASE).glob("*.json")):
        if p.stem < limite:
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for e in d.get("entrees", []):
            if isinstance(e, dict):
                yield p.stem, e


def charger_fiches(base: Path = None) -> tuple:
    """(fiche_situation | None, [fiches événement]) : version la plus récente de chaque id, statuts servis seulement."""
    evs, sit = {}, None
    for jour, e in _entrees_fenetre(base=base):
        if e.get("statut") not in ("verifie_auto", "valide"):
            continue
        if e.get("type") == "fiche_evenement":
            evs[e["id"]] = dict(e, jour=jour)
        elif e.get("type") == "fiche_situation" and (sit is None or jour >= sit["jour"]):
            sit = dict(e, jour=jour)
    return sit, sorted(evs.values(), key=lambda f: f.get("date") or f.get("jour", ""), reverse=True)


def fiches_touchees(fiches: list, requete: str) -> list:
    """Fiches dont un terme distinctif (lieu, nature) figure dans la requête (sujet, question, pièces)."""
    r = sans(requete)
    return [f for f in fiches if any(c in r for c in f.get("cles") or [])]


MENTION = "Tout ce qui n'est pas écrit dans une fiche est INCONNU : tu ne le dis pas, tu ne le déduis pas, tu ne le complètes pas."


def bloc_etat_du_monde(requete: str, base: Path = None) -> tuple:
    """(texte_situation_en_tete, texte_fiches_evenement, preuves) pour un prompt Arène ou chat. Fiche entière, jamais une pièce orpheline."""
    sit, fiches = charger_fiches(base)
    tete = ""
    preuves = []
    if sit and sit.get("texte"):
        tete = f"ÉTAT DU MONDE (fiche établie par concordance de médias, valable à sa date) :\n{sit['texte']}\n{MENTION}\n\n"
    touchees = fiches_touchees(fiches, requete)[:3]
    corps = ""
    if touchees:
        corps = "\n\nFICHES D'ÉVÉNEMENTS (établies par concordance d'au moins 2 médias ou d'une source officielle ; « non établi » = on ne sait pas) :\n" + "\n".join(rendre_fiche(f) for f in touchees) + "\n" + MENTION + "\n"
        for f in touchees:
            preuves.append({"type": "actu", "candidat_id": "sujet", "titre": "Fiche événement : " + f.get("titre", ""), "page": f.get("date", ""), "theme": "",
                            "extrait": rendre_fiche(f), "texte_integral": rendre_fiche(f), "url": "", "orateur": ", ".join(sorted({m for c in f["champs"].values() for m in c.get("medias", [])}))[:120],
                            "date_lisible": f.get("date", "")})
    if sit and sit.get("texte"):
        preuves.append({"type": "actu", "candidat_id": "sujet", "titre": "Situation politique", "page": sit.get("jour", ""), "theme": "", "extrait": sit["texte"],
                        "texte_integral": sit["texte"], "url": "", "orateur": "fiche situation", "date_lisible": sit.get("jour", "")})
    return tete, corps, preuves
