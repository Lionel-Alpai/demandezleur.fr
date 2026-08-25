import os
import json
import logging
from dotenv import load_dotenv

# Charger les variables d'environnement depuis .env
load_dotenv()

# Chemins relatifs au fichier (lancement possible depuis n'importe quel cwd)
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent


from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from openai import AsyncOpenAI
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from rate_limiter import (
    verifier_et_incrementer,
    categoriser_debat,
    demarrer_tache_reset,
    get_stats_actuelles,
)
from feedback import traiter_feedback
import parlement  # [parlement] couche actualité parlementaire

# --- Configuration Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Clés API ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")

# --- App FastAPI ---
app = FastAPI(title="DemandezLeur API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Accepte les requêtes de tous les domaines (local ou remote)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def au_demarrage():
    demarrer_tache_reset()
    asyncio.create_task(_precalculer_themes())


async def _precalculer_themes():
    """Thèmes lisibles des sujets parlementaires (cache sidecar), en tâche de fond."""
    try:
        import themes_parlement
        bruts = parlement.sujets(n=64).get("sujets", [])
        await themes_parlement.precalculer(bruts, {themes_parlement.cle_sujet(s): s.get("extraits", []) for s in bruts})
    except Exception:
        logger.warning("précalcul des thèmes parlementaires en échec", exc_info=True)

def extraire_ip_reelle(request: Request) -> str:
    """
    Extrait l'IP réelle du visiteur en tenant compte du reverse proxy Nginx.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    
    return request.client.host if request.client else "unknown"


def is_admin_bypass(request: Request) -> bool:
    """
    Vérifie si la requête a le token admin pour bypasser le rate limiting.
    Token lu depuis ADMIN_BYPASS_TOKEN (env, injecté par systemd) — JAMAIS de littéral.
    """
    jeton = os.environ.get("ADMIN_BYPASS_TOKEN")
    if not jeton:
        return False
    return request.headers.get("X-Admin-Token") == jeton
# Accès au modèle : voir llm.py (DL_MODE = live | demo | record)
import llm
import preuves


class Message(BaseModel):
    role: str
    content: str

class AskRequest(BaseModel):
    candidat_id: str
    question: str
    history: List[Message] = []

def load_corpus(candidat_id: str):
    # Charge le corpus JSON du candidat, puis ajoute l'actu parlementaire.
    path = str(BASE_DIR / "corpus" / f"{candidat_id}.json")
    corpus = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            corpus = json.load(f)
    # [parlement] greffe actu load_corpus
    try:
        corpus.extend(parlement.blocs_actu(candidat_id))
    except Exception:
        logging.getLogger(__name__).warning(
            "parlement.blocs_actu en echec pour %s", candidat_id, exc_info=True
        )
    return corpus

def search_corpus_from_list(corpus: list, query: str, top_k: int = 3, threshold: float = 0.02, window: int = None):
    """Recherche TF-IDF pour trouver les blocs les plus pertinents."""
    if not corpus:
        return ""
    blocs = preuves.rechercher_blocs(corpus, query, top_k=top_k, threshold=threshold)
    return preuves.formater_contexte(blocs, window=window)

def search_corpus(candidat_id: str, query: str, top_k: int = 3, window: int = None):
    """Interface simplifiée pour la recherche RAG."""
    corpus = load_corpus(candidat_id)
    return search_corpus_from_list(corpus, query, top_k=top_k, window=window)

def load_prompts(candidat_id: str):
    """Charge le prompt de base et le ton politique du candidat (source : candidats.json)."""
    from debat import charger_candidat, TON_PAR_FAMILLE
    try:
        c = charger_candidat(candidat_id)
    except (ValueError, FileNotFoundError):
        return None, None, None
    meta = {"nom": c["nom"], "parti": c.get("parti", ""), "famille": c.get("famille", ""),
            "ton_file": TON_PAR_FAMILLE.get(c.get("famille"), "ton_" + str(c.get("famille"))) + ".txt"}
    
    base_prompt = ""
    if os.path.exists(BASE_DIR / "prompts" / "base.txt"):
        with open(BASE_DIR / "prompts" / "base.txt", "r", encoding="utf-8") as f:
            base_prompt = f.read()
    
    ton_content = ""
    ton_path = str(BASE_DIR / "prompts" / meta['ton_file'])
    if os.path.exists(ton_path):
        with open(ton_path, "r", encoding="utf-8") as f:
            ton_content = f.read()
            
    return base_prompt, ton_content, meta

from fastapi import Request
from debat import (
    valider_requete_debat,
    randomiser_ordre,
    construire_prompt_debat,
    charger_candidat,
    MAX_TOKENS_DEBAT,
    TEMPERATURE_DEBAT,
    MAX_TOKENS_ARENE,  # [parlement]
    TEMPERATURE_ARENE,  # [parlement]
)
import asyncio
import random

def format_sse(event_type: str, data: dict) -> str:
    """Formate un événement SSE avec type et données JSON."""
    payload = json.dumps({"type": event_type, **data}, ensure_ascii=False)
    return f"data: {payload}\n\n"

@app.post("/api/debat/stream")
async def debat_stream(request: Request):
    """Stream SSE pour un tour de débat complet."""
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        return StreamingResponse(iter([format_sse("error", {"error": "Invalid JSON payload"})]), media_type="text/event-stream")
    
    # Validation
    valide, erreur = valider_requete_debat(payload)
    if not valide:
        return StreamingResponse(iter([format_sse("error", {"error": erreur})]), media_type="text/event-stream")
    
    # === NOUVEAU : Rate limit ===
    ip = extraire_ip_reelle(request)
    nb_candidats = len(payload["candidats"])
    
    # On estime le nombre de tours prévus à partir du tour actuel
    # Un débat qui est au tour 4+ est nécessairement un débat long
    tour_actuel = payload.get("tour", 1)
    nb_tours_prevus = max(tour_actuel, 3)  # minimum 3 pour la catégorisation initiale
    
    type_debat = categoriser_debat(nb_candidats, nb_tours_prevus)
    
    # On n'incrémente qu'au tour 1 (ouverture), pour ne compter qu'un débat
    # même si l'utilisateur enchaîne plusieurs tours
    if tour_actuel == 1:
        # Vérifier si admin bypass
        if not is_admin_bypass(request):
            autorise, usage, limite = verifier_et_incrementer(ip, type_debat)
            if not autorise:
                # Pour SSE, on renvoie l'erreur via le format SSE ou via une HTTPException
                # FastAPI gère bien l'HTTPException même sur un retour attendu de type StreamingResponse
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "rate_limit_exceeded",
                        "action": type_debat,
                        "usage": usage,
                        "limite": limite,
                        "message": "Vous avez atteint votre quota quotidien de débats. "
                                   "Revenez demain, le compteur se réinitialise à minuit."
                    }
                )
        else:
            # Admin bypass activé, on skip le rate limiting
            autorise, usage, limite = True, 0, 0
    # Charger les métadonnées des candidats
    try:
        candidats = [charger_candidat(cid) for cid in payload["candidats"]]
        candidats_by_id = {c["id"]: c for c in candidats}
    except Exception as e:
        return StreamingResponse(iter([format_sse("error", {"error": str(e)})]), media_type="text/event-stream")
    
    # Déterminer l'ordre de parole
    type_tour = payload.get("type_tour", "ouverture")
    mode_debat = payload.get("mode", "standard")  # [parlement]
    if type_tour == "intervention":
        interpelle_id = payload["candidat_interpelle_id"]
        autres_ids = [cid for cid in payload["candidats"] if cid != interpelle_id]
        random.shuffle(autres_ids)
        ordre_ids = [interpelle_id] + autres_ids
    elif llm.MODE == "demo":
        ordre_ids = list(payload["candidats"])  # démo : ordre reçu, rejeu reproductible
    else:
        ordre_ids = randomiser_ordre(payload["candidats"])
    
    candidat_interpelle = candidats_by_id.get(payload.get("candidat_interpelle_id"))
    
    # NOUVEAU : cache RAG local à ce tour
    cache_rag = {}

    async def generate():
        """Générateur SSE : émet les événements au fil de la génération."""
        
        # Événement : début du tour
        yield format_sse("turn_start", {
            "tour": payload.get("tour", 1),
            "candidats_ordre": ordre_ids,
            "candidats_meta": [
                {"id": c["id"], "nom": c["nom"], "parti": c.get("parti_court", c["parti"]), "famille": c.get("famille", ""), "photo": c.get("photo", "")}
                for c in [candidats_by_id[cid] for cid in ordre_ids]
            ],
            "sujet": payload["sujet"],
            "type_tour": type_tour,
            "mode": mode_debat,
        })
        
        # Historique qui s'enrichit au fil des interventions de CE tour
        interventions_ce_tour = []
        historique_complet = payload.get("historique", [])
        
        total_in_tour = 0
        total_out_tour = 0

        for position, candidat_id in enumerate(ordre_ids):
            candidat = candidats_by_id[candidat_id]
            est_interpelle = (type_tour == "intervention" and candidat_id == payload.get("candidat_interpelle_id"))
            
            # Signal : ce candidat commence à parler
            yield format_sse("speaker_start", {
                "candidat_id": candidat_id,
                "position": position,
            })
            
            # Enrichir l'historique avec ce qui vient d'être dit dans ce tour
            historique_pour_ce_candidat = historique_complet + [{
                "tour": payload.get("tour", 1),
                "type": type_tour,
                "question_moderateur": payload.get("question_moderateur"),
                "candidat_interpelle_nom": candidat_interpelle["nom"] if candidat_interpelle else None,
                "interventions": interventions_ce_tour,
            }] if interventions_ce_tour else historique_complet
            
            # Construire le prompt système
            prompt_system, preuves_locuteur = construire_prompt_debat(
                candidat=candidat,
                tour=payload["tour"],
                type_tour=type_tour,
                sujet=payload["sujet"],
                historique=historique_pour_ce_candidat,
                question_moderateur=payload.get("question_moderateur"),
                candidat_interpelle=candidat_interpelle if not est_interpelle else None,
                est_interpelle=est_interpelle,
                position_dans_tour=position,
                cache_rag=cache_rag,
                mode=mode_debat,  # [parlement]
                adversaires=[candidats_by_id[cid] for cid in ordre_ids if cid != candidat_id],
            )
            # A.4 — les pièces sur lesquelles ce locuteur s'appuie, avant le premier mot
            yield format_sse("preuves", {"candidat_id": candidat_id, "preuves": preuves_locuteur})
            
            # Appeler Groq en streaming
            full_text = ""
            tokens_in = 0
            tokens_out = 0
            try:
                usage = {}
                def _usage_cb(p_tok, c_tok, _u=usage):
                    _u["in"], _u["out"] = p_tok, c_tok
                cle_demo = ("debat", candidat_id, llm.normaliser(payload.get("question_moderateur") or payload["sujet"]), type_tour, mode_debat)
                async for delta in llm.completer(
                    [
                        {"role": "system", "content": prompt_system},
                        {"role": "user", "content": "Prends la parole maintenant."},
                    ],
                    cle_demo=cle_demo,
                    max_tokens=(MAX_TOKENS_ARENE if mode_debat == "arene" else MAX_TOKENS_DEBAT),  # [parlement]
                    temperature=(TEMPERATURE_ARENE if mode_debat == "arene" else TEMPERATURE_DEBAT),  # [parlement]
                    usage_cb=_usage_cb,
                ):
                    full_text += delta
                    yield format_sse("token", {
                        "candidat_id": candidat_id,
                        "text": delta,
                    })
                tokens_in, tokens_out = usage.get("in", 0), usage.get("out", 0)
                
                yield format_sse("speaker_end", {
                    "candidat_id": candidat_id,
                    "full_text": full_text,
                    "finish_reason": "stop",
                })
                
                # Si tokens_in/out sont toujours à 0 (fallback estimation)
                if tokens_in == 0:
                    tokens_in = len(prompt_system) // 4
                    tokens_out = len(full_text) // 4
                
                # Log par intervention
                print(f"[DEBAT] tour={payload['tour']} candidat={candidat_id} "
                      f"est_tokens_in={tokens_in} est_tokens_out={tokens_out} total={tokens_in + tokens_out}", 
                      flush=True)
                
                total_in_tour += tokens_in
                total_out_tour += tokens_out

            except Exception as e:
                logger.error(f"Erreur débat candidat {candidat_id}: {e}")
                yield format_sse("error", {
                    "candidat_id": candidat_id,
                    "error": str(e),
                })
                full_text = "(Erreur technique, ce candidat n'a pas pu répondre.)"
            
            # Enregistrer l'intervention pour le candidat suivant
            interventions_ce_tour.append({
                "candidat_id": candidat_id,
                "candidat_nom": candidat["nom"],
                "texte": full_text,
                "preuves": preuves_locuteur,
            })
        
        # Événement : fin du tour
        yield format_sse("turn_end", {
            "tour": payload.get("tour", 1),
            "interventions_complete": interventions_ce_tour,
        })
        
        print(f"[DEBAT] === FIN TOUR {payload['tour']} === "
              f"tokens_in_total={total_in_tour} "
              f"tokens_out_total={total_out_tour} "
              f"grand_total={total_in_tour + total_out_tour}",
              flush=True)

        # --- Archivage du débat ---
        try:
            archive_path = str(BASE_DIR.parent / "historique_debats.json")
            archive_entry = {
                "timestamp": str(asyncio.get_event_loop().time()),
                "sujet": payload["sujet"],
                "tour": payload.get("tour", 1),
                "type_tour": type_tour,
                "interventions": interventions_ce_tour,
                "usage": {
                    "prompt_tokens": total_in_tour,
                    "completion_tokens": total_out_tour,
                    "total_tokens": total_in_tour + total_out_tour
                }
            }
            
            archives = []
            if os.path.exists(archive_path):
                with open(archive_path, "r", encoding="utf-8") as f:
                    archives = json.load(f)
            
            archives.append(archive_entry)
            
            with open(archive_path, "w", encoding="utf-8") as f:
                json.dump(archives, f, ensure_ascii=False, indent=2)
            logger.info(f"Tour de débat archivé dans {archive_path}")
        except Exception as e:
            logger.error(f"Erreur lors de l'archivage du débat : {e}")
            
        yield format_sse("done", {})

    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@app.get("/api/admin/rate_limit_stats")
async def rate_limit_stats():
    return get_stats_actuelles()

@app.post("/api/feedback")
async def soumettre_feedback(request: Request):
    """Endpoint pour recevoir un feedback utilisateur et le transmettre via Telegram."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Payload invalide")
    
    message = payload.get("message", "")
    ip = extraire_ip_reelle(request)
    
    resultat = await traiter_feedback(ip, message)
    
    if not resultat["success"]:
        status_code = 429 if resultat["error"] == "rate_limit" else 400
        raise HTTPException(
            status_code=status_code,
            detail={
                "error": resultat["error"],
                "message": resultat["message_utilisateur"],
            }
        )
    
    return {
        "success": True,
        "message": resultat["message_utilisateur"],
    }

@app.post("/api/suggerer-document")
async def suggerer_document(
    request: Request,
    candidat: str = Form(...),
    titre: str = Form(...),
    url: str = Form(""),
    notes: str = Form(""),
    fichier: Optional[UploadFile] = File(None),
):
    """Reçoit une suggestion de document RAG et la transmet via Telegram."""
    ip = extraire_ip_reelle(request)
    TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_FEEDBACK_CHAT_ID")

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise HTTPException(status_code=500, detail="Configuration Telegram manquante")

    # Validation basique
    if not candidat.strip() or not titre.strip():
        raise HTTPException(status_code=400, detail="Candidat et titre sont requis")
    if len(titre) > 200 or len(notes) > 1000:
        raise HTTPException(status_code=400, detail="Champs trop longs")

    from datetime import datetime
    horodatage = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Construction du texte de notification
    lignes = [
        f"📎 Suggestion de document — demandezleur.fr",
        f"🕐 {horodatage}",
        f"━━━━━━━━━━━━━━━",
        f"👤 Candidat : {candidat}",
        f"📄 Document : {titre}",
    ]
    if url:
        lignes.append(f"🔗 URL : {url}")
    if notes:
        lignes.append(f"📝 Notes : {notes}")
    lignes.append("━━━━━━━━━━━━━━━")
    texte = "\n".join(lignes)

    import httpx
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if fichier and fichier.filename:
                # Envoi avec pièce jointe
                contenu = await fichier.read()
                if len(contenu) > 20 * 1024 * 1024:
                    raise HTTPException(status_code=400, detail="Fichier trop volumineux (max 20 Mo)")
                resp = await client.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument",
                    data={"chat_id": TELEGRAM_CHAT_ID, "caption": texte[:1024]},
                    files={"document": (fichier.filename, contenu, fichier.content_type or "application/octet-stream")},
                )
            else:
                # Envoi texte seul
                resp = await client.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={"chat_id": TELEGRAM_CHAT_ID, "text": texte},
                )
            resp.raise_for_status()
    except httpx.HTTPError as e:
        logger.error(f"[SUGGESTION] Erreur Telegram : {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de l'envoi")

    return {"success": True, "message_utilisateur": "Suggestion transmise avec succès."}


@app.post("/api/ask")
async def ask_candidat(request: Request, ask_request: AskRequest):
    ip = extraire_ip_reelle(request)
    if is_admin_bypass(request):
        autorise, usage, limite = True, 0, 0
    else:
        autorise, usage, limite = verifier_et_incrementer(ip, "chat")
    
    if not autorise:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "action": "chat",
                "usage": usage,
                "limite": limite,
                "message": "Vous avez atteint votre quota quotidien de questions. "
                           "Revenez demain, le compteur se réinitialise à minuit."
            }
        )
    
    candidat_id = ask_request.candidat_id
    
    # 1. Vérification du candidat
    base_prompt, ton_content, meta = load_prompts(candidat_id)
    if not meta:
        # Fallback pour permettre de tester n'importe quel candidat même sans fichier ton_*.txt
        meta = {"nom": candidat_id.replace('-', ' ').title(), "parti": "Indépendant"}
        base_prompt = "Tu es un militant politique. Réponds sur la base des extraits." if not base_prompt else base_prompt
        ton_content = "Sois convaincant et poli."
        
    # 2. RAG structuré : blocs -> contexte pour le modèle + preuves pour le visiteur
    corpus = load_corpus(candidat_id)
    blocs = preuves.rechercher_blocs(corpus, ask_request.question, top_k=3, threshold=0.02)
    rag_context = preuves.formater_contexte(blocs)
    preuves_visiteur = preuves.vers_preuves(blocs, candidat_id)
        
    # 4. Assemblage du prompt système
    system_prompt = base_prompt.replace("{candidat}", meta["nom"]) \
                               .replace("{parti}", meta["parti"]) \
                               .replace("{ton_famille_politique}", ton_content) \
                               .replace("{rag_context}", rag_context)

    messages = [{"role": "system", "content": system_prompt}]
    
    # Ajout de l'historique (limité aux 6 derniers messages)
    for msg in ask_request.history[-6:]:
        messages.append({"role": msg.role, "content": msg.content})
        
    # Ajout de la question actuelle
    messages.append({"role": "user", "content": ask_request.question})

    # 5. Flux SSE typé : preuves -> token* -> done | error
    async def generate():
        try:
            yield format_sse("preuves", {"candidat_id": candidat_id, "preuves": preuves_visiteur})
            cle_demo = ("ask", candidat_id, llm.normaliser(ask_request.question))
            async for delta in llm.completer(messages, cle_demo=cle_demo, max_tokens=700, temperature=0.65):
                yield format_sse("token", {"candidat_id": candidat_id, "text": delta})
            yield format_sse("done", {"candidat_id": candidat_id})
        except Exception as e:
            logger.error(f"Erreur DeepSeek API: {e}")
            yield format_sse("error", {"candidat_id": candidat_id, "error": str(e)})

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/parlement/etat")  # [parlement]
async def parlement_etat():
    return parlement.etat()

@app.get("/api/parlement/sujets")  # [parlement]
async def parlement_sujets(n: int = 8, dedup: int = 1):
    """Sujets parlementaires avec thème lisible (cache sidecar) ; dédoublonnés par thème."""
    import themes_parlement
    n = max(1, min(int(n), 24))
    brut = parlement.sujets(n=64)
    enrichis = themes_parlement.enrichir(brut.get("sujets", []), dedup=(dedup != 0))[:n]
    for sj in enrichis:
        sj.pop("extraits", None)
    brut["sujets"] = enrichis
    return brut

@app.post("/api/parlement/ingest")  # [parlement]
async def parlement_ingest(request: Request):
    token = request.headers.get("X-Parlement-Token")
    if not parlement.verifier_token(token):
        raise HTTPException(status_code=401, detail="token invalide")
    if parlement.OFF.exists():
        raise HTTPException(status_code=503, detail="feed desactive")
    try:
        obj = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON invalide")
    ok, raison = parlement.valider_payload(obj)
    if not ok:
        raise HTTPException(status_code=422, detail=raison)
    asyncio.create_task(_precalculer_themes())
    return {"ok": True, **parlement.ecrire(obj)}

if __name__ == "__main__":
    import uvicorn
    # Le serveur écoute sur 0.0.0.0 pour être joignable depuis votre téléphone via l'IP locale (192.168.1.x)
    uvicorn.run("api:app", host="0.0.0.0", port=8001, reload=True)
