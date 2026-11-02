#!/usr/bin/env python3
r"""Mesure déterministe (zéro LLM) de la signature de style oral par candidat.

Lit les verbatims JSONL dans <verbatims_dir>/<slug>.*.jsonl (en excluant les
lignes où voix_mixtes est vrai, typiquement les interviews/mixtes non
diarisées) et produit <out_dir>/<slug>.json avec les métriques globales et
par situation :
  1. Longueur de phrase (moyenne, médiane, écart-type, IQR, CV, rafales/périodes)
  2. Taux de questions, d'exclamations et de phrases nominales (sans verbe conjugué)
  3. Pronoms et marqueurs de posture (je, nous, vous, on, les Français)
  4. N-grammes signature par log-odds avec prior de Dirichlet (Monroe et al. 2008)
  5. Formules d'ouverture de prise de parole
  6. Formules d'adresse directe et d'interpellation
  7. Réactions à l'interruption et dynamique de duel en hémicycle (.an.jsonl)

Deux exécutions sur les mêmes entrées produisent exactement le même SHA-256.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import re
import shutil
import sys
import time


_PATTERNS = {
    "didascalie_yt": (r"\[[^\]]{1,60}\]", re.IGNORECASE),
    "espaces": (r"\s+", 0),
    "ponct_orpheline_q": (r"\.\s+\?", 0),
    "ponct_orpheline_e": (r"\.\s+!", 0),
    "decoupe_phrases": (r"([^.!?…]+(?:[.!?…]+|$))", 0),
    "mot_token": (r"[a-zàâäéèêëîïôöùûüÿçœæ]+(?:'[a-zàâäéèêëîïôöùûüÿçœæ]+)?", re.IGNORECASE),
    "mot_simple": (r"[a-zàâäéèêëîïôöùûüÿçœæ]+", re.IGNORECASE),
    "je_elide": (r"\bj'[a-zàâäéèêëîïôöùûüÿçœæ]", re.IGNORECASE),
    "verbe_clitique": (
        r"\b(?:j'|je\s+ne\s+|je\s+n'|tu\s+|il\s+|elle\s+|on\s+|nous\s+|vous\s+|ils\s+|elles\s+|"
        r"c'est\b|ce\s+sont\b|c'était\b|c'etait\b|il\s+y\s+a\b|il\s+faut\b|"
        r"n'est\b|n'ont\b|n'a\b|qu'il\b|qu'elle\b|qu'on\b|qui\s+(?:est|sont|a|ont|fait|font|peut|veut|doit|va|vont)\b)",
        re.IGNORECASE,
    ),
    "verbe_suffixe": (
        r"\b[a-zàâäéèêëîïôöùûüÿçœæ]{2,}(?:ons|ez|ais|ait|aient|erai|eras|era|eront|erions|eriez|"
        r"irai|iras|ira|iront|issons|issez|issent)\b",
        re.IGNORECASE,
    ),
}

REGEXES = {k: re.compile(pat, flags) for k, (pat, flags) in _PATTERNS.items()}

# Auxiliaires, modaux et formes conjuguées très fréquentes en français oral
VERBES_CONJUGUES_FREQUENTS = frozenset({
    "suis", "es", "est", "sommes", "êtes", "etes", "sont",
    "étais", "etais", "était", "etait", "étions", "etions", "étiez", "etiez", "étaient", "etaient",
    "serai", "seras", "sera", "serons", "serez", "seront", "serait", "seraient", "soit", "soient", "soyons", "soyez",
    "ai", "as", "a", "avons", "avez", "ont",
    "avais", "avait", "avions", "aviez", "avaient",
    "aurai", "auras", "aura", "aurons", "aurez", "auront", "aurait", "auraient", "ait", "aient",
    "vais", "vas", "va", "allons", "allez", "vont", "allait", "allaient", "ira", "iront",
    "fais", "fait", "faisons", "faites", "font", "faisait", "faisaient", "fera", "feront", "ferait", "fassent",
    "peux", "peut", "pouvons", "pouvez", "peuvent", "pouvait", "pouvaient", "pourra", "pourront", "pourrait", "puisse",
    "veux", "veut", "voulons", "voulez", "veulent", "voulait", "voulaient", "voudrais", "voudrait", "veuille",
    "dois", "doit", "devons", "devez", "doivent", "devait", "devaient", "devra", "devront", "devrait", "devraient",
    "sais", "sait", "savons", "savez", "savent", "savait", "savaient", "saura", "saurait", "sache", "sachez",
    "vois", "voit", "voyons", "voyez", "voient", "voyait", "verra", "verrez",
    "dis", "dit", "disons", "dites", "disent", "disait", "disaient", "dira", "dirai", "dirais",
    "prends", "prend", "prenons", "prenez", "prennent", "prenait", "prendra",
    "viens", "vient", "venons", "venez", "viennent", "venait", "viendra",
    "tiens", "tient", "tenons", "tenez", "tiennent", "tenait", "tiendra",
    "mets", "met", "mettons", "mettez", "mettent", "mettait", "mettra",
    "crois", "croit", "croyons", "croyez", "croient", "croyait",
    "faut", "fallait", "faudra", "faudrait", "vaut", "valait", "vaudrait", "pleut",
    "parle", "parlent", "pense", "pensent", "passe", "passent", "donne", "donnent",
    "trouve", "trouvent", "arrive", "arrivent", "reste", "restent", "cherche", "cherchent",
    "appelle", "appellent", "existe", "existent", "continue", "continuent", "demande", "demandent",
    "propose", "proposent", "refuse", "refusent", "accepte", "acceptent", "écoutez", "ecoutez", "regardez",
})

# Stopwords fonctionnels pour filtrer les unigrammes purement grammaticaux dans les n-grammes signature
STOPWORDS_UNIGRAM = frozenset({
    "le", "la", "les", "un", "une", "des", "du", "de", "d", "au", "aux",
    "ce", "cet", "cette", "ces", "mon", "ton", "son", "ma", "ta", "sa",
    "mes", "tes", "ses", "notre", "votre", "leur", "nos", "vos", "leurs",
    "et", "ou", "où", "mais", "donc", "or", "ni", "car", "que", "qu",
    "qui", "quoi", "dont", "dans", "sur", "sous", "par", "pour", "en",
    "vers", "avec", "sans", "chez", "entre", "jusqu", "contre", "comme",
    "plus", "moins", "très", "tres", "bien", "mal", "peu", "trop", "aussi",
    "si", "ne", "n", "pas", "point", "plus", "jamais", "rien", "tout", "tous",
    "toute", "toutes", "même", "meme", "autre", "autres", "quel", "quelle",
    "quels", "quelles", "quelque", "quelques", "chaque", "aucun", "aucune",
    "tel", "telle", "tels", "telles", "se", "s", "y", "en", "l", "c", "m", "t",
    "il", "ils", "elle", "elles", "lui", "eux", "cela", "ça", "ca", "ceci",
    "être", "etre", "avoir", "faire", "dire", "aller", "voir", "savoir",
    "pouvoir", "falloir", "vouloir", "devoir", "prendre", "venir", "mettre",
    "suis", "es", "est", "sommes", "êtes", "etes", "sont", "était", "etait",
    "étaient", "etaient", "sera", "seront", "serait", "soit", "été", "ete",
    "ai", "as", "a", "avons", "avez", "ont", "avait", "avaient", "aura", "aurait",
    "fait", "font", "faisait", "fera", "peut", "peuvent", "pouvait", "pourra",
    "pourrait", "faut", "fallait", "faudra", "faudrait", "va", "vont", "allait",
    "dit", "disent", "disait", "veut", "veulent", "doit", "doivent", "devrait",
    "quand", "lorsque", "puisque", "parce", "alors", "ainsi", "après", "apres",
    "avant", "depuis", "pendant", "encore", "déjà", "deja", "toujours", "souvent",
    "ici", "là", "la", "oui", "non", "bon", "euh", "ben", "bah", "hein", "ouais",
})

# Bruit d'auto-transcription ou artefacts de noms propres isolés non stylistiques
BRUIT_TRANSCRIPTION = frozenset({
    "euh", "hum", "ouais", "bah", "ben", "hein", "nan", "ok",
    "applaudissements", "musique", "rires", "sourires", "acclamation",
    "grognement", "raclement", "gorge",
})

FORMULES_ADRESSE_CATALOGUE = (
    ("monsieur le président", ("monsieur", "le", "président")),
    ("madame la présidente", ("madame", "la", "présidente")),
    ("monsieur le premier ministre", ("monsieur", "le", "premier", "ministre")),
    ("madame la première ministre", ("madame", "la", "première", "ministre")),
    ("monsieur le ministre", ("monsieur", "le", "ministre")),
    ("madame la ministre", ("madame", "la", "ministre")),
    ("monsieur le député", ("monsieur", "le", "député")),
    ("madame la députée", ("madame", "la", "députée")),
    ("monsieur le rapporteur", ("monsieur", "le", "rapporteur")),
    ("madame la rapporteure", ("madame", "la", "rapporteure")),
    ("mes chers collègues", ("mes", "chers", "collègues")),
    ("chers collègues", ("chers", "collègues")),
    ("chères collègues", ("chères", "collègues")),
    ("mes chers compatriotes", ("mes", "chers", "compatriotes")),
    ("chers compatriotes", ("chers", "compatriotes")),
    ("mes chers amis", ("mes", "chers", "amis")),
    ("chers amis", ("chers", "amis")),
    ("mes amis", ("mes", "amis")),
    ("camarades", ("camarades",)),
    ("mesdames et messieurs", ("mesdames", "et", "messieurs")),
    ("mesdames messieurs", ("mesdames", "messieurs")),
    ("écoutez", ("écoutez",)),
    ("regardez", ("regardez",)),
    ("voyez-vous", ("voyez", "vous")),
    ("figurez-vous", ("figurez", "vous")),
    ("permettez-moi", ("permettez", "moi")),
    ("croyez-moi", ("croyez", "moi")),
    ("comprenez-moi", ("comprenez", "moi")),
    ("rassurez-vous", ("rassurez", "vous")),
    ("imaginez", ("imaginez",)),
    ("allons", ("allons",)),
)

CATEGORIES_OUVERTURE = (
    (
        "adresse_institutionnelle",
        (
            ("monsieur", "le"),
            ("madame", "la"),
            ("mes", "chers"),
            ("chers", "collègues"),
            ("chers", "amis"),
            ("chers", "compatriotes"),
            ("mesdames", "et"),
            ("mesdames", "messieurs"),
            ("merci", "madame"),
            ("merci", "monsieur"),
        ),
    ),
    (
        "attaque_ou_contradiction",
        (
            ("mais",),
            ("non",),
            ("pas", "du", "tout"),
            ("au", "contraire"),
            ("faux",),
            ("c'est", "faux"),
            ("mensonge",),
            ("arrêtez",),
            ("vous", "mentez"),
            ("vous", "avez"),
            ("vous", "ne"),
            ("vous", "êtes"),
            ("pardon",),
        ),
    ),
    (
        "prise_a_temoin_ou_injonction",
        (
            ("écoutez",),
            ("regardez",),
            ("voyez",),
            ("figurez",),
            ("allons",),
            ("enfin",),
            ("franchement",),
            ("honnêtement",),
            ("eh", "bien"),
            ("alors",),
            ("voilà",),
        ),
    ),
    (
        "affirmation_personnelle_ou_collective",
        (
            ("je",),
            ("j'",),
            ("moi",),
            ("nous",),
            ("pour", "ma", "part"),
            ("pour", "notre", "part"),
        ),
    ),
)


def normaliser_apostrophes(texte: str) -> str:
    res = []
    for ch in texte:
        if ch in ("’", "‘", "`", "´"):
            res.append("'")
        else:
            res.append(ch)
    return "".join(res)


def nettoyer_texte(texte: str) -> str:
    t = normaliser_apostrophes(texte)
    t = REGEXES["didascalie_yt"].sub(" ", t)
    t = REGEXES["ponct_orpheline_q"].sub("?", t)
    t = REGEXES["ponct_orpheline_e"].sub("!", t)
    t = REGEXES["espaces"].sub(" ", t).strip()
    return t


def extraire_mots_simples(texte_minuscule: str) -> list[str]:
    return [
        m for m in REGEXES["mot_simple"].findall(texte_minuscule)
        if m not in ("euh", "hum")
    ]


def segmenter_phrases(texte: str) -> list[tuple[str, str, list[str]]]:
    r"""Retourne une liste de (phrase_brute, ponctuation_finale, mots_simples)."""
    propre = nettoyer_texte(texte)
    if not propre:
        return []
    morceaux = REGEXES["decoupe_phrases"].findall(propre)
    phrases: list[tuple[str, str, list[str]]] = []
    for m in morceaux:
        seg = m.strip()
        if not seg:
            continue
        ponct = "."
        for ch in reversed(seg):
            if ch in ("?", "!", ".", "…"):
                ponct = ch
                break
        mots = extraire_mots_simples(seg.lower())
        if not mots:
            continue
        phrases.append((seg, ponct, mots))
    return phrases


def est_phrase_nominale(phrase_brute: str, mots: list[str]) -> bool:
    r"""Détecte une phrase nominale (sans verbe conjugué repérable)."""
    if not mots:
        return False
    # Une très longue phrase (>= 25 mots) en transcription orale contient quasi toujours un verbe
    if len(mots) >= 25:
        return False
    pl = phrase_brute.lower()
    if any(w in VERBES_CONJUGUES_FREQUENTS for w in mots):
        return False
    if REGEXES["verbe_clitique"].search(pl):
        return False
    if REGEXES["verbe_suffixe"].search(pl):
        return False
    return True


def calculer_quantiles(valeurs_triees: list[int | float]) -> tuple[float, float, float]:
    r"""Retourne (q25, mediane, q75) de manière déterministe."""
    n = len(valeurs_triees)
    if n == 0:
        return (0.0, 0.0, 0.0)

    def _percentile(p: float) -> float:
        if n == 1:
            return float(valeurs_triees[0])
        pos = p * (n - 1)
        bas = int(math.floor(pos))
        haut = int(math.ceil(pos))
        if bas == haut:
            return float(valeurs_triees[bas])
        frac = pos - bas
        return float(valeurs_triees[bas]) * (1.0 - frac) + float(valeurs_triees[haut]) * frac

    return (_percentile(0.25), _percentile(0.50), _percentile(0.75))


def compter_sous_sequence(mots: list[str], motif: tuple[str, ...]) -> int:
    k = len(motif)
    n = len(mots)
    if k == 0 or n < k:
        return 0
    if k == 1:
        cible = motif[0]
        return sum(1 for w in mots if w == cible)
    total = 0
    for i in range(n - k + 1):
        ok = True
        for j in range(k):
            if mots[i + j] != motif[j]:
                ok = False
                break
        if ok:
            total += 1
    return total


def extraire_ouverture_prise(phrases: list[tuple[str, str, list[str]]]) -> tuple[str, str]:
    r"""Classifie l'ouverture de la première phrase d'une prise de parole."""
    if not phrases:
        return ("autre_ouverture", "")
    prem_brute, prem_ponct, prem_mots = phrases[0]
    mots_debut = tuple(prem_mots[:5])
    amorce = " ".join(prem_mots[:3]) if prem_mots else ""

    # Test des catégories d'ouverture dans l'ordre de priorité
    for cat_nom, motifs in CATEGORIES_OUVERTURE:
        for motif in motifs:
            k = len(motif)
            if len(mots_debut) >= k and mots_debut[:k] == motif:
                return (cat_nom, amorce)
            # Cas de j' en début de phrase (ex: "j'ai", "j'entends")
            if motif == ("j'",) and prem_brute.lower().lstrip()[:2] == "j'":
                return (cat_nom, amorce)

    if prem_ponct == "?":
        return ("question_initiale", amorce)

    return ("explicative_ou_narrative", amorce)


def calculer_metriques_sous_corpus(enregistrements: list[dict]) -> dict:
    """Calcule les métriques 1, 2, 3, 5, 6 sur un ensemble d'enregistrements."""
    longueurs_phrases: list[int] = []
    nb_questions = 0
    nb_exclamations = 0
    nb_nominales = 0
    total_mots = 0

    # Compteurs pronoms et marqueurs
    cnt_je = 0
    cnt_nous = 0
    cnt_vous = 0
    cnt_on = 0
    cnt_les_francais = 0
    cnt_francais_total = 0
    cnt_peuple = 0

    # Compteurs ouvertures et adresses
    cat_ouvertures: Counter[str] = Counter()
    amorces_ouvertures: Counter[str] = Counter()
    exemples_ouvertures: dict[str, str] = {}
    cnt_adresses: Counter[str] = Counter()

    for rec in enregistrements:
        texte = str(rec.get("texte", ""))
        phrases = segmenter_phrases(texte)
        if not phrases:
            continue

        cat_ouv, amorce = extraire_ouverture_prise(phrases)
        cat_ouvertures[cat_ouv] += 1
        if amorce:
            amorces_ouvertures[amorce] += 1
            if amorce not in exemples_ouvertures:
                extrait = phrases[0][0].strip()
                if len(extrait) > 120:
                    extrait = extrait[:117] + "..."
                exemples_ouvertures[amorce] = extrait

        # Analyse phrase par phrase
        mots_prise: list[str] = []
        for ph_brute, ph_ponct, ph_mots in phrases:
            nb_w = len(ph_mots)
            longueurs_phrases.append(nb_w)
            total_mots += nb_w
            mots_prise.extend(ph_mots)

            if ph_ponct == "?":
                nb_questions += 1
            elif ph_ponct == "!":
                nb_exclamations += 1

            if est_phrase_nominale(ph_brute, ph_mots):
                nb_nominales += 1

            # j' élidé dans la phrase
            cnt_je += len(REGEXES["je_elide"].findall(ph_brute))

        # Comptage des pronoms dans la prise
        for idx, w in enumerate(mots_prise):
            if w in ("je", "moi"):
                cnt_je += 1
            elif w == "nous":
                cnt_nous += 1
            elif w == "vous":
                cnt_vous += 1
            elif w == "on":
                cnt_on += 1
            elif w == "français":
                cnt_francais_total += 1
                if idx > 0 and mots_prise[idx - 1] in ("les", "aux", "des", "nos"):
                    cnt_les_francais += 1
            elif w == "peuple":
                cnt_peuple += 1

        # Comptage des formules d'adresse
        for label_adr, seq_adr in FORMULES_ADRESSE_CATALOGUE:
            c = compter_sous_sequence(mots_prise, seq_adr)
            if c > 0:
                cnt_adresses[label_adr] += c

    nb_prises = len(enregistrements)
    nb_phrases = len(longueurs_phrases)
    if nb_phrases == 0 or total_mots == 0:
        return {
            "nb_interventions": nb_prises,
            "nb_phrases": 0,
            "nb_mots": 0,
            "longueur_phrases": {},
            "ponctuation_et_syntaxe": {},
            "pronoms": {},
            "formules_ouverture": {},
            "formules_adresse": {},
        }

    # 1. Longueur de phrase & dispersion
    longueurs_triees = sorted(longueurs_phrases)
    moyenne = total_mots / nb_phrases
    q25, mediane, q75 = calculer_quantiles(longueurs_triees)
    iqr = q75 - q25
    variance = sum((x - moyenne) ** 2 for x in longueurs_phrases) / nb_phrases
    ecart_type = math.sqrt(variance)
    cv = ecart_type / moyenne if moyenne > 0 else 0.0

    nb_rafales = sum(1 for x in longueurs_phrases if x <= 8)
    nb_moyennes = sum(1 for x in longueurs_phrases if 9 <= x <= 24)
    nb_periodes = sum(1 for x in longueurs_phrases if x >= 25)
    part_rafales = (nb_rafales * 100.0) / nb_phrases
    part_moyennes = (nb_moyennes * 100.0) / nb_phrases
    part_periodes = (nb_periodes * 100.0) / nb_phrases
    ratio_rafales_periodes = (
        round(nb_rafales / nb_periodes, 3) if nb_periodes > 0 else float(nb_rafales)
    )

    longueur_info = {
        "nb_phrases": nb_phrases,
        "nb_mots": total_mots,
        "moyenne_mots": round(moyenne, 2),
        "mediane_mots": round(mediane, 2),
        "q25_mots": round(q25, 2),
        "q75_mots": round(q75, 2),
        "iqr_mots": round(iqr, 2),
        "ecart_type_mots": round(ecart_type, 2),
        "cv_mots": round(cv, 3),
        "part_rafales_courtes_pct": round(part_rafales, 2),
        "part_phrases_moyennes_pct": round(part_moyennes, 2),
        "part_periodes_longues_pct": round(part_periodes, 2),
        "ratio_rafales_periodes": ratio_rafales_periodes,
        "profil_rythmique": (
            "rafales_percussives"
            if ratio_rafales_periodes >= 1.5
            else ("periodes_amples" if ratio_rafales_periodes <= 0.9 else "alternance_rafales_periodes")
        ),
    }

    # 2. Taux de questions, d'exclamations et de phrases nominales
    taux_q_pct = round((nb_questions * 100.0) / nb_phrases, 2)
    taux_e_pct = round((nb_exclamations * 100.0) / nb_phrases, 2)
    taux_n_pct = round((nb_nominales * 100.0) / nb_phrases, 2)
    ponct_info = {
        "nb_questions": nb_questions,
        "taux_questions_pct": taux_q_pct,
        "questions_pour_1000_mots": round((nb_questions * 1000.0) / total_mots, 2),
        "nb_exclamations": nb_exclamations,
        "taux_exclamations_pct": taux_e_pct,
        "exclamations_pour_1000_mots": round((nb_exclamations * 1000.0) / total_mots, 2),
        "nb_phrases_nominales": nb_nominales,
        "taux_phrases_nominales_pct": taux_n_pct,
    }

    # 3. Pronoms et marqueurs de posture (je, nous, vous, on, les Français)
    total_marqueurs = max(1, cnt_je + cnt_nous + cnt_vous + cnt_on + cnt_les_francais)

    def _bloc_pronom(c: int) -> dict:
        return {
            "occurrences": c,
            "pour_1000_mots": round((c * 1000.0) / total_mots, 2),
            "part_pct": round((c * 100.0) / total_marqueurs, 2),
        }

    bloc_lf = _bloc_pronom(cnt_les_francais)
    pronoms_info = {
        "je": _bloc_pronom(cnt_je),
        "nous": _bloc_pronom(cnt_nous),
        "vous": _bloc_pronom(cnt_vous),
        "on": _bloc_pronom(cnt_on),
        "les_francais": bloc_lf,
        "les Français": bloc_lf,
        "francais_tous_contextes": {
            "occurrences": cnt_francais_total,
            "pour_1000_mots": round((cnt_francais_total * 1000.0) / total_mots, 2),
        },
        "peuple": {
            "occurrences": cnt_peuple,
            "pour_1000_mots": round((cnt_peuple * 1000.0) / total_mots, 2),
        },
        "ratio_nous_sur_je": round(cnt_nous / max(1, cnt_je), 3),
        "ratio_les_francais_sur_nous": round(cnt_les_francais / max(1, cnt_nous), 3),
    }

    # 5. Formules d'ouverture
    total_ouv = max(1, sum(cat_ouvertures.values()))
    repartition_ouv = {
        k: {
            "occurrences": cat_ouvertures.get(k, 0),
            "part_pct": round((cat_ouvertures.get(k, 0) * 100.0) / total_ouv, 2),
        }
        for k in (
            "adresse_institutionnelle",
            "attaque_ou_contradiction",
            "prise_a_temoin_ou_injonction",
            "affirmation_personnelle_ou_collective",
            "question_initiale",
            "explicative_ou_narrative",
        )
    }
    top_amorces = [
        {
            "amorce": am,
            "occurrences": cnt,
            "part_prises_pct": round((cnt * 100.0) / total_ouv, 2),
            "exemple": exemples_ouvertures.get(am, ""),
        }
        for am, cnt in sorted(amorces_ouvertures.items(), key=lambda x: (-x[1], x[0]))[:15]
        if cnt >= 2
    ]
    ouvertures_info = {
        "nb_prises_analysees": total_ouv,
        "repartition_categories": repartition_ouv,
        "top_amorces": top_amorces,
    }

    # 6. Formules d'adresse
    total_adr = sum(cnt_adresses.values())
    top_adr = [
        {
            "formule": form,
            "occurrences": cnt,
            "pour_1000_mots": round((cnt * 1000.0) / total_mots, 2),
        }
        for form, cnt in sorted(cnt_adresses.items(), key=lambda x: (-x[1], x[0]))
        if cnt > 0
    ]
    adresses_info = {
        "total_occurrences": total_adr,
        "taux_pour_1000_mots": round((total_adr * 1000.0) / total_mots, 2),
        "formules": top_adr,
    }

    return {
        "nb_interventions": nb_prises,
        "nb_phrases": nb_phrases,
        "nb_mots": total_mots,
        "longueur_phrases": longueur_info,
        "ponctuation_et_syntaxe": ponct_info,
        "taux_questions_pct": taux_q_pct,
        "taux_exclamations_pct": taux_e_pct,
        "taux_phrases_nominales_pct": taux_n_pct,
        "pronoms": pronoms_info,
        "formules_ouverture": ouvertures_info,
        "formules_adresse": adresses_info,
    }


def analyser_interruptions_et_duels(enregistrements: list[dict]) -> dict:
    """Mesure 7 : réactions à l'interruption et dynamique de duel en hémicycle."""
    recs_an = [
        r for r in enregistrements
        if str(r.get("situation", "")) in ("interruption", "interpellation", "commission")
        or "contexte_avant" in r
        or "reaction" in r
    ]
    recs_interruption = [r for r in recs_an if str(r.get("situation", "")) == "interruption"]
    recs_avec_ctx = [r for r in recs_an if str(r.get("contexte_avant", "")).strip()]
    recs_avec_react = [r for r in recs_an if str(r.get("reaction", "")).strip()]

    nb_an = len(recs_an)
    nb_int = len(recs_interruption)
    if nb_an == 0:
        return {
            "nb_prises_hemicycle": 0,
            "nb_interruptions_spontanees": 0,
            "part_interruptions_hemicycle_pct": 0.0,
        }

    # Caractérisation des interruptions spontanées émises par le candidat
    mots_int_total = 0
    nb_int_exclam = 0
    nb_int_quest = 0
    registres_int: Counter[str] = Counter()
    exemples_int: list[dict] = []

    for r in recs_interruption:
        txt = nettoyer_texte(str(r.get("texte", "")))
        tl = txt.lower()
        mots = extraire_mots_simples(tl)
        mots_int_total += len(mots)
        if "!" in txt:
            nb_int_exclam += 1
        if "?" in txt:
            nb_int_quest += 1

        if any(w in mots for w in ("faux", "mensonge", "mentez", "inexact", "caricature", "honte")):
            registres_int["dementi_ou_indignation"] += 1
        elif "?" in txt:
            registres_int["question_incisive"] += 1
        elif any(w in mots for w in ("bravo", "exactement", "très", "raison", "merci")):
            registres_int["approbation_ou_ironie"] += 1
        else:
            registres_int["apostrophe_ou_relance"] += 1

        if len(exemples_int) < 10 and 2 <= len(mots) <= 25:
            exemples_int.append({
                "texte": txt,
                "contexte_avant": str(r.get("contexte_avant", ""))[:140],
                "reaction": str(r.get("reaction", "")),
                "date": str(r.get("date", "")),
                "url": str(r.get("url", "")),
            })

    # Réactions provoquées dans l'hémicycle (didascalies AN)
    cnt_applaudissements = 0
    cnt_protestations = 0
    cnt_rires = 0
    for r in recs_avec_react:
        rl = str(r.get("reaction", "")).lower()
        if "applaudissement" in rl:
            cnt_applaudissements += 1
        if "exclamation" in rl or "protestation" in rl or "murmure" in rl or "bruit" in rl:
            cnt_protestations += 1
        if "rire" in rl or "sourire" in rl:
            cnt_rires += 1

    # Reprise en duel après contexte_avant (riposte directe)
    riposte_categories: Counter[str] = Counter()
    for r in recs_avec_ctx:
        phrases = segmenter_phrases(str(r.get("texte", "")))
        cat_ouv, _ = extraire_ouverture_prise(phrases)
        riposte_categories[cat_ouv] += 1

    nb_ctx = max(1, len(recs_avec_ctx))
    nb_int_div = max(1, nb_int)
    return {
        "nb_prises_hemicycle": nb_an,
        "nb_interruptions_spontanees": nb_int,
        "part_interruptions_hemicycle_pct": round((nb_int * 100.0) / nb_an, 2),
        "longueur_moyenne_interruption_mots": round(mots_int_total / nb_int_div, 2) if nb_int > 0 else 0.0,
        "taux_exclamations_en_interruption_pct": round((nb_int_exclam * 100.0) / nb_int_div, 2) if nb_int > 0 else 0.0,
        "taux_questions_en_interruption_pct": round((nb_int_quest * 100.0) / nb_int_div, 2) if nb_int > 0 else 0.0,
        "registres_interruption": {
            k: {
                "occurrences": registres_int.get(k, 0),
                "part_pct": round((registres_int.get(k, 0) * 100.0) / nb_int_div, 2) if nb_int > 0 else 0.0,
            }
            for k in (
                "dementi_ou_indignation",
                "question_incisive",
                "approbation_ou_ironie",
                "apostrophe_ou_relance",
            )
        },
        "reactions_provoquees_hemicycle": {
            "nb_prises_avec_reaction": len(recs_avec_react),
            "taux_prises_avec_reaction_pct": round((len(recs_avec_react) * 100.0) / nb_an, 2),
            "applaudissements": cnt_applaudissements,
            "exclamations_ou_protestations": cnt_protestations,
            "rires_ou_sourires": cnt_rires,
        },
        "reprise_en_duel_apres_contradicteur": {
            "nb_prises_avec_contexte_avant": len(recs_avec_ctx),
            "part_attaque_ou_contradiction_pct": round(
                (riposte_categories.get("attaque_ou_contradiction", 0) * 100.0) / nb_ctx, 2
            ),
            "part_question_initiale_pct": round(
                (riposte_categories.get("question_initiale", 0) * 100.0) / nb_ctx, 2
            ),
            "part_prise_a_temoin_pct": round(
                (riposte_categories.get("prise_a_temoin_ou_injonction", 0) * 100.0) / nb_ctx, 2
            ),
            "part_adresse_institutionnelle_pct": round(
                (riposte_categories.get("adresse_institutionnelle", 0) * 100.0) / nb_ctx, 2
            ),
        },
        "exemples_interruptions": exemples_int,
    }


def extraire_ngrammes_candidat(enregistrements: list[dict]) -> dict[int, Counter[str]]:
    """Extrait les compteurs de 1-grammes, 2-grammes et 3-grammes par phrase."""
    compteurs: dict[int, Counter[str]] = {1: Counter(), 2: Counter(), 3: Counter()}
    for rec in enregistrements:
        phrases = segmenter_phrases(str(rec.get("texte", "")))
        for _brute, _ponct, mots in phrases:
            mots_filtres = [w for w in mots if w not in BRUIT_TRANSCRIPTION and len(w) >= 2]
            n_m = len(mots_filtres)
            # 1-grammes (hors stopwords grammaticaux purs, longueur >= 4)
            for w in mots_filtres:
                if len(w) >= 4 and w not in STOPWORDS_UNIGRAM:
                    compteurs[1][w] += 1
            # 2-grammes (au moins un mot non-stopword de >= 4 lettres)
            for i in range(n_m - 1):
                w1, w2 = mots_filtres[i], mots_filtres[i + 1]
                if w1 == w2:
                    continue
                if (w1 not in STOPWORDS_UNIGRAM and len(w1) >= 4) or (
                    w2 not in STOPWORDS_UNIGRAM and len(w2) >= 4
                ):
                    compteurs[2][f"{w1} {w2}"] += 1
            # 3-grammes (au moins un mot significatif et pas de bégaiement)
            for i in range(n_m - 2):
                w1, w2, w3 = mots_filtres[i], mots_filtres[i + 1], mots_filtres[i + 2]
                if w1 == w2 or w2 == w3:
                    continue
                if any(w not in STOPWORDS_UNIGRAM and len(w) >= 4 for w in (w1, w2, w3)):
                    compteurs[3][f"{w1} {w2} {w3}"] += 1
    return compteurs


def calculer_ngrammes_log_odds(
    ngrammes_par_candidat: dict[str, dict[int, Counter[str]]],
    mots_par_candidat: dict[str, int],
    top_par_taille: int = 20,
    min_freq: int = 5,
) -> dict[str, dict]:
    """Calcule les n-grammes signature par log-odds avec prior informatif de Dirichlet (Monroe et al. 2008).

    Pour chaque candidat i contre le reste du corpus r :
      delta_w = log((y_iw + alpha_w) / (n_i + alpha_0 - y_iw - alpha_w))
              - log((y_rw + alpha_w) / (n_r + alpha_0 - y_rw - alpha_w))
      sigma^2_w = 1 / (y_iw + alpha_w) + 1 / (y_rw + alpha_w)
      z_w = delta_w / sqrt(sigma^2_w)
    """
    resultats: dict[str, dict] = {}
    candidats = sorted(ngrammes_par_candidat.keys())

    for cand in candidats:
        par_taille: dict[str, list[dict]] = {}
        tous_distinctifs: list[dict] = []
        total_mots_cand = max(1, mots_par_candidat.get(cand, 1))
        total_mots_autres = max(
            1, sum(m for c, m in mots_par_candidat.items() if c != cand)
        )

        for k, nom_taille in ((1, "unigrammes"), (2, "bigrammes"), (3, "trigrammes")):
            cnt_i = ngrammes_par_candidat[cand][k]
            cnt_r: Counter[str] = Counter()
            for autre in candidats:
                if autre != cand:
                    cnt_r.update(ngrammes_par_candidat[autre][k])

            vocab = set(cnt_i.keys()) | set(cnt_r.keys())
            n_i = sum(cnt_i.values())
            n_r = sum(cnt_r.values())
            n_tot = max(1, n_i + n_r)
            # Masse totale du prior Dirichlet proportionnelle à la taille des n-grammes
            alpha_0 = 500.0

            candidats_k: list[dict] = []
            for w in vocab:
                y_i = cnt_i.get(w, 0)
                if y_i < min_freq:
                    continue
                y_r = cnt_r.get(w, 0)
                alpha_w = max(0.5, alpha_0 * ((y_i + y_r) / n_tot))

                num_i = y_i + alpha_w
                den_i = max(1.0, (n_i + alpha_0) - num_i)
                num_r = y_r + alpha_w
                den_r = max(1.0, (n_r + alpha_0) - num_r)

                log_odds = math.log(num_i / den_i) - math.log(num_r / den_r)
                if log_odds <= 0:
                    continue
                variance = (1.0 / num_i) + (1.0 / num_r)
                z_score = log_odds / math.sqrt(variance)
                if z_score < 1.96:
                    continue

                item = {
                    "ngramme": w,
                    "taille": k,
                    "occurrences": y_i,
                    "occurrences_autres": y_r,
                    "pour_1000_mots": round((y_i * 1000.0) / total_mots_cand, 3),
                    "pour_1000_mots_autres": round((y_r * 1000.0) / total_mots_autres, 3),
                    "log_odds": round(log_odds, 4),
                    "z_score": round(z_score, 3),
                }
                candidats_k.append(item)

            candidats_k.sort(key=lambda x: (-x["z_score"], -x["log_odds"], x["ngramme"]))
            retenus_k = candidats_k[:top_par_taille]
            par_taille[nom_taille] = retenus_k
            tous_distinctifs.extend(retenus_k)

        tous_distinctifs.sort(key=lambda x: (-x["z_score"], -x["log_odds"], x["ngramme"]))
        resultats[cand] = {
            "methode": "log_odds_dirichlet_monroe_2008",
            "nb_ngrammes_distinctifs": len(tous_distinctifs),
            "top_distinctifs": tous_distinctifs[:45],
            "unigrammes": par_taille.get("unigrammes", []),
            "bigrammes": par_taille.get("bigrammes", []),
            "trigrammes": par_taille.get("trigrammes", []),
        }

    return resultats


def charger_verbatims_candidat(verbatims_dir: Path, slug: str) -> tuple[list[dict], dict]:
    """Charge tous les fichiers <slug>.*.jsonl en filtrant voix_mixtes=True."""
    fichiers = sorted(verbatims_dir.glob(f"{slug}.*.jsonl"))
    retenus: list[dict] = []
    exclus_voix_mixtes = 0
    lignes_totales = 0
    sources_lues: list[str] = []

    for fp in fichiers:
        sources_lues.append(fp.name)
        for line in fp.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s:
                continue
            lignes_totales += 1
            rec = json.loads(s)
            if bool(rec.get("voix_mixtes", False)):
                exclus_voix_mixtes += 1
                continue
            retenus.append(rec)

    meta = {
        "fichiers_sources": sources_lues,
        "lignes_lues_total": lignes_totales,
        "lignes_exclues_voix_mixtes": exclus_voix_mixtes,
        "lignes_retenues_voix_pure": len(retenus),
    }
    return retenus, meta


def decouvrir_candidats(verbatims_dir: Path, filtre_candidats: list[str] | None) -> list[str]:
    if filtre_candidats:
        return sorted(set(filtre_candidats))
    slugs: set[str] = set()
    for fp in sorted(verbatims_dir.glob("*.jsonl")):
        nom = fp.name
        if "." in nom:
            slugs.add(nom.split(".")[0])
    return sorted(slugs)


def calculer_signatures_corpus(
    verbatims_dir: Path,
    candidats: list[str],
    min_freq_ngram: int = 5,
) -> dict[str, dict]:
    """Calcule la signature complète de chaque candidat du corpus."""
    enregistrements_par_cand: dict[str, list[dict]] = {}
    meta_par_cand: dict[str, dict] = {}
    ngrammes_par_cand: dict[str, dict[int, Counter[str]]] = {}
    mots_par_cand: dict[str, int] = {}

    for slug in candidats:
        recs, meta = charger_verbatims_candidat(verbatims_dir, slug)
        if not recs:
            raise ValueError(f"Aucun verbatim voix pure trouvé pour {slug} dans {verbatims_dir}")
        enregistrements_par_cand[slug] = recs
        meta_par_cand[slug] = meta
        ngrammes_par_cand[slug] = extraire_ngrammes_candidat(recs)
        mots_par_cand[slug] = sum(
            len(ph_mots)
            for r in recs
            for _b, _p, ph_mots in segmenter_phrases(str(r.get("texte", "")))
        )

    ngrammes_sign = calculer_ngrammes_log_odds(
        ngrammes_par_cand,
        mots_par_cand,
        top_par_taille=20,
        min_freq=min_freq_ngram,
    )

    signatures: dict[str, dict] = {}
    for slug in candidats:
        recs = enregistrements_par_cand[slug]
        metriques_globales = calculer_metriques_sous_corpus(recs)

        # Regroupement par situation (trié par nom de situation)
        par_sit_recs: dict[str, list[dict]] = defaultdict(list)
        for r in recs:
            sit = str(r.get("situation", "inconnue")).strip() or "inconnue"
            par_sit_recs[sit].append(r)

        par_situation: dict[str, dict] = {}
        for sit in sorted(par_sit_recs.keys()):
            par_situation[sit] = calculer_metriques_sous_corpus(par_sit_recs[sit])

        interruptions_info = analyser_interruptions_et_duels(recs)
        ng_info = ngrammes_sign[slug]

        signatures[slug] = {
            "candidat": slug,
            "version_schema": "1.0",
            "corpus_comparatif": candidats,
            "couverture_corpus": {
                **meta_par_cand[slug],
                "nb_mots_analyses": metriques_globales["nb_mots"],
                "nb_phrases_analysees": metriques_globales["nb_phrases"],
                "situations_couvertes": sorted(par_sit_recs.keys()),
            },
            "global": metriques_globales,
            "par_situation": par_situation,
            "longueur_phrases": metriques_globales["longueur_phrases"],
            "ponctuation_et_syntaxe": metriques_globales["ponctuation_et_syntaxe"],
            "taux_questions_pct": metriques_globales["taux_questions_pct"],
            "taux_exclamations_pct": metriques_globales["taux_exclamations_pct"],
            "taux_phrases_nominales_pct": metriques_globales["taux_phrases_nominales_pct"],
            "pronoms": metriques_globales["pronoms"],
            "ngrammes_signature": ng_info["top_distinctifs"],
            "ngrammes_detail": ng_info,
            "formules_ouverture": metriques_globales["formules_ouverture"],
            "formules_adresse": metriques_globales["formules_adresse"],
            "reactions_interruption": interruptions_info,
        }

    return signatures


def ecrire_signature_json(out_dir: Path, slug: str, payload: dict, avec_backup: bool = True) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    cible = out_dir / f"{slug}.json"
    contenu = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if avec_backup and cible.exists():
        ts = int(time.time())
        bak = out_dir / f"{slug}.json.bak-{ts}"
        shutil.copy2(cible, bak)
    tmp = out_dir / f".{slug}.json.tmp"
    tmp.write_text(contenu, encoding="utf-8")
    tmp.replace(cible)
    return cible


def main(argv: list[str] | None = None) -> int:
    racine_style = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Calcule la signature chiffrée déterministe du style oral par candidat."
    )
    parser.add_argument(
        "--verbatims-dir",
        type=Path,
        default=racine_style / "verbatims",
        help="Répertoire contenant les fichiers <slug>.*.jsonl",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=racine_style / "signature",
        help="Répertoire de sortie pour <slug>.json",
    )
    parser.add_argument(
        "--candidats",
        type=str,
        default="",
        help="Liste de slugs séparés par des virgules (défaut: tous les candidats présents)",
    )
    parser.add_argument(
        "--min-freq-ngram",
        type=int,
        default=5,
        help="Fréquence minimale d'un n-gramme pour le calcul log-odds (défaut: 5)",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Ne pas créer de fichier .bak-<ts> si la cible existe déjà",
    )
    args = parser.parse_args(argv)

    filtre = [c.strip() for c in args.candidats.split(",") if c.strip()] if args.candidats else None
    candidats = decouvrir_candidats(args.verbatims_dir, filtre)
    if len(candidats) < 2:
        print(
            f"ERREUR: au moins 2 candidats requis pour le log-odds comparatif, trouvé: {candidats}",
            file=sys.stderr,
        )
        return 1

    signatures = calculer_signatures_corpus(
        args.verbatims_dir,
        candidats,
        min_freq_ngram=args.min_freq_ngram,
    )
    for slug in candidats:
        cible = ecrire_signature_json(
            args.out_dir,
            slug,
            signatures[slug],
            avec_backup=not args.no_backup,
        )
        sig = signatures[slug]
        nb_mots = sig["couverture_corpus"]["nb_mots_analyses"]
        nb_ng = len(sig["ngrammes_signature"])
        moy_p = sig["longueur_phrases"]["moyenne_mots"]
        iqr_p = sig["longueur_phrases"]["iqr_mots"]
        print(
            f"SIGNATURE_ECRITE {slug} -> {cible} "
            f"(mots={nb_mots}, moy_phrase={moy_p}, iqr={iqr_p}, ngrammes={nb_ng})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
