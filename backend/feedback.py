"""
Module de gestion du feedback utilisateur pour demandezleur.fr
Envoie les feedbacks reçus via webhook Telegram, sans stockage persistant.

Philosophie : zéro donnée utilisateur stockée après transmission.
"""

import os
import asyncio
import httpx
from datetime import datetime

# Limites anti-spam pour le feedback
LIMITE_FEEDBACK_PAR_JOUR = 5
LONGUEUR_MIN_MESSAGE = 10
LONGUEUR_MAX_MESSAGE = 2000

# On récupère les secrets depuis l'environnement
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_FEEDBACK_CHAT_ID = os.environ.get("TELEGRAM_FEEDBACK_CHAT_ID")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage" if TELEGRAM_BOT_TOKEN else None


class FeedbackError(Exception):
    pass


def valider_message(message: str) -> tuple[bool, str]:
    """Valide le contenu d'un feedback. Retourne (valide, erreur)."""
    if not message or not message.strip():
        return (False, "Le message est vide.")
    
    message_trimmed = message.strip()
    
    if len(message_trimmed) < LONGUEUR_MIN_MESSAGE:
        return (False, f"Message trop court (minimum {LONGUEUR_MIN_MESSAGE} caractères).")
    
    if len(message_trimmed) > LONGUEUR_MAX_MESSAGE:
        return (False, f"Message trop long (maximum {LONGUEUR_MAX_MESSAGE} caractères).")
    
    return (True, "")


def verifier_rate_limit_feedback(ip: str) -> tuple[bool, int, int]:
    """
    Vérifie si l'IP peut envoyer un feedback aujourd'hui.
    Utilise le rate_limiter partagé avec une clé dédiée 'feedback'.
    """
    from rate_limiter import _compteurs, _lock
    
    with _lock:
        if ip not in _compteurs:
            _compteurs[ip] = {"chat": 0, "debat_court": 0, "debat_long": 0}
        
        # Ajouter le champ feedback si absent
        if "feedback" not in _compteurs[ip]:
            _compteurs[ip]["feedback"] = 0
        
        usage = _compteurs[ip]["feedback"]
        
        if usage >= LIMITE_FEEDBACK_PAR_JOUR:
            return (False, usage, LIMITE_FEEDBACK_PAR_JOUR)
        
        _compteurs[ip]["feedback"] += 1
        return (True, usage + 1, LIMITE_FEEDBACK_PAR_JOUR)


def escape_markdown_v2(text: str) -> str:
    """Échappe les caractères réservés pour le MarkdownV2 de Telegram."""
    reserved = r"\_*[]()~`>#+-=|{}.!"
    for char in reserved:
        text = text.replace(char, f"\\{char}")
    return text


def formater_message_telegram(message_brut: str) -> str:
    """
    Formate le message de feedback pour affichage dans Telegram.
    Le message utilise le mode Markdown de Telegram (V2).
    """
    horodatage = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # Échapper les parties variables
    ts_escaped = escape_markdown_v2(horodatage)
    msg_escaped = escape_markdown_v2(message_brut)
    
    return (
        f"📬 *Nouveau feedback demandezleur\\.fr*\n"
        f"🕐 {ts_escaped}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{msg_escaped}\n"
        f"━━━━━━━━━━━━━━━"
    )


async def envoyer_vers_telegram(message: str) -> bool:
    """
    Envoie un message formaté au bot Telegram configuré.
    Retourne True si envoyé avec succès, False sinon.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_FEEDBACK_CHAT_ID:
        print("[FEEDBACK] ERREUR : TELEGRAM_BOT_TOKEN ou TELEGRAM_FEEDBACK_CHAT_ID non configuré", flush=True)
        return False
    
    payload = {
        "chat_id": TELEGRAM_FEEDBACK_CHAT_ID,
        "text": message,
        "parse_mode": "MarkdownV2",
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(TELEGRAM_API_URL, json=payload)
            response.raise_for_status()
            return True
    except httpx.HTTPStatusError as e:
        print(f"[FEEDBACK] Erreur statut Telegram ({e.response.status_code}) : {e.response.text}", flush=True)
        return False
    except httpx.HTTPError as e:
        print(f"[FEEDBACK] Erreur réseau Telegram : {e}", flush=True)
        return False
    except Exception as e:
        print(f"[FEEDBACK] Erreur inattendue : {e}", flush=True)
        return False


async def traiter_feedback(ip: str, message: str) -> dict:
    """
    Point d'entrée principal pour traiter un feedback utilisateur.
    """
    # 1. Validation du contenu
    valide, erreur = valider_message(message)
    if not valide:
        return {
            "success": False,
            "error": "validation",
            "message_utilisateur": erreur,
        }
    
    # 2. Rate limit
    autorise, usage, limite = verifier_rate_limit_feedback(ip)
    if not autorise:
        return {
            "success": False,
            "error": "rate_limit",
            "message_utilisateur": f"Vous avez atteint le maximum de {limite} feedbacks par jour. "
                                    f"Merci pour vos retours, revenez demain si vous avez d'autres remarques.",
        }
    
    # 3. Envoi vers Telegram
    message_formate = formater_message_telegram(message.strip())
    envoi_ok = await envoyer_vers_telegram(message_formate)
    
    if not envoi_ok:
        return {
            "success": False,
            "error": "transmission",
            "message_utilisateur": "Une erreur technique s'est produite lors de l'envoi. "
                                    "Merci de réessayer dans un instant.",
        }
    
    return {
        "success": True,
        "error": None,
        "message_utilisateur": "Merci pour votre retour, il a bien été transmis.",
    }
