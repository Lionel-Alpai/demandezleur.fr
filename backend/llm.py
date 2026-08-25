# llm.py — seul point d'accès au modèle (DeepSeek via SDK OpenAI).
"""
Trois modes, choisis par la variable d'environnement DL_MODE :
  live    (défaut) : appel réseau, streaming.
  record           : comme live, et enregistre la réponse dans demo/<hash>.json ;
                     si la fixture existe déjà, la rejoue (comble les trous sans dépenser).
  demo             : aucun réseau ; rejoue demo/<hash>.json (ou demo/generique.json).

Clé de fixture (cle_demo) : tuple sérialisable, ex. ("ask", candidat_id, question_normalisee).
"""
import asyncio
import hashlib
import json
import logging
import os
import re
import unicodedata
from pathlib import Path
from typing import AsyncIterator, Callable, Optional

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

MODE = os.environ.get("DL_MODE", "live").strip().lower()
if MODE not in ("live", "demo", "record"):
    MODE = "live"
MODELE = os.environ.get("DL_MODELE", "deepseek-v4-flash")
BASE_DIR = Path(__file__).resolve().parent
DEMO_DIR = BASE_DIR / "demo"
DELAI_DEMO = 0.015  # secondes entre deux deltas rejoués

_client = None


def client():
    global _client
    if _client is None:
        from openai import AsyncOpenAI
        _client = AsyncOpenAI(api_key=os.environ.get("DEEPSEEK_API_KEY", ""), base_url="https://api.deepseek.com")
    return _client


def normaliser(texte: str) -> str:
    """Minuscules, sans accents, sans ponctuation, espaces réduits — pour les clés de fixture."""
    t = unicodedata.normalize("NFKD", str(texte or "")).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-z0-9]+", " ", t.lower())
    return t.strip()


def _chemin_fixture(cle_demo) -> Path:
    brut = json.dumps(list(cle_demo), ensure_ascii=False)
    return DEMO_DIR / (hashlib.sha1(brut.encode("utf-8")).hexdigest()[:16] + ".json")


def _lire_fixture(cle_demo) -> Optional[dict]:
    for chemin in (_chemin_fixture(cle_demo), DEMO_DIR / "generique.json"):
        if chemin.exists():
            try:
                return json.loads(chemin.read_text(encoding="utf-8"))
            except Exception:
                logger.warning("fixture illisible : %s", chemin)
    return None


def _decouper(texte: str) -> list:
    """Découpe un texte en deltas plausibles (mots + espaces) pour le rejeu."""
    return re.findall(r"\S+\s*", texte)


async def completer(messages: list, *, cle_demo, max_tokens: int, temperature: float,
                    usage_cb: Optional[Callable[[int, int], None]] = None,
                    extra: Optional[dict] = None) -> AsyncIterator[str]:
    """Génère la réponse en streaming (yield des morceaux de texte)."""
    if MODE == "demo" or (MODE == "record" and _chemin_fixture(cle_demo).exists()):
        fx = _lire_fixture(cle_demo)
        deltas = (fx or {}).get("deltas") or _decouper((fx or {}).get("texte", "") or
                  "[Mode démo] Aucune réponse enregistrée pour cette question. Lancez le backend en DL_MODE=live pour une vraie réponse.")
        for d in deltas:
            yield d
            await asyncio.sleep(DELAI_DEMO)
        if usage_cb:
            u = (fx or {}).get("usage") or {}
            usage_cb(int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0)))
        return

    params = dict(model=MODELE, messages=messages, max_tokens=max_tokens, temperature=temperature,
                  stream=True, stream_options={"include_usage": True},
                  extra_body={"thinking": {"type": "disabled"}})
    if extra:
        params.update(extra)
    stream = await client().chat.completions.create(**params)
    deltas, p_tok, c_tok = [], 0, 0
    async for chunk in stream:
        if getattr(chunk, "usage", None) is not None:
            p_tok, c_tok = chunk.usage.prompt_tokens, chunk.usage.completion_tokens
        if chunk.choices and chunk.choices[0].delta.content:
            d = chunk.choices[0].delta.content
            deltas.append(d)
            yield d
    if usage_cb:
        usage_cb(p_tok, c_tok)
    if MODE == "record":
        DEMO_DIR.mkdir(exist_ok=True)
        _chemin_fixture(cle_demo).write_text(json.dumps({
            "cle": list(cle_demo), "texte": "".join(deltas), "deltas": deltas,
            "usage": {"prompt_tokens": p_tok, "completion_tokens": c_tok}, "modele": MODELE,
        }, ensure_ascii=False, indent=1), encoding="utf-8")


async def completer_texte(messages: list, *, cle_demo, max_tokens: int, temperature: float,
                          extra: Optional[dict] = None) -> str:
    """Version non streamée (juge, thèmes…). En démo : fixture ou chaîne vide."""
    if MODE == "demo" or (MODE == "record" and _chemin_fixture(cle_demo).exists()):
        fx = _lire_fixture(cle_demo)
        return (fx or {}).get("texte", "") if fx and _chemin_fixture(cle_demo).exists() else ""
    params = dict(model=MODELE, messages=messages, max_tokens=max_tokens, temperature=temperature,
                  extra_body={"thinking": {"type": "disabled"}})
    if extra:
        params.update(extra)
    rep = await client().chat.completions.create(**params)
    texte = (rep.choices[0].message.content or "") if rep.choices else ""
    if MODE == "record":
        DEMO_DIR.mkdir(exist_ok=True)
        _chemin_fixture(cle_demo).write_text(json.dumps({"cle": list(cle_demo), "texte": texte, "deltas": _decouper(texte),
            "usage": {"prompt_tokens": getattr(rep.usage, "prompt_tokens", 0), "completion_tokens": getattr(rep.usage, "completion_tokens", 0)},
            "modele": MODELE}, ensure_ascii=False, indent=1), encoding="utf-8")
    return texte
