"""
Rate limiter simple en mémoire pour demandezleur.fr
Limite les requêtes par IP et par type d'action, avec reset quotidien à minuit.

Philosophie : zéro persistance, zéro tracking, zéro donnée stockée au-delà
de la journée en cours. Cohérent avec le positionnement "zéro tracking" du projet.
"""

import asyncio
from datetime import datetime, time as dtime, timedelta
from threading import Lock
from typing import Literal

# ============================================================================
# Limites — facilement ajustables
# ============================================================================
LIMITE_CHAT_PAR_JOUR = 20
LIMITE_DEBAT_COURT_PAR_JOUR = 3
LIMITE_DEBAT_LONG_PAR_JOUR = 2

# Seuils de catégorisation des débats
SEUIL_DEBAT_LONG_CANDIDATS = 4  # 4 candidats ou plus = débat long
SEUIL_DEBAT_LONG_TOURS = 4      # 4 tours ou plus = débat long

ActionType = Literal["chat", "debat_court", "debat_long"]

# ============================================================================
# État interne
# ============================================================================
# Structure : {ip: {"chat": int, "debat_court": int, "debat_long": int}}
_compteurs: dict[str, dict[str, int]] = {}
_lock = Lock()


def _get_compteur_vide() -> dict[str, int]:
    return {"chat": 0, "debat_court": 0, "debat_long": 0}


def verifier_et_incrementer(ip: str, action: ActionType) -> tuple[bool, int, int]:
    """
    Vérifie si l'IP peut effectuer l'action et incrémente le compteur si oui.
    
    Returns:
        (autorise, usage_actuel, limite) — si autorise=False, la requête doit être bloquée
    """
    limites = {
        "chat": LIMITE_CHAT_PAR_JOUR,
        "debat_court": LIMITE_DEBAT_COURT_PAR_JOUR,
        "debat_long": LIMITE_DEBAT_LONG_PAR_JOUR,
    }
    limite = limites[action]
    
    with _lock:
        if ip not in _compteurs:
            _compteurs[ip] = _get_compteur_vide()
        
        usage_actuel = _compteurs[ip].get(action, 0)
        
        if usage_actuel >= limite:
            return (False, usage_actuel, limite)
        
        _compteurs[ip][action] = usage_actuel + 1
        return (True, usage_actuel + 1, limite)


def categoriser_debat(nb_candidats: int, nb_tours_prevus: int) -> ActionType:
    """
    Détermine si un débat est 'long' ou 'court' selon sa configuration.
    
    Un débat est considéré long si :
    - Il a 4+ candidats, OU
    - Il est prévu pour 4+ tours
    
    Sinon c'est un débat court.
    """
    if nb_candidats >= SEUIL_DEBAT_LONG_CANDIDATS or nb_tours_prevus >= SEUIL_DEBAT_LONG_TOURS:
        return "debat_long"
    return "debat_court"


def reset_compteurs() -> int:
    """
    Vide tous les compteurs. Appelée automatiquement à minuit.
    Retourne le nombre d'IPs qui étaient actives dans la journée (pour log).
    """
    with _lock:
        nb_ips = len(_compteurs)
        _compteurs.clear()
        return nb_ips


def get_stats_actuelles() -> dict:
    """
    Retourne des statistiques agrégées pour monitoring/debug.
    Ne divulgue aucune IP individuelle.
    """
    with _lock:
        return {
            "nb_ips_actives_aujourdhui": len(_compteurs),
            "total_chats": sum(c.get("chat", 0) for c in _compteurs.values()),
            "total_debats_courts": sum(c.get("debat_court", 0) for c in _compteurs.values()),
            "total_debats_longs": sum(c.get("debat_long", 0) for c in _compteurs.values()),
        }


# ============================================================================
# Tâche asynchrone de reset à minuit
# ============================================================================
async def _tache_reset_minuit():
    """Tâche d'arrière-plan qui reset les compteurs chaque nuit à 00:00."""
    while True:
        maintenant = datetime.now()
        prochain_minuit = datetime.combine(
            maintenant.date() + timedelta(days=1),
            dtime(0, 0, 0)
        )
        secondes_a_attendre = (prochain_minuit - maintenant).total_seconds()
        
        await asyncio.sleep(secondes_a_attendre)
        
        nb_ips = reset_compteurs()
        print(f"[RATE_LIMITER] Reset quotidien à {datetime.now().isoformat()} — "
              f"{nb_ips} IPs nettoyées", flush=True)


def demarrer_tache_reset():
    """
    À appeler depuis le startup event de FastAPI pour lancer la tâche de reset.
    """
    asyncio.create_task(_tache_reset_minuit())
    print("[RATE_LIMITER] Tâche de reset quotidien démarrée", flush=True)
