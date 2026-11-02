# debat.py
"""
Logique métier du mode débat demandezleur.fr
Indépendant de FastAPI pour testabilité.
"""

import random
import json
import os
import hashlib
import re as _re
from pathlib import Path
from typing import Iterator

# Chemins relatifs au dossier du projet
BASE_DIR = Path(__file__).parent
PROMPTS_DIR = BASE_DIR / "prompts"
CORPUS_DIR = BASE_DIR / "corpus"

# Constantes
MAX_CANDIDATS = 5
MIN_CANDIDATS = 2
MAX_TOURS = 5
MAX_TOKENS_DEBAT = 400       # 200 coupait 8 % des repliques en pleine phrase (mesure 27/10)
TEMPERATURE_DEBAT = 0.8
MAX_TOKENS_ARENE = 520       # [parlement] mode arène : on laisse la place à la citation
TEMPERATURE_ARENE = 0.95     # [parlement] mode arène : plus mordant
RAG_TOP_K_OUVERTURE = 2       # Tour d'ouverture : le candidat a besoin de matière pour poser sa vision
RAG_TOP_K_INTERPELLE = 2      # Candidat interpellé : même logique, il doit répondre en profondeur
RAG_TOP_K_REACTION = 1        # Réaction rapide : un seul bloc suffit, le candidat réagit aux autres
RAG_TOP_K_TOUR_SUIVANT = 1    # Tour suivant : idem, c'est une réaction croisée
RAG_WINDOW_DEBAT = 400
HISTORIQUE_TRONCATURE_CHARS = 500  # Nombre max de caractères par intervention dans l'historique (~100 tokens)

def hash_query(query: str) -> str:
    """Hash court d'une requête pour servir de clé de cache."""
    return hashlib.md5(query.encode("utf-8")).hexdigest()[:16]

def search_corpus_cached(candidat_id: str, query: str, top_k: int, window: int, cache: dict) -> str:
    """Version cachée de search_corpus. Le cache est passé explicitement en paramètre
    pour qu'il soit lié à la durée d'un débat."""
    from api import search_corpus
    
    cle = (candidat_id, hash_query(query), top_k, window)
    if cache is not None and cle in cache:
        return cache[cle]
    
    resultat = search_corpus(candidat_id, query, top_k=top_k, window=window)
    if cache is not None:
        cache[cle] = resultat
    return resultat

def search_blocs_cached(candidat_id: str, query: str, top_k: int, cache: dict) -> list:
    """Comme search_corpus_cached mais renvoie les blocs (pour les preuves). Même cache."""
    from api import load_corpus
    import preuves
    cle = ("blocs", candidat_id, hash_query(query), top_k)
    if cache is not None and cle in cache:
        return cache[cle]
    blocs = preuves.rechercher_blocs(load_corpus(candidat_id), query, top_k=top_k)
    if cache is not None:
        cache[cle] = blocs
    return blocs


def load_prompt(name: str) -> str:
    """Charge un fichier prompt depuis prompts/debat/"""
    path = PROMPTS_DIR / "debat" / f"{name}.txt"
    return path.read_text(encoding="utf-8")


# Famille politique -> fichier de ton (miroir de hugo-src/data/familles.json, champ "ton")
TON_PAR_FAMILLE = {
    "extreme_gauche": "ton_extreme_gauche",
    "gauche": "ton_gauche",
    "ecologistes": "ton_ecologie",
    "centre": "ton_centre",
    "droite": "ton_droite",
    "souverainistes": "ton_souverainiste",
    "extreme_droite": "ton_extreme_droite",
    "non_classe": None,  # famille politique indéterminée : ton générique
}

# Brique demandez-leur-le-champ-famille-fait-double-emploi (23/09/2026) : `famille` ne porte
# plus que l'APPARTENANCE POLITIQUE ; le MODE DE SOURÇAGE vit dans le seul booléen
# `sans_source_officielle`. Ancienne valeur tolérée en lecture (fiches produites avant la
# dissociation) : famille "sans-source-officielle" => famille "non_classe" + booléen vrai.
FAMILLE_HERITEE_SANS_SOURCE = "sans-source-officielle"
TON_SANS_SOURCE = "ton_sans-source-officielle"


def normaliser_candidat(c: dict) -> dict:
    """Rend un candidat à la forme dissociée (famille politique + booléen de sourçage)."""
    c = dict(c)
    if c.get("famille") == FAMILLE_HERITEE_SANS_SOURCE:
        c["famille"] = "non_classe"
        c["sans_source_officielle"] = True
    c["sans_source_officielle"] = bool(c.get("sans_source_officielle"))
    return c


TON_GENERIQUE = "Sois convaincant, poli et fidèle à tes convictions."


def _lire_ton(nom) -> str:
    if not nom:
        return ""
    path = PROMPTS_DIR / f"{nom}.txt"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def load_ton_famille(famille: str) -> str:
    """Charge le prompt de ton militant pour une famille politique."""
    return _lire_ton(TON_PAR_FAMILLE.get(famille, "ton_" + str(famille))) or TON_GENERIQUE


def ton_candidat(c: dict) -> str:
    """Ton complet d'un candidat : ton de sa famille politique, puis, s'il n'a publié aucun
    programme consultable, la consigne d'absence (les deux dimensions se composent)."""
    c = normaliser_candidat(c)
    ton = load_ton_famille(c.get("famille", ""))
    if c["sans_source_officielle"]:
        ton = ton.rstrip() + "\n\n" + _lire_ton(TON_SANS_SOURCE)
    return ton


def randomiser_ordre(candidats_ids: list[str]) -> list[str]:
    """Randomise l'ordre de parole. Sécurité équité."""
    ordre = candidats_ids.copy()
    random.shuffle(ordre)
    return ordre


_MOT = _re.compile(r"[0-9a-zàâäçéèêëîïôöùûüÿœ]+(?:'[0-9a-zàâäçéèêëîïôöùûüÿœ]+)*")
_CITATION = _re.compile(r"[«“\"]\s*([^»”\"]{8,400}?)\s*[»”\"]")
_COUPE_PHRASES = _re.compile(r"(?<=[.!?…])\s+")
_MAX_DEJA_DIT = 12


def _norm_mots(texte: str) -> list:
    """Mots d'un texte, en minuscules, apostrophes normalisées (clé de comparaison des répliques)."""
    return _MOT.findall((texte or "").lower().replace("\u2019", "'"))


def _occurrences(mots: list, sous: tuple) -> int:
    n = len(sous)
    if not n:
        return 0
    return sum(1 for k in range(len(mots) - n + 1) if tuple(mots[k:k + n]) == sous)


def _interventions_a_plat(historique) -> list:
    return [(i.get("candidat_nom") or i.get("candidat_id") or "?", i.get("texte", ""))
            for t in (historique or []) for i in t.get("interventions", [])]


def citations_deja_dites(historique) -> list:
    """[(texte, n, {orateur: fois})] : citations entre guillemets (5 mots ou plus, ou 3 mots et plus si répétées)
    et formules de 6 mots ou plus reprises, TOUS TOURS CONFONDUS. n = nombre de répliques qui la contiennent."""
    inter = [(nom, _norm_mots(brut), brut) for nom, brut in _interventions_a_plat(historique)]
    citees, formules = {}, {}
    for _, _, brut in inter:
        for m in _CITATION.finditer(brut.replace("\u2019", "'")):
            q = tuple(_norm_mots(m.group(1)))
            if len(q) >= 3 and q not in citees:
                citees[q] = m.group(1).strip()
    N = 6
    grammes = {}
    for idx, (_, mots, _) in enumerate(inter):
        for k in range(len(mots) - N + 1):
            grammes.setdefault(tuple(mots[k:k + N]), set()).add(idx)
    for _, mots, _ in inter:
        k = 0
        while k <= len(mots) - N:
            if len(grammes[tuple(mots[k:k + N])]) >= 2:
                j = k
                while j + 1 <= len(mots) - N and len(grammes[tuple(mots[j + 1:j + 1 + N])]) >= 2:
                    j += 1
                formules.setdefault(tuple(mots[k:j + N]), " ".join(mots[k:j + N]))
                k = j + 1
            else:
                k += 1
    gardees = []
    for source, est_citation in ((citees, True), (formules, False)):
        for q, affichage in source.items():
            par = {}
            for nom, mots, _ in inter:
                c = _occurrences(mots, q)
                if c:
                    par[nom] = par.get(nom, 0) + c
            n = sum(1 for _, mots, _ in inter if _occurrences(mots, q))
            if n == 0:
                continue
            if est_citation and (len(q) >= 5 or n >= 2) or (not est_citation and n >= 2):
                gardees.append((q, affichage, n, par))
    # une suite incluse dans une plus longue citée aussi souvent est redondante
    finales = []
    for q, aff, n, par in gardees:
        if any(q2 != q and len(q2) > len(q) and n2 >= n and _occurrences(list(q2), q) for q2, _, n2, _ in gardees):
            continue
        finales.append((q, aff, n, par))
    finales.sort(key=lambda e: (-e[2], -len(e[0])))
    vus, sortie = set(), []
    for q, aff, n, par in finales:
        if q in vus:
            continue
        vus.add(q)
        sortie.append((aff, n, par))
    return sortie[:_MAX_DEJA_DIT]


def _phrases(texte: str) -> list:
    return [p.strip() for p in _COUPE_PHRASES.split((texte or "").strip()) if p.strip()]


def derniere_replique(candidat_id: str, historique) -> str:
    for t in reversed(historique or []):
        for i in reversed(t.get("interventions", [])):
            if i.get("candidat_id") == candidat_id:
                return i.get("texte", "")
    return ""


def questions_en_suspens(candidat: dict, historique) -> tuple:
    """(questions posées à ce candidat par les autres, questions qu'il a posées dans sa dernière réplique)."""
    nom_court = candidat["nom"].split()[-1].lower()
    recues, posees = [], []
    for t in historique or []:
        for i in t.get("interventions", []):
            qs = [p for p in _phrases(i.get("texte", "")) if p.endswith("?")]
            if i.get("candidat_id") == candidat["id"]:
                posees = qs
            else:
                recues += [(i.get("candidat_nom") or "?", p) for p in qs if nom_court in p.lower()]
    return recues[-2:], posees[:2]


def bloc_deja_dit(candidat: dict, historique, mode: str) -> str:
    """Bloc « DÉJÀ DIT DANS CE DÉBAT » : citations et formules déjà prononcées, règle d'interdiction, questions."""
    if not historique or not any(t.get("interventions") for t in historique):
        return ""
    lignes = []
    for aff, n, par in citations_deja_dites(historique):
        qui = ", ".join(f"{nom} ×{c}" for nom, c in sorted(par.items(), key=lambda e: -e[1]))
        aff = aff if len(aff) <= 160 else aff[:160].rsplit(" ", 1)[0] + "…"
        if n >= 2:
            lignes.append(f"— « {aff} » — dite dans {n} répliques ({qui}) → INTERDITE, ne la reprends sous aucune forme")
        else:
            lignes.append(f"— « {aff} » — dite une fois ({qui}) → tu ne peux la reprendre que pour la RETOURNER contre celui qui l'a servie")
    texte = "\n\nDÉJÀ DIT DANS CE DÉBAT (tous tours confondus ; [TOI] dans l'historique = tes propres répliques) :\n"
    texte += "\n".join(lignes) if lignes else "— (aucune citation reprise pour l'instant)"
    texte += ("\nRÈGLE (bloquante) : une citation déjà prononcée DEUX fois est INTERDITE ; prononcée une fois, elle n'est permise que pour la RETOURNER contre celui qui l'a servie. "
              "Même règle pour toute formule de 6 mots ou plus déjà employée par quelqu'un dans ce débat. "
              "Un argument que tu as déjà développé ([TOI]) est INTERDIT de resservir : prends un autre angle ou réponds à ce qui vient d'être dit.")
    if mode == "arene":
        recues, posees = questions_en_suspens(candidat, historique)
        if recues:
            texte += "\nQuestions qu'on t'a posées : " + " | ".join(f"{nom} : « {q[:200]} »" for nom, q in recues) + " — si tu ne réponds pas, dis-le franchement, ne fais pas semblant."
        if posees:
            texte += "\nQuestions que tu as posées : " + " | ".join(f"« {q[:200]} »" for q in posees) + " — si l'adversaire visé n'y a pas répondu depuis, fais-le-lui remarquer (« vous n'avez pas répondu à ma question »)."
    return texte


def bloc_forme_arene(candidat: dict, tour: int, historique, position_dans_tour: int, nb_candidats: int) -> str:
    """Fin de prompt de l'Arène (ping-pong, dl-arene-ping-pong-et-tension) : coup précédent à ne pas refaire,
    tension qui monte par tour, une RÉACTION À CHAUD par tour à partir du tour 2."""
    out = ""
    phrases = _phrases(derniere_replique(candidat["id"], historique))
    if phrases:
        out += ("\n\nTA RÉPLIQUE PRÉCÉDENTE finissait par : « " + phrases[-1][:200] + " ». "
                "INTERDIT de refaire le même coup (même ressort, même chute) : choisis 1 ou 2 AUTRES coups dans la BOÎTE À COUPS.")
    tension = {1: "TOUR 1 : posé, tu installes ta voix.", 2: "TOUR 2 : ça se tend — tu peux couper."}.get(
        tour, "TOUR 3 ET SUIVANTS : ça chauffe — réaction à chaud permise, coupure bienvenue.")
    court = (nb_candidats - 1 - (max(1, tour) - 1)) % max(1, nb_candidats)
    if tour >= 2 and position_dans_tour == court:
        out += f"\n\n{tension} FORME : RÉACTION À CHAUD — de 3 mots à une phrase : une coupure, une exclamation, une question-éclair, dans TA voix."
    else:
        out += f"\n\n{tension} FORME : de 3 mots à 4 phrases, au rythme de TA voix ; ne décalque ni la longueur ni l'ouverture des répliques précédentes ; réagis d'abord à la DERNIÈRE intervention adverse."
    return out


def formater_historique(historique: list[dict], exclure_candidat: str = None, moi: str = None) -> str:
    """Formate l'historique du débat en texte pour injection dans le prompt."""
    if not historique:
        return "(Début du débat, aucune intervention précédente.)"
    
    lignes = []
    for tour_data in historique:
        lignes.append(f"=== Tour {tour_data['tour']} ===")
        if tour_data.get("question_moderateur"):
            cible = tour_data.get("candidat_interpelle_nom", "")
            if cible:
                lignes.append(f"[Question du modérateur à {cible}] : {tour_data['question_moderateur']}")
            else:
                lignes.append(f"[Question du modérateur] : {tour_data['question_moderateur']}")
        
        interventions = tour_data.get("interventions", [])
        for intervention in interventions:
            if exclure_candidat and intervention["candidat_id"] == exclure_candidat:
                continue
            
            texte = intervention["texte"]
            if len(texte) > HISTORIQUE_TRONCATURE_CHARS:
                # Tronquer au dernier espace avant la limite
                texte = texte[:HISTORIQUE_TRONCATURE_CHARS].rsplit(" ", 1)[0] + "…"
            
            etiquette = "TOI" if moi and intervention["candidat_id"] == moi else intervention["candidat_nom"]
            lignes.append(f"[{etiquette}] : {texte}")
        lignes.append("")
    
    return "\n".join(lignes)


def construire_prompt_debat(
    candidat: dict,
    tour: int,
    type_tour: str,  # "ouverture" | "tour_suivant" | "intervention"
    sujet: str,
    historique: list[dict],
    question_moderateur: str = None,
    candidat_interpelle: dict = None,
    est_interpelle: bool = False,
    position_dans_tour: int = 0,
    cache_rag: dict = None,
    mode: str = "standard",  # [parlement]
    adversaires: list = None,
) -> tuple:
    """Construit le prompt système d'un candidat pour un tour. Retourne (prompt, preuves) où
    preuves = liste publique des pièces utilisées (programme, pièce Assemblée, programmes adverses)."""
    # Charger le bon template selon le type de tour
    if type_tour == "intervention" and est_interpelle:
        template = load_prompt("base_interpelle")
    elif type_tour == "intervention":
        template = load_prompt("base_reaction")
    elif type_tour == "tour_suivant":
        template = load_prompt("base_tour_suivant")
    else:  # ouverture
        template = load_prompt("base_ouverture")
    
    # Charger le ton de la famille politique
    ton = ton_candidat(candidat)
    
    # Formater l'historique (en excluant le candidat lui-même s'il a déjà parlé)
    historique_txt = formater_historique(historique, moi=candidat["id"])  # le candidat se voit : [TOI]
    
    # Note spéciale pour l'ouverture selon position
    autres_ont_parle_note = ""
    if type_tour == "ouverture" and position_dans_tour > 0:
        autres_ont_parle_note = "\nDes candidats avant toi ont déjà exposé leur position. Présente la tienne en tenant compte de ce qui a été dit."
    
    # Note pour les réactions selon si d'autres ont déjà réagi
    reponses_autres_note = ""
    if type_tour == "intervention" and not est_interpelle and position_dans_tour > 1:
        reponses_autres_note = ", ainsi que celles des autres candidats qui ont déjà réagi"
    
    # Choix du top_k selon le type de tour
    if type_tour == "ouverture":
        top_k = RAG_TOP_K_OUVERTURE
    elif type_tour == "intervention" and est_interpelle:
        top_k = RAG_TOP_K_INTERPELLE
    elif type_tour == "intervention":
        top_k = RAG_TOP_K_REACTION
    else:  # tour_suivant
        top_k = RAG_TOP_K_TOUR_SUIVANT

    # Récupérer le RAG pour ce candidat sur ce sujet/question (blocs -> contexte + preuves)
    import preuves as _preuves
    query = question_moderateur or sujet
    blocs = search_blocs_cached(candidat["id"], query, top_k=top_k, cache=cache_rag)
    rag_context = _preuves.formater_contexte(blocs, window=RAG_WINDOW_DEBAT)
    liste_preuves = _preuves.vers_preuves(blocs, candidat["id"])
    
    # Consigne d'Arène : partie STABLE, placée avant les extraits pour rester dans le préfixe mis en cache
    consigne_arene = ""
    if mode == "arene":
        consigne_path = PROMPTS_DIR / "debat" / "consigne_arene.txt"
        if consigne_path.exists():
            consigne_arene = "\n" + consigne_path.read_text(encoding="utf-8").strip() + "\n"
            if type_tour == "ouverture":
                consigne_arene += "\nOUVERTURE : personne n'a encore parlé. Tu n'attaques donc pas des propos tenus ici — tu attaques le PROGRAMME d'un adversaire présent à partir de ses pièces, ou tu poses ta ligne.\n"

    # Remplir le template
    prompt = template.format(
        consigne_arene=consigne_arene,
        candidat_nom=candidat["nom"],
        candidat_parti=candidat["parti"],
        ton_famille_politique=ton,
        rag_context=rag_context,
        historique_debat=historique_txt,
        sujet=sujet,
        question_moderateur=question_moderateur or "",
        candidat_interpelle_nom=candidat_interpelle["nom"] if candidat_interpelle else "",
        autres_ont_parle_note=autres_ont_parle_note,
        reponses_autres_note=reponses_autres_note,
    )
    
    # A.1 — matière sur les ADVERSAIRES présents : leur programme officiel + faits structurés.
    # Sans cela, « attaque un adversaire nommé » ne peut se satisfaire qu'en inventant.
    adversaires = [a for a in (adversaires or []) if a.get("id") != candidat["id"]]
    if adversaires:
        faits = charger_faits()
        lignes = []
        for adv in adversaires:
            k_adv = 2 if mode == "arene" else 1
            tous_adv = search_blocs_cached(adv["id"], query, top_k=k_adv * 3, cache=cache_rag)
            # rotation par position dans le tour : les orateurs successifs ne reçoivent pas les mêmes extraits adverses
            dec = (position_dans_tour * k_adv) % max(1, len(tous_adv)) if tous_adv else 0
            blocs_adv = (tous_adv[dec:] + tous_adv[:dec])[:k_adv]
            nom_adv = f"{adv['nom']} ({adv.get('parti_court') or adv.get('parti', '')})"
            if blocs_adv:
                for b in blocs_adv:
                    txt = b.get("text", "")
                    txt = txt[:300] + "..." if len(txt) > 300 else txt
                    lignes.append(f"— {nom_adv} [Source: {b.get('source', '?')}, page {b.get('page', 'N/A')}] : « {txt} »")
                liste_preuves.extend(_preuves.vers_preuves(blocs_adv, adv["id"], type_defaut="adversaire", extrait_max=200))
            else:
                lignes.append(f"— {nom_adv} : son programme ne contient AUCUN extrait sur ce sujet. Tu peux le lui reprocher, rien d'autre.")
            f = faits.get(adv["id"]) or {}
            if f:
                statut = "a été membre d'un gouvernement (" + ", ".join(f.get("fonctions_passees") or []) + ")" if f.get("a_gouverne") else "n'a JAMAIS été membre d'un gouvernement — aucun « bilan gouvernemental », aucun « votre ministère », aucune « année au pouvoir » ne peut lui être reproché"
                depute = "député(e) en exercice" if f.get("depute") else "n'est PAS député(e) — ne lui attribue aucun vote à l'Assemblée"
                lignes.append(f"  FAIT : {adv['nom']} {statut} ; {depute}.")
        prompt += (
            "\n\nPIÈCES SUR TES ADVERSAIRES (leur programme officiel et des faits vérifiés — SEULE matière autorisée pour parler d'eux) :\n"
            + "\n".join(lignes)
            + "\nRÈGLE : toute affirmation sur le programme, le bilan, les votes ou les fonctions d'un adversaire doit s'appuyer sur une de ces pièces. Sinon, tu ne la fais pas."
        )

    # [parlement] mode arene : consigne + pièce Assemblée (verbatim officiel)
    if mode == "arene":
        try:
            import parlement as _p
            if True:
                seqs = []
                try:
                    import themes_parlement as _tp
                    bruts = _p.sujets(n=64).get("sujets", [])
                    trouve = _tp.trouver_sujet(sujet, bruts)
                    if trouve:
                        seqs = _p.sequences_de(trouve.get("cr_uid"), trouve.get("segment"), n=6)
                except Exception:
                    seqs = []
                if not seqs:
                    seqs = _p.sequences_pour_sujet(sujet, n=6)
                if not seqs:
                    prompt += ("\n\nPIÈCE AU DOSSIER : aucune — aucune séance de l'Assemblée dans nos archives ne traite de ce sujet précis. "
                               "Si le sujet nomme un texte de loi, un projet, un événement ou un sigle que ni tes extraits de programme ni les pièces ne décrivent, "
                               "tu ne fais AUCUNE affirmation sur son contenu : tu dis que tu n'as pas ce texte sous les yeux, et tu débats du PRINCIPE que le sujet pose, à partir de ton programme.")
                if seqs:
                    # Une pièce DIFFÉRENTE par orateur : on écarte celles déjà citées dans le débat, puis rotation par position
                    import dossiers as _dd
                    textes_deb = [i.get("texte", "") for t in (historique or []) for i in t.get("interventions", [])]
                    libres = [q for q in seqs if not _dd.deja_cite(q.get("texte", "")[:400], textes_deb, seuil=4)] or seqs
                    sq = libres[position_dans_tour % len(libres)]
                    prompt += (
                        "\n\nPIÈCE AU DOSSIER — verbatim officiel de l'Assemblée nationale, sur « "
                        + (sq.get("libelle") or sq["titre"]) + " » :\n"
                        + "« " + sq["texte"] + " »\n"
                        + "— " + sq["orateur"] + ", séance du " + sq["date_lisible"] + "\n"
                        + "Tu peux la citer TELLE QUELLE. Tu n'inventes JAMAIS une autre citation."
                    )
                    liste_preuves.append({
                        "type": "piece", "candidat_id": candidat["id"],
                        "titre": sq.get("libelle") or sq["titre"], "page": sq["titre"], "theme": "",
                        "extrait": (sq["texte"][:280].rsplit(" ", 1)[0] + "…") if len(sq["texte"]) > 280 else sq["texte"],
                        "texte_integral": sq["texte"],
                        "orateur": sq["orateur"], "date_lisible": sq["date_lisible"], "url": sq.get("url", ""),
                    })
        except Exception:
            pass

    # DANS CE TOUR — qui a déjà été interpellé, avec quel argument : on impose la diversité
    if adversaires and historique:
        courant = [t for t in historique if t.get("tour") == tour]
        interventions = courant[-1].get("interventions", []) if courant else []
        if interventions:
            noms = {a["id"]: a["nom"] for a in adversaires}
            noms[candidat["id"]] = candidat["nom"]
            lignes, compte = [], {}
            for i in interventions:
                txt = i.get("texte", "")
                vises = [n for cid, n in noms.items() if cid != i.get("candidat_id") and n.split()[-1] in txt]
                for v in vises:
                    compte[v] = compte.get(v, 0) + 1
                premiere = txt.split(". ")[0][:160]
                lignes.append(f"— {i.get('candidat_nom', i.get('candidat_id'))} a interpellé {', '.join(vises) or 'personne'} ; son angle : « {premiere}… »")
            jamais = [n for cid, n in noms.items() if cid != candidat["id"] and n not in compte]
            prompt += (
                "\n\nDANS CE TOUR, AVANT TOI :\n" + "\n".join(lignes)
                + ("\nVise de préférence : " + ", ".join(jamais) + "." if jamais else "")
                + "\nRÈGLE DE DIVERSITÉ (bloquante) : ne reprends NI l'argument NI la formule d'un candidat qui a parlé avant toi dans ce tour. "
                + (f"INTERDIT d'interpeller {', '.join(n for n, c in compte.items() if c >= 1)} une nouvelle fois dans ce tour tant que {', '.join(jamais)} n'ont pas été interpellés : ton adversaire nommé est l'un d'eux. " if jamais and compte else "")
                + "Si tu reviens malgré tout sur un adversaire déjà visé, prends un angle que personne n'a pris (ton programme, une autre pièce, un autre fait). "
                  "Tu ne dis jamais « vous nous ressortez » ni « encore » à propos d'un argument que tu n'as pas toi-même déjà réfuté."
            )

    # ARÈNE — pièces d'ACTUALITÉ (déclarations verbatim des adversaires présents, faits datés), pertinentes au sujet
    if mode == "arene" and adversaires:
        try:
            import actu as _a
            ids_adv = {a["id"] for a in adversaires}
            dernieres = [i.get("texte", "") for t in (historique or [])[-1:] for i in t.get("interventions", []) if i.get("candidat_id") in ids_adv]
            texte_actu, preuves_actu = _a.pieces_pour(sujet if not question_moderateur else sujet + " " + question_moderateur, candidat, adversaires, " ".join(dernieres),
                                                   textes_debat=[i.get("texte", "") for t in (historique or []) for i in t.get("interventions", [])])
            if texte_actu:
                prompt += texte_actu
                liste_preuves.extend(preuves_actu)
        except Exception:
            pass

    # ARÈNE — FICHES (état du monde) : la situation politique du jour est injectée en TÊTE du prompt, et la FICHE ENTIÈRE de tout événement
    # touché par le sujet, la question ou une pièce d'actu (jamais une pièce orpheline) ; fiches validées par la machine (actu_fiches.py)
    _tete_monde = ""
    if mode == "arene":
        try:
            import actu_fiches as _af
            _requete_monde = " ".join([sujet or "", question_moderateur or "", locals().get("texte_actu") or ""])
            _tete_monde, _corps_monde, _preuves_monde = _af.bloc_etat_du_monde(_requete_monde)
            prompt += _corps_monde
            for _p in _preuves_monde:
                _p["candidat_id"] = candidat["id"]
            liste_preuves.extend(_preuves_monde)
        except Exception:
            _tete_monde = ""

    # ARÈNE — le DOSSIER (faits vérifiés + reproches documentés), en fin de prompt : c'est la dernière chose lue
    if mode == "arene" and adversaires:
        try:
            import dossiers as _d
            textes_debat = [i.get("texte", "") for t in (historique or []) for i in t.get("interventions", [])]
            ids_adv = {a["id"] for a in adversaires}
            dernieres_adv = [i.get("texte", "") for t in (historique or [])[-1:] for i in t.get("interventions", []) if i.get("candidat_id") in ids_adv]
            requete = " ".join([sujet, question_moderateur or ""])
            texte_dossier, preuves_dossier = _d.pieces_pour(candidat, adversaires, textes_debat, requete, " ".join(dernieres_adv))
            if texte_dossier:
                prompt += texte_dossier
                liste_preuves.extend(preuves_dossier)
        except Exception:
            pass
    # DÉJÀ DIT (standard et Arène) puis, en Arène, coup à changer et forme : la dernière chose lue
    prompt += bloc_deja_dit(candidat, historique, mode)
    if mode == "arene":
        prompt += bloc_forme_arene(candidat, tour, historique, position_dans_tour, len(adversaires or []) + 1)
    if mode == "arene":
        prompt += "\n\nÉVÉNEMENTS RÉCENTS : tu ne sais d'un événement de 2026 QUE ce que disent les pièces. Tu n'attribues JAMAIS un auteur, un mobile, une idéologie, une religion, une nationalité ou une origine qui n'est pas écrit dans une pièce. Si la pièce dit raciste, c'est raciste. Si rien n'est dit, tu n'en dis rien. Tu ne prêtes à personne, ni à toi-même, une déclaration publique (« j'ai dit », « vous avez déclaré ») sans pièce verbatim. Tu gardes ta ligne politique (tu peux parler d'un sujet EN GÉNÉRAL), jamais en l'accrochant à un fait que les pièces contredisent ou ne disent pas.\n"
    if _tete_monde:
        prompt = _tete_monde + prompt
    return prompt, liste_preuves


_FAITS = None


def charger_faits() -> dict:
    """faits.json -> {candidat_id: {a_gouverne, depute, mandats, fonctions_passees}}."""
    global _FAITS
    if _FAITS is None:
        path = BASE_DIR / "faits.json"
        try:
            _FAITS = json.loads(path.read_text(encoding="utf-8")).get("candidats", {}) if path.exists() else {}
        except Exception:
            _FAITS = {}
    return _FAITS


def valider_requete_debat(payload: dict) -> tuple[bool, str]:
    """Valide une requête de débat entrante. Retourne (valide, message_erreur)."""
    candidats = payload.get("candidats", [])
    if not isinstance(candidats, list):
        return False, "candidats doit être une liste"
    if len(candidats) < MIN_CANDIDATS:
        return False, f"Au moins {MIN_CANDIDATS} candidats requis"
    if len(candidats) > MAX_CANDIDATS:
        return False, f"Maximum {MAX_CANDIDATS} candidats"
    
    tour = payload.get("tour", 1)
    if tour < 1 or tour > MAX_TOURS:
        return False, f"Numéro de tour invalide (1 à {MAX_TOURS})"
    
    sujet = payload.get("sujet", "").strip()
    if not sujet:
        return False, "Sujet manquant"
    if len(sujet) > 500:
        return False, "Sujet trop long (500 caractères max)"
    
    type_tour = payload.get("type_tour", "ouverture")
    if type_tour not in ("ouverture", "tour_suivant", "intervention"):
        return False, "type_tour invalide"
    
    if type_tour == "intervention":
        if not payload.get("question_moderateur", "").strip():
            return False, "question_moderateur requise pour une intervention"
        candidat_interpelle_id = payload.get("candidat_interpelle_id")
        if not candidat_interpelle_id:
            return False, "candidat_interpelle_id requis pour une intervention"
        if candidat_interpelle_id not in candidats:
            return False, "candidat_interpelle_id doit être dans la liste des candidats"
    
    mode = payload.get("mode", "standard")  # [parlement]
    if mode not in ("standard", "arene"):
        return False, "mode invalide"
    return True, ""


def charger_candidat(candidat_id: str) -> dict:
    """Charge les métadonnées d'un candidat depuis data/candidats.json."""
    path = BASE_DIR / "candidats.json"
    if not path.exists():
        raise FileNotFoundError(f"Fichier candidats.json non trouvé dans {BASE_DIR}")
        
    with open(path, encoding="utf-8") as f:
        tous = json.load(f)
    for c in tous:
        if c["id"] == candidat_id:
            return normaliser_candidat(c)
    raise ValueError(f"Candidat inconnu : {candidat_id}")
