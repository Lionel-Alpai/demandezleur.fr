# llm.py — seul point d'accès au modèle (SDK Anthropic natif si DL_BASE_URL=anthropic.com, sinon SDK OpenAI : DeepSeek, Mistral).
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
from types import SimpleNamespace
from typing import AsyncIterator, Callable, Optional

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

MODE = os.environ.get("DL_MODE", "live").strip().lower()
if MODE not in ("live", "demo", "record"):
    MODE = "live"
MODELE = os.environ.get("DL_MODELE", "deepseek-v4-flash")
# Le chemin STREAMÉ (completer) est l'orateur ; le chemin non streamé
# (completer_texte) est le juge du garde-fou et les analyses. Les deux n'ont pas
# besoin du même modèle : mesuré le 28/08/2026, un juge économique attrape les
# mêmes affirmations qu'un gros. DL_MODELE_JUGE permet donc (a) de payer le gros
# modèle là où la qualité se voit, (b) de tenir le juge CONSTANT quand on compare
# deux orateurs — sans quoi on change l'instrument en même temps que la mesure.
MODELE_JUGE = os.environ.get("DL_MODELE_JUGE", "").strip() or MODELE

# Fournisseur du modèle. Tout endpoint compatible OpenAI convient — DeepSeek par
# défaut, Mistral (https://api.mistral.ai/v1) vérifié le 28/08/2026 : streaming
# et response_format json_object acceptés, usage remonté dans le flux.
#   DL_CLE_VAR = le NOM de la variable d'environnement qui porte la clé, jamais
#   la clé elle-même : on ne met pas de secret dans un .env que le paquet côtoie.
BASE_URL = os.environ.get("DL_BASE_URL", "https://api.deepseek.com").rstrip("/")
CLE_VAR = os.environ.get("DL_CLE_VAR", "DEEPSEEK_API_KEY")

# `thinking: disabled` n'existe que chez DeepSeek — sans lui, v4-flash raisonne
# jusqu'à épuiser max_tokens et rend un contenu vide, facturé plein pot (leçon du
# 27/08). Mistral, lui, REFUSE le champ (422 extra_forbidden). Le paramètre suit
# donc le fournisseur, il n'est jamais envoyé à l'aveugle.
EXTRA_FOURNISSEUR = {"thinking": {"type": "disabled"}} if "deepseek" in BASE_URL else {}

# Anthropic (endpoint compatible OpenAI, https://api.anthropic.com/v1) : sondes du 23/10/2026.
#   - `temperature` REFUSÉ par claude-sonnet-5-5 (400) -> retiré ;
#   - `thinking: disabled` refusé par Sonnet (400), accepté par Haiku ; Sonnet se coupe
#     avec `between_tools` (sans quoi la réflexion avale max_tokens : contenu vide facturé) ;
#   - response_format json_object REFUSÉ -> retiré, la consigne JSON passe dans le prompt
#     (les appelants extraient le JSON de façon tolérante).
ANTHROPIC = "anthropic.com" in BASE_URL
CONSIGNE_JSON = "\n\nRéponds UNIQUEMENT par un objet JSON valide, sans texte ni balises autour."


def _adapter_fournisseur(params: dict) -> dict:
    """Ajuste les paramètres d'appel au fournisseur ; identité hors Anthropic."""
    if not ANTHROPIC:
        return params
    params.pop("temperature", None)
    mode = "disabled" if "haiku" in str(params.get("model", "")) else "between_tools"
    params["extra_body"] = {**(params.get("extra_body") or {}), "thinking": {"type": mode}}
    rf = params.pop("response_format", None)
    if isinstance(rf, dict) and rf.get("type") == "json_object":
        msgs = [dict(m) for m in params["messages"]]
        msgs[-1]["content"] = str(msgs[-1]["content"]) + CONSIGNE_JSON
        params["messages"] = msgs
    return params

BASE_DIR = Path(__file__).resolve().parent
DEMO_DIR = BASE_DIR / "demo"
DELAI_DEMO = 0.015  # secondes entre deux deltas rejoués

_client = None


def client():
    global _client
    if _client is None:
        from openai import AsyncOpenAI
        _client = AsyncOpenAI(api_key=os.environ.get(CLE_VAR, ""), base_url=BASE_URL)
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


_client_natif = None


def client_natif():
    """Client du SDK Anthropic natif (cache du prefixe) ; base_url par defaut du SDK."""
    global _client_natif
    if _client_natif is None:
        from anthropic import AsyncAnthropic
        _client_natif = AsyncAnthropic(api_key=os.environ.get(CLE_VAR, ""))
    return _client_natif


def _params_natifs(params: dict) -> dict:
    """Traduit les parametres deja adaptes (_adapter_fournisseur) en appel Messages natif :
    le(s) message(s) system deviennent UN bloc `system` marque cache_control ephemeral
    (le prefixe stable de l'orateur est mis en cache) ; stream/stream_options disparaissent."""
    msgs = [dict(m) for m in params["messages"]]
    systeme = "\n\n".join(str(m["content"]) for m in msgs if m.get("role") == "system")
    p = {"model": params["model"], "max_tokens": params["max_tokens"],
         "messages": [m for m in msgs if m.get("role") != "system"]}
    if systeme:
        p["system"] = [{"type": "text", "text": systeme, "cache_control": {"type": "ephemeral"}}]
    if params.get("extra_body"):
        p["extra_body"] = params["extra_body"]
    return p


def _usage_natif(u):
    """Usage natif -> forme lue par _compter (hit = lu du cache, miss = non cache)."""
    lu = int(getattr(u, "cache_read_input_tokens", 0) or 0)
    cree = int(getattr(u, "cache_creation_input_tokens", 0) or 0)
    ent = int(getattr(u, "input_tokens", 0) or 0)
    return SimpleNamespace(prompt_tokens=ent + lu + cree, completion_tokens=int(getattr(u, "output_tokens", 0) or 0),
                           prompt_cache_hit_tokens=lu, prompt_cache_miss_tokens=ent,
                           cache_creation_input_tokens=cree)


def _compter(u, usage_nom: str):
    """Enregistre l'appel au budget (cache hit/miss/creation/sortie) ; jamais bloquant."""
    try:
        import budget, rate_limiter
        hit = int(getattr(u, "prompt_cache_hit_tokens", 0) or 0)
        cree = int(getattr(u, "cache_creation_input_tokens", 0) or 0)
        p_tok = int(getattr(u, "prompt_tokens", 0) or 0)
        miss = getattr(u, "prompt_cache_miss_tokens", None)
        miss = max(0, p_tok - hit - cree) if miss is None else int(miss)
        out = int(getattr(u, "completion_tokens", 0) or 0)
        budget.enregistrer(hit, miss, out, usage_nom, pointe=rate_limiter.en_pointe(), creation=cree)
        logger.info("[COUT] %s hit=%d miss=%d creation=%d out=%d", usage_nom, hit, miss, cree, out)
    except Exception:
        logger.debug("budget non enregistre", exc_info=True)


_FRONTIERE = re.compile(r"[.!?…»][\"»”)’]*\s")
_FIN_PHRASE = re.compile(r"[.!?…»][\"»”)’]*\s*$")


def _derniere_frontiere(tampon: str) -> int:
    """Index de fin de la derniere phrase COMPLETE (ponctuation finale + espace) ; 0 si aucune."""
    fin = 0
    for m in _FRONTIERE.finditer(tampon):
        fin = m.end()
    return fin


def _reste_a_emettre(reste: str, emis: bool, raison) -> str:
    """Fin de flux : que faire du tampon non terminé. Coupe par max_tokens (length) -> on le JETTE,
    sauf s'il se termine par une ponctuation finale ou si rien n'a jamais été émis (jamais de réponse vide)."""
    if raison != "length" or not emis or _FIN_PHRASE.search(reste):
        return reste
    return ""


async def _flux(params: dict, fin: Optional[dict] = None):
    """Flux unifie (delta, usage) : SDK natif si Anthropic, SDK OpenAI sinon (DeepSeek, Mistral).
    `fin`, si fourni, reçoit {"raison": "length"|...} : la raison d'arrêt du dernier chunk."""
    if ANTHROPIC:
        async with client_natif().messages.stream(**_params_natifs(params)) as flux:
            async for d in flux.text_stream:
                yield d, None
            final = await flux.get_final_message()
        if fin is not None:
            sr = str(getattr(final, "stop_reason", "") or "")
            fin["raison"] = "length" if sr == "max_tokens" else sr
        yield "", _usage_natif(final.usage)
        return
    stream = await client().chat.completions.create(**params)
    async for chunk in stream:
        if getattr(chunk, "usage", None) is not None:
            yield "", chunk.usage
        if fin is not None and chunk.choices and getattr(chunk.choices[0], "finish_reason", None):
            fin["raison"] = chunk.choices[0].finish_reason
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content, None


async def _appel(params: dict):
    """Appel non streame unifie -> (texte, usage)."""
    if ANTHROPIC:
        rep = await client_natif().messages.create(**_params_natifs(params))
        texte = "".join(b.text for b in rep.content if getattr(b, "type", "") == "text")
        return texte, _usage_natif(rep.usage)
    rep = await client().chat.completions.create(**params)
    texte = (rep.choices[0].message.content or "") if rep.choices else ""
    return texte, getattr(rep, "usage", None)


async def completer(messages: list, *, cle_demo, max_tokens: int, temperature: float,
                    usage_cb: Optional[Callable[[int, int], None]] = None,
                    extra: Optional[dict] = None, par_phrase: bool = False) -> AsyncIterator[str]:
    """Génère la réponse en streaming (yield des morceaux de texte).
    par_phrase=True : ne yield que des phrases complètes ; un tampon non terminé est jeté si le modèle
    a été coupé par max_tokens (finish_reason length), vidé sinon."""
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
                  extra_body=EXTRA_FOURNISSEUR)
    if extra:
        params.update(extra)
    params = _adapter_fournisseur(params)
    deltas, p_tok, c_tok = [], 0, 0
    fin, tampon, emis = {}, "", False
    async for d, u in _flux(params, fin):
        if u is not None:
            p_tok, c_tok = u.prompt_tokens, u.completion_tokens
            _compter(u, str(cle_demo[0]) if cle_demo else "autre")
        if d and not par_phrase:
            deltas.append(d)
            yield d
        elif d:
            tampon += d
            cran = _derniere_frontiere(tampon)
            if cran:
                sortie, tampon, emis = tampon[:cran], tampon[cran:], True
                deltas.append(sortie)
                yield sortie
    if par_phrase and tampon:
        garde = _reste_a_emettre(tampon, emis, fin.get("raison"))
        if garde:
            deltas.append(garde)
            yield garde
        else:
            logger.warning("[COUPURE] replique coupee par max_tokens (length) : %d car. jetes, out=%d tokens, cle=%s, fin=%r",
                           len(tampon), c_tok, str(cle_demo)[:120], tampon[-60:])
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
    params = dict(model=MODELE_JUGE, messages=messages, max_tokens=max_tokens, temperature=temperature,
                  extra_body=EXTRA_FOURNISSEUR)
    if extra:
        params.update(extra)
    params = _adapter_fournisseur(params)
    texte, usage = await _appel(params)
    if usage is not None:
        _compter(usage, str(cle_demo[0]) if cle_demo else "autre")
    if MODE == "record":
        DEMO_DIR.mkdir(exist_ok=True)
        _chemin_fixture(cle_demo).write_text(json.dumps({"cle": list(cle_demo), "texte": texte, "deltas": _decouper(texte),
            "usage": {"prompt_tokens": getattr(usage, "prompt_tokens", 0), "completion_tokens": getattr(usage, "completion_tokens", 0)},
            "modele": MODELE_JUGE}, ensure_ascii=False, indent=1), encoding="utf-8")
    return texte
