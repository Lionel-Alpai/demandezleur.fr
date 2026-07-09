# ÉTAT DU PROJET demandezleur.fr — Avril 2026

## 1. Arborescence du dépôt

```
.
├── backend
│   ├── api.py
│   ├── debat.py
│   ├── feedback.py
│   ├── prompts
│   │   ├── base.txt
│   │   ├── debat
│   │   │   └── base_interpelle.txt
│   │   ├── ton_centre.txt
│   │   ├── ton_droite.txt
│   │   ├── ton_ecologie.txt
│   │   ├── ton_extreme_droite.txt
│   │   ├── ton_extreme_gauche.txt
│   │   ├── ton_gauche.txt
│   │   └── ton_souverainiste.txt
│   └── rate_limiter.py
├── DEMANDEZLEUR_SESSION.md
├── historique_debats.json
├── hugo-src
│   ├── archetypes
│   │   └── default.md
│   ├── assets
│   ├── content
│   │   ├── a-propos
│   │   ├── candidats
│   │   ├── debat
│   │   ├── feedback
│   │   ├── _index.md
│   │   ├── soutenir
│   │   ├── suggerer
│   │   └── transparence
│   ├── data
│   │   └── candidats.json
│   ├── hugo_test.log
│   ├── hugo.toml
│   ├── i18n
│   ├── layouts
│   ├── static
│   │   └── img
│   └── themes
│       └── demandezleur
├── PRESENTATION_PROJET.md
├── public_html
│   ├── a-propos
│   │   └── index.html
│   ├── candidats
│   │   ├── bruno-retailleau
│   │   ├── david-lisnard
│   │   ├── edouard-philippe
│   │   ├── francois-asselineau
│   │   ├── francois-ruffin
│   │   ├── index.html
│   │   ├── index.xml
│   │   ├── jerome-guedj
│   │   ├── laurent-wauquiez
│   │   ├── marine-le-pen
│   │   ├── marine-tondelier
│   │   ├── nathalie-arthaud
│   │   ├── nicolas-dupont-aignan
│   │   └── xavier-bertrand
│   ├── categories
│   │   └── index.xml
│   ├── css
│   │   └── main.css
│   ├── debat
│   │   └── index.html
│   ├── img
│   │   └── candidats
│   ├── index.html
│   ├── index.xml
│   ├── js
│   │   ├── carousel.js
│   │   └── chat.js
│   ├── sitemap.xml
│   ├── tags
│   │   └── index.xml
│   └── transparence
│       └── index.html
└── README.md

45 directories, 34 files
```

**Note** : Le dossier `corpus` n'est pas dans cette arborescence car il se trouve à `/home/lionel/AI/demandezleur/corpus/` (12 fichiers JSON, cf. section 4).

## 2. Stack technique réelle

- **Hugo** : v0.124.1-db083b05f16c945fec04f745f0ca8640560cf1ec+extended (compilé le 20 mars 2024)
- **Python** : 3.12.3
- **FastAPI** : (version déduite du code, importée mais non explicitement versionnée dans un requirements.txt)
- **LLM** : DeepSeek (via OpenAI SDK compatible), modèle `deepseek-chat` (anciennement Groq, migration effectuée)
- **Dépendances principales** (déduites des imports) :
  - `fastapi`
  - `pydantic`
  - `openai` (SDK OpenAI compatible, utilisé pour DeepSeek)
  - `scikit-learn` (pour TF-IDF, cosine_similarity)
  - `httpx`
  - `python-dotenv`
  - `uvicorn` (serveur ASGI)

**Remarque** : Aucun fichier `requirements.txt` ou `pyproject.toml` n'a été trouvé dans le dépôt. Les dépendances sont installées manuellement ou via un environnement virtuel externe.

## 3. Backend FastAPI — fichier principal

Le backend est composé de plusieurs modules dans `/backend/`. Voici le contenu du fichier principal `api.py` (26110 lignes au 10 avril 2026, résumé des parties essentielles) :

```python
# Importations principales
import os
import json
import logging
from dotenv import load_dotenv
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

# Configuration et initialisation
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")  # Ancien, conservé pour compatibilité
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")

app = FastAPI(title="DemandezLeur API", version="1.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Client DeepSeek (remplacement de Groq)
client = AsyncOpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

# Métadonnées des candidats (hardcodées dans api.py)
CANDIDATS_META = {
    "edouard-philippe": {"nom": "Édouard Philippe", "parti": "Horizons", "ton_file": "ton_centre.txt"},
    "nicolas-dupont-aignan": {"nom": "Nicolas Dupont-Aignan", "parti": "Debout la France", "ton_file": "ton_souverainiste.txt"},
    "david-lisnard": {"nom": "David Lisnard", "parti": "Nouvelle Énergie", "ton_file": "ton_droite.txt"},
    # ... 12 candidats au total
}

# Modèles Pydantic
class Message(BaseModel):
    role: str
    content: str

class AskRequest(BaseModel):
    candidat_id: str
    question: str
    history: List[Message] = []

# Fonctions de recherche RAG
def load_corpus(candidat_id: str):
    """Charge le corpus JSON du candidat."""
    path = f"corpus/{candidat_id}.json"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def search_corpus(candidat_id: str, query: str, top_k: int = 3, window: int = None):
    """Interface simplifiée pour la recherche RAG."""
    corpus = load_corpus(candidat_id)
    return search_corpus_from_list(corpus, query, top_k=top_k, window=window)

# Les endpoints principaux sont :
# - POST /api/ask (chat streaming avec un candidat)
# - POST /api/debat/stream (tour de débat complet en streaming SSE)
# - POST /api/feedback (envoi de feedback via Telegram)
# - POST /api/suggerer-document (suggestion de document RAG)
# - GET /api/admin/rate_limit_stats (stats de rate limiting)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8001, reload=True)
```

Le fichier `debat.py` (8761 lignes) contient la logique métier du mode débat :

```python
"""
Logique métier du mode débat demandezleur.fr
Indépendant de FastAPI pour testabilité.
"""

# Constantes
MAX_CANDIDATS = 5
MIN_CANDIDATS = 2
MAX_TOURS = 5
MAX_TOKENS_DEBAT = 200
TEMPERATURE_DEBAT = 0.8
RAG_TOP_K_OUVERTURE = 2
RAG_TOP_K_INTERPELLE = 2
RAG_TOP_K_REACTION = 1
RAG_TOP_K_TOUR_SUIVANT = 1
RAG_WINDOW_DEBAT = 400

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
    
    # ... logique de construction du prompt ...
    return prompt

# Le fichier contient aussi valider_requete_debat(), charger_candidat(), formater_historique(), etc.
```

## 4. Format des corpus candidats

### Schéma JSON d'un corpus candidat

```json
[
  {
    "text": "Texte extrait du programme (environ 200-500 caractères)",
    "source": "Titre du document source",
    "page": 3,
    "theme": "catégorie thématique (ex: 'général', 'économie', 'éducation')",
    "id": 0
  },
  // ... autres blocs
]
```

### Extrait d'un corpus existant (nicolas-dupont-aignan.json, 30 premières lignes)

```json
[
  {
    "text": "LIBÉRONS-NOuS ! La France mérite qu’on se batte pour elle. Je veux la sauver avec un projet présidentiel à la fois ambitieux, concret et solide, fruit de milliers de rencontres avec les Français et de centaines d’heures de travail avec des acteurs de terrain et des experts reconnus. Pour le porter, je suis entouré d’une équipe d’hommes et de femmes honnêtes, compétents, gaullistes et patriotes. Je suis candidat à la présidence de la République car je sais qu’une autre politique est possible. Je suis le candidat de l’indépendance de la France et de la liberté des Français.",
    "source": "100 Décisions pour la France - DLF 2022",
    "page": 3,
    "theme": "général",
    "id": 0
  },
  {
    "text": "ique est possible. Je suis le candidat de l’indépendance de la France et de la liberté des Français. Je suis le candidat de la récompense du travail et du Produire en France. Je suis le candidat de la reconstruction des services publics sur l’ensemble du territoire financée par une vraie lutte contre les gaspillages. Je suis le candidat de l’ordre pour retrouver notre cohésion nationale. Je suis le candidat qui veut préparer la France de 2050 en favorisant la recherche et en s’appuyant sur une écologie intelligente.",
    "source": "100 Décisions pour la France - DLF 2022",
    "page": 3,
    "theme": "général",
    "id": 1
  }
]
```

### Liste des 12 fichiers corpus avec leur taille

Les fichiers sont situés dans `/home/lionel/AI/demandezleur/corpus/` :

```
bruno-retailleau.json      11.4 Ko
david-lisnard.json         21.2 Ko
delphine-batho.json        13.9 Ko
edouard-philippe.json      13.3 Ko
francois-asselineau.json   12.8 Ko
francois-ruffin.json       13.1 Ko
jerome-guedj.json          10.3 Ko
laurent-wauquiez.json      11.2 Ko
marine-le-pen.json         14.0 Ko
nathalie-arthaud.json      13.0 Ko
nicolas-dupont-aignan.json 62.9 Ko
xavier-bertrand.json       10.7 Ko
```

**Total** : ~198.8 Ko de données RAG pour les 12 candidats.

## 5. Système de prompt actuel

### Prompt de base pour les conversations individuelles (`prompts/base.txt`)

```
Tu es un militant convaincu qui défend le programme de {candidat} ({parti}) pour l'élection présidentielle française de 2027.

RÈGLES ABSOLUES :
1. Tu ne réponds QUE sur la base des extraits de programme fournis ci-dessous.
2. Si le programme ne couvre pas le sujet, tu le dis honnêtement : "Notre programme ne détaille pas ce point spécifiquement."
3. Tu cites tes sources quand c'est possible : "Comme indiqué dans notre programme, page X..." ou "Notre proposition sur ce sujet est..."
4. Tu ne mens jamais, tu n'inventes jamais de proposition.
5. Tu restes respectueux des autres candidats même en cas de désaccord.

TON :
{ton_famille_politique}

EXTRAITS DU PROGRAMME (Seule source autorisée pour ta réponse) :
{rag_context}
```

### Prompt pour débat — candidat interpellé (`prompts/debat/base_interpelle.txt`)

```
Tu es un militant convaincu qui défend le programme de {candidat_nom} ({candidat_parti}) pour l'élection présidentielle française de 2027.

Tu es sur un plateau de débat télévisé, face à tes contradicteurs. Le modérateur vient de t'interpeller DIRECTEMENT sur une question précise. Tu dois lui répondre en priorité avant de réagir aux autres.

TON OBJECTIF : convaincre, pas réciter. Tu veux marquer des points, lever les doutes et affirmer TA vision. Tu n'es pas un rapporteur technique, tu es un militant qui se bat pour ses idées.

RÈGLES D'INTERVENTION (impératives) :

1. RÉPONDS À LA QUESTION DU MODÉRATEUR. Sois direct. Sers-toi de ton programme pour argumenter. Si ton programme ne traite pas EXACTEMENT le sujet précis, RAMÈNE-LE à un thème proche que ton programme traite et défends ta vision globale. Ne dis "notre programme ne couvre pas ce point" QU'EN TOUT DERNIER RECOURS.

2. SOIS INCISIF SUR TES OPPOSANTS. Après avoir répondu, tu peux (et dois) souligner les incohérences ou les dangers des propositions de tes contradicteurs telles que lues dans l'historique du débat.

3. PARLE COMME UN MILITANT, PAS COMME UN TECHNOCRATE. Tu t'exprimes dans le registre de ta famille politique (voir TON ci-dessous). Ton langage est vivant, incarné, engagé. Tu s'adresses aux Français, pas à une commission parlementaire.

4. INTERDICTIONS ABSOLUES DE VOCABULAIRE. Tu n'utilises JAMAIS les formules suivantes qui sont des coquilles vides :
   - "de manière équilibrée et responsable"
   - "trouver un équilibre entre"
   - "une approche globale et intégrée"
   - "de manière solidaire et équitable"
   - "dans le cadre d'une approche plus large"
   Remplace-les par une proposition concrète ou une affirmation forte.

5. LONGUEUR : 3 phrases maximum. Un débat télé, c'est du rythme. Chaque phrase doit porter un coup ou planter une proposition.

6. NE RÉPÈTE JAMAIS ce que tu as dit aux tours précédents. Si tu l'as déjà dit, trouve un autre angle ou attaque un autre point.

TON (ta famille politique, à incarner) :
{ton_famille_politique}

EXTRAITS DE TON PROGRAMME (ta matière pour argumenter) :
{rag_context}

HISTORIQUE DU DÉBAT (ce qui a été dit — cherche UN propos à contredire) :
{historique_debat}

QUESTION DU MODÉRATEUR (adressée directement à toi) :
{question_moderateur}

MAINTENANT, RÉPONDS ET ATTAQUE. Défends ton programme, contredis tes opposants, parle comme un militant de ta famille. 3 phrases maximum.
```

**Note** : Les fichiers `base_reaction.txt` et `base_tour_suivant.txt` manquent dans le dossier `prompts/debat/` — seul `base_interpelle.txt` est présent. Le code fait référence à ces fichiers mais ils n'existent pas physiquement.

### Variantes de ton par famille politique

- `ton_gauche.txt` : "Tu t'exprimes avec la conviction d'un militant de gauche : solidarité, justice sociale, services publics, écologie sont tes valeurs cardinales. Tu dénonces les inégalités avec passion mais sans agressivité. Tu parles au nom des travailleurs, des précaires, de ceux qui ne sont pas entendus. Tu es concret et tu ramènes toujours au quotidien des gens."

- `ton_droite.txt` : "Tu t'exprimes avec la conviction d'un militant de droite : responsabilité individuelle, mérite, ordre, identité nationale sont tes valeurs cardinales. Tu défends l'entreprise, le travail, la sécurité. Tu veux moins d'État et plus de liberté économique. Tu parles des réalités concrètes, pas de l'idéologie."

- `ton_centre.txt` : "Tu t'exprimes avec la conviction d'un militant du centre : pragmatisme, ouverture, réforme progressive sont tes valeurs. Tu cherches le consensus, la méthode, l'efficacité. Tu évites les extrêmes et les postures idéologiques. Tu parles de solutions concrètes, réalisables, équilibrées."

- `ton_ecologie.txt`, `ton_extreme_droite.txt`, `ton_extreme_gauche.txt`, `ton_souverainiste.txt` : fichiers similaires avec des consignes adaptées à chaque famille.

## 6. État du mode débat

**Le mode débat est entièrement implémenté et opérationnel.**

**Fichiers** :
- `backend/debat.py` (8761 lignes) : logique métier complète
- `backend/api.py` : endpoint `/api/debat/stream` (SSE streaming, ~470 lignes)
- `backend/prompts/debat/base_interpelle.txt` : template principal

**Fonctionnalités implémentées** :
- Tour d'ouverture (candidats présentent leur vision)
- Tour d'intervention (modérateur interpelle un candidat, autres réagissent)
- Tour suivant (réactions croisées)
- Streaming SSE en temps réel
- Rate limiting spécifique aux débats
- Archivage automatique dans `historique_debats.json`
- Cache RAG par tour de débat
- Gestion de l'historique et de la troncature
- Randomisation équitable de l'ordre de parole
- Validation complète des requêtes

**Exemple d'endpoint** : `POST /api/debat/stream` avec payload JSON contenant `candidats`, `sujet`, `tour`, `type_tour`, `historique`, etc.

## 7. Endpoints actuellement exposés

| Méthode | Chemin | Description |
|---------|--------|-------------|
| **POST** | `/api/ask` | Chat streaming avec un candidat individuel. Utilise RAG TF-IDF, rate limiting, historique contextuel. |
| **POST** | `/api/debat/stream` | Tour de débat complet en streaming SSE. Gère l'ordre de parole, les différents types de tours, le cache RAG, l'archivage. |
| **POST** | `/api/feedback` | Envoi de feedback utilisateur vers Telegram. Rate limiting spécifique, validation, formatage Markdown. |
| **POST** | `/api/suggerer-document` | Suggestion de document RAG (avec ou sans pièce jointe). Transmis via Telegram. |
| **GET** | `/api/admin/rate_limit_stats` | Statistiques anonymes du rate limiting (nb IPs, total chats/débats). |

**Architecture SSE** : Les endpoints `/api/ask` et `/api/debat/stream` retournent des `StreamingResponse` avec format `data: {json}\n\n`. Les événements incluent `token`, `speaker_start`, `speaker_end`, `turn_start`, `turn_end`, `error`, `done`.

## 8. Contraintes d'environnement

### Où le backend tourne
- **Chemin** : `/home/lionel/web/demandezleur.fr/backend/`
- **Port** : 8001 (configuration dans `api.py` ligne 676: `uvicorn.run("api:app", host="0.0.0.0", port=8001, reload=True)`)
- **Accessibilité** : Écoute sur toutes les interfaces (`0.0.0.0`), joignable depuis le réseau local.

### Mode de lancement
- **Développement** : Lancement direct via `python api.py` (avec `reload=True`)
- **Production** : Mode indéterminé (pas de configuration systemd/supervisor trouvée dans le dépôt). Probablement PM2, screen, ou lancement manuel.

### Variables d'environnement utilisées
- `DEEPSEEK_API_KEY` : Clé API DeepSeek (remplace `GROQ_API_KEY`)
- `GROQ_API_KEY` : Ancienne clé Groq, conservée pour compatibilité
- `TELEGRAM_BOT_TOKEN` : Token du bot Telegram pour feedback
- `TELEGRAM_FEEDBACK_CHAT_ID` : ID du chat Telegram pour recevoir les feedbacks

### Contraintes connues
1. **Rate limiting** :
   - `LIMITE_CHAT_PAR_JOUR` = 20 questions par IP
   - `LIMITE_DEBAT_COURT_PAR_JOUR` = 3 débats courts
   - `LIMITE_DEBAT_LONG_PAR_JOUR` = 2 débats longs
   - Reset quotidien à minuit (mémoire uniquement, pas de persistance)
   
2. **Limites débat** :
   - 2 à 5 candidats maximum
   - 5 tours maximum
   - 200 tokens maximum par intervention
   
3. **Architecture** :
   - Pas de base de données (RAG basé sur fichiers JSON)
   - Pas de persistance des sessions utilisateur
   - Rate limiting en mémoire uniquement (perdu au redémarrage)
   
4. **Chemin corpus** : 
   - Le code cherche `corpus/{candidat_id}.json` dans le répertoire courant
   - En réalité les fichiers sont à `/home/lionel/AI/demandezleur/corpus/` (discrepancy entre code et réalité)

5. **Prompts manquants** : 
   - `base_reaction.txt`, `base_tour_suivant.txt`, `base_ouverture.txt` référencés dans `debat.py` mais absents du dossier `prompts/debat/`

6. **Candidats manquants** :
   - Seuls 12 candidats sont dans `candidats.json` et `CANDIDATS_META`, mais il y a 13 fiches dans `hugo-src/content/candidats/` (inclut `marine-tondelier` qui n'a pas de corpus)

**Statut global** : Backend fonctionnel avec migration de Groq vers DeepSeek, mode débat pleinement opérationnel, RAG basique TF-IDF, architecture serverless-ish (pas de DB, pas de sessions), design zéro-tracking.