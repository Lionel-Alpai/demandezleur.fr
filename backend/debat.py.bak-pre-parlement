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

def load_prompt(name: str) -> str:
    """Charge un fichier prompt depuis prompts/debat/"""
    path = PROMPTS_DIR / "debat" / f"{name}.txt"
    return path.read_text(encoding="utf-8")


def load_ton_famille(famille: str) -> str:
    """Charge le prompt de ton militant pour une famille politique."""
    path = PROMPTS_DIR / f"ton_{famille}.txt"
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
) -> str:
    """Construit le prompt système complet pour un candidat à un tour donné."""
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

    # Récupérer le RAG pour ce candidat sur ce sujet/question
    query = question_moderateur or sujet
    rag_context = search_corpus_cached(
        candidat["id"], 
        query, 
        top_k=top_k, 
        window=RAG_WINDOW_DEBAT, 
        cache=cache_rag
    )
    
    # Remplir le template
    prompt = template.format(
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
    
    return prompt


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
