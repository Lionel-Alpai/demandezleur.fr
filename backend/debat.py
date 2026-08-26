# debat.py
"""
Logique métier du mode débat demandezleur.fr
Indépendant de FastAPI pour testabilité.
"""

import random
import json
import os
import hashlib
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
MAX_TOKENS_DEBAT = 200
TEMPERATURE_DEBAT = 0.8
MAX_TOKENS_ARENE = 320       # [parlement] mode arène : on laisse la place à la citation
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
}


def load_ton_famille(famille: str) -> str:
    """Charge le prompt de ton militant pour une famille politique."""
    path = PROMPTS_DIR / f"{TON_PAR_FAMILLE.get(famille, 'ton_' + str(famille))}.txt"
    # Fallback si le fichier spécifique à la famille n'existe pas
    if not path.exists():
        return "Sois convaincant, poli et fidèle à tes convictions."
    return path.read_text(encoding="utf-8")


def randomiser_ordre(candidats_ids: list[str]) -> list[str]:
    """Randomise l'ordre de parole. Sécurité équité."""
    ordre = candidats_ids.copy()
    random.shuffle(ordre)
    return ordre


def formater_historique(historique: list[dict], exclure_candidat: str = None) -> str:
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
            
            lignes.append(f"[{intervention['candidat_nom']}] : {texte}")
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
    ton = load_ton_famille(candidat["famille"])
    
    # Formater l'historique (en excluant le candidat lui-même s'il a déjà parlé)
    historique_txt = formater_historique(historique, exclure_candidat=candidat["id"])
    
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
                + ("\nPersonne n'a encore interpellé : " + ", ".join(jamais) + "." if jamais else "")
                + "\nRÈGLE DE DIVERSITÉ (bloquante) : ne reprends NI l'argument NI la formule d'un candidat qui a parlé avant toi dans ce tour. "
                + (f"INTERDIT d'interpeller {', '.join(n for n, c in compte.items() if c >= 1)} une nouvelle fois dans ce tour tant que {', '.join(jamais)} n'ont pas été interpellés : ton adversaire nommé est l'un d'eux. " if jamais and compte else "")
                + "Si tu reviens malgré tout sur un adversaire déjà visé, prends un angle que personne n'a pris (ton programme, une autre pièce, un autre fait). "
                  "Tu ne dis jamais « vous nous ressortez » ni « encore » à propos d'un argument que tu n'as pas toi-même déjà réfuté."
            )

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
            return c
    raise ValueError(f"Candidat inconnu : {candidat_id}")
