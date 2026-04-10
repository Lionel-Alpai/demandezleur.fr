# demandezleur.fr

**Interrogez les programmes politiques des candidats à la présidentielle 2027.**

Site citoyen indépendant. L'IA répond uniquement à partir des programmes officiels des candidats — chaque réponse est sourcée, aucun tracking, code ouvert.

→ [demandezleur.fr](https://demandezleur.fr)

---

## Ce que fait ce projet

- **Chat par candidat** : posez vos questions au programme d'un candidat, l'IA répond en citant ses sources (RAG).
- **Mode débat** : sélectionnez jusqu'à 5 candidats, lancez un sujet, orchestrez les tours de parole. L'IA fait s'affronter leurs programmes en temps réel.
- **Transparence totale** : prompts visibles, corpus documentés, rate limiting public.

## Stack technique

| Composant | Technologie |
|---|---|
| Frontend | Hugo (site statique) |
| Backend | Python / FastAPI |
| IA | DeepSeek via API |
| Hébergement | VPS OVH + Hestia |
| Recherche RAG | TF-IDF sur corpus JSON |

## Structure du projet

```
├── hugo-src/          # Site statique Hugo
│   ├── themes/        # Thème demandezleur
│   ├── content/       # Pages candidats
│   └── data/          # candidats.json
├── backend/           # API Python
│   ├── api.py         # Endpoints chat & débat
│   ├── debat.py       # Logique débat multi-candidats
│   ├── rate_limiter.py
│   ├── feedback.py
│   └── prompts/       # Prompts système par famille politique
```

## Déploiement local

```bash
# Frontend
cd hugo-src && hugo server --port 1313

# Backend (nécessite une clé API DeepSeek dans .env)
cd backend && python api.py
```

## Transparence des sources RAG

Chaque candidat dispose d'un corpus documentaire consultable sur sa page. L'IA ne sort jamais de ce cadre.

---

*Projet indépendant — aucune affiliation avec les partis politiques, les candidats ou les institutions.*
