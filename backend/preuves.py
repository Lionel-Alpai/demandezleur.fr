# preuves.py — recherche RAG structurée : renvoie des BLOCS (pas une chaîne), d'où l'on tire
# à la fois le contexte injecté au modèle et les PREUVES affichées au visiteur.
import logging
from typing import Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

# Petite liste de mots vides français (le corpus est en français ; 'english' ne servait à rien).
STOP_FR = """a à ai aie aient aies ait alors au aucun aura aurai auraient aurais aurait auras aurez auriez aurions aurons auront
aux avaient avais avait avant avec avez aviez avions avons ayant ayez ayons bon c ça car ce ceci cela celà ces cet cette ceux chaque
ci comme comment d dans de des du donc dos e elle elles en encore es est et été étée étées étés êtes étiez étions étais était
étaient eu eue eues eus eut eux faire fait faites fois font fûmes fut fût furent hors ici il ils j je juste l la là le les leur
leurs lui m ma mais me même mes moi mon n ne ni nommés nos notre nous on ont ou où par parce pas peu peut plupart pour pourquoi qu
quand que quel quelle quelles quels qui s sa sans se sera serai seraient serais serait seras serez seriez serions serons seront ses
seulement si sien soi soient sois soit sommes son sont soyez soyons suis sur t ta tandis te tellement tels tes toi ton tous tout
très trop tu un une vos votre vous y""".split()


import re
import unicodedata

_STOP_NORM = None


def _normaliser_mot(m: str) -> str:
    """Sans accents, minuscule, racine grossière (pluriels, féminins, suffixes fréquents)."""
    m = unicodedata.normalize("NFKD", m).encode("ascii", "ignore").decode().lower()
    for suf in ("issements", "issement", "ations", "ation", "ements", "ement", "aux", "eux", "euses", "euse", "ives", "ive", "ees", "ee", "es", "s", "x", "e"):
        if len(m) > len(suf) + 3 and m.endswith(suf):
            return m[: -len(suf)]
    return m


def analyser(texte: str) -> list:
    """Analyseur TF-IDF : tokens ≥ 3 lettres, hors mots vides, racinisés. Partagé par le corpus et la requête."""
    global _STOP_NORM
    if _STOP_NORM is None:
        _STOP_NORM = {_normaliser_mot(w) for w in STOP_FR} | set(STOP_FR)
    out = []
    texte = unicodedata.normalize("NFC", texte or "")  # corpus parfois en NFD (é = e + accent combinant)
    for tok in re.findall(r"[a-zA-ZÀ-ÿ']{2,}", texte):
        tok = tok.lower().lstrip("'")
        if "'" in tok:
            tok = tok.split("'")[-1]
        if tok in STOP_FR or len(tok) < 3:
            continue
        r = _normaliser_mot(tok)
        if r and r not in _STOP_NORM and len(r) >= 3:
            out.append(r)
    return out


# Expansion de requête : le vocabulaire des électeurs n'est pas celui des programmes
# (« sécurité » → peines, police, délinquance…). Petite table, français politique courant.
EXPANSION = {
    "securit": "police delinquance peine prison justice ordre gendarmerie criminalite violence",
    "ecol": "education enseignant eleve professeur scolaire lycee college",
    "retrait": "pension cotisation age depart",
    "immigr": "frontiere asile etranger naturalisation regroupement expulsion",
    "sant": "hopital medecin soin medical urgence",
    "nuclea": "energie electricite centrale reacteur",
    "climat": "ecologie environnement carbone transition energie",
    "logement": "loyer habitat construction locataire proprietaire",
    "salair": "pouvoir achat remuneration smic revenu",
    "pouvoir achat": "salaire prix inflation tva revenu",
    "europ": "union bruxelles souverainete traite frexit",
    "enfant": "famille jeunesse mineur parent",
    "travail": "emploi chomage entreprise salarie",
    "impot": "fiscalite taxe tva prelevement budget",
    "democrat": "referendum institution assemblee proportionnelle citoyen",
    "agricult": "paysan ferme alimentation agriculteur",
    "polic": "securite ordre gendarmerie rebellion",
    "probit": "condamnation detournement fonds publics fraude justice exemplarite ethique corruption transparence",
    "exemplar": "condamnation detournement fonds publics probite ethique",
    "corrupt": "condamnation detournement fonds publics probite fraude",
    "justic": "condamnation tribunal juridiction peine procedure",
    "fraud": "detournement fonds publics condamnation",
    "press": "diffamation journaliste liberte expression",
    "journal": "diffamation presse liberte expression",
    "terror": "apologie terrorisme poursuite",
}


def etendre_requete(query: str) -> str:
    """Ajoute des termes voisins (une fois) pour les racines connues présentes dans la requête."""
    racines = set(analyser(query))
    q_norm = " ".join(racines)
    extra = []
    for cle, mots in EXPANSION.items():
        if any(r.startswith(cle) for r in racines) or cle in q_norm:
            extra.append(mots)
    return query + (" " + " ".join(extra) if extra else "")


def rechercher_blocs(corpus: list, query: str, top_k: int = 3, threshold: float = 0.02) -> list:
    """Blocs les plus proches de la requête (TF-IDF cosinus), avec leur score, triés décroissant.
    Le thème de chaque bloc est indexé avec son texte ; la requête est étendue (synonymes)."""
    if not corpus or not query or not query.strip():
        return []
    textes = [(str(b.get("theme", "")).replace("-", " ") + " ") * 2 + b.get("text", "") for b in corpus]
    try:
        vec = TfidfVectorizer(analyzer=analyser, sublinear_tf=True)
        mat = vec.fit_transform(textes + [etendre_requete(query)])
        sims = cosine_similarity(mat[-1], mat[:-1]).flatten()
    except Exception as e:  # requête vide après filtrage, etc.
        logger.error("TF-IDF : %s", e)
        return []
    idx = sims.argsort()[::-1][:top_k]
    resultats = []
    for i in idx:
        if sims[i] >= threshold:
            bloc = dict(corpus[i])
            bloc["_score"] = float(sims[i])
            resultats.append(bloc)
    return resultats


SANS_EXTRAIT = "Aucun extrait pertinent trouvé dans le programme officiel sur ce sujet précis."


def formater_contexte(blocs: list, window: Optional[int] = None) -> str:
    """Chaîne injectée au modèle — même forme qu'avant la refonte."""
    if not blocs:
        return SANS_EXTRAIT
    parts = []
    for b in blocs:
        texte = b.get("text", "")
        if window and len(texte) > window:
            texte = texte[:window] + "..."
        parts.append(f"[Source: {b.get('source', '?')}, page {b.get('page', 'N/A')}]\n{texte}")
    return "\n\n".join(parts)


def vers_preuves(blocs: list, candidat_id: str, type_defaut: str = "programme", extrait_max: int = 280) -> list:
    """Représentation publique des blocs : ce que le visiteur voit sous une réponse."""
    out = []
    for b in blocs:
        texte = b.get("text", "") or ""
        if len(texte) > extrait_max:
            coupe = texte[:extrait_max].rsplit(" ", 1)[0]
            texte = coupe + "…"
        piece = bool(b.get("url") or b.get("cr_uid"))
        p = {
            "type": "piece" if piece else type_defaut,
            "candidat_id": candidat_id,
            "titre": b.get("source", ""),
            "page": b.get("page", ""),
            "theme": b.get("theme", ""),
            "extrait": texte,
            "texte_integral": b.get("text", "") or "",  # pour le juge ; non affiché, non stocké
        }
        for k in ("url", "date", "orateur", "date_lisible"):
            if b.get(k):
                p[k] = b[k]
        out.append(p)
    return out
