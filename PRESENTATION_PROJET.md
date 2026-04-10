# DemandezLeur.fr : L'Intelligence Artificielle au Service du Citoyen

## L'Idée et l'Intention

À l'approche de l'élection présidentielle française de 2027, le volume d'informations, de promesses et de discours politiques peut rapidement devenir écrasant. **DemandezLeur.fr** est né d'une volonté simple : remettre le citoyen au centre du jeu politique en lui offrant un outil interactif, neutre et puissant pour décrypter les programmes électoraux.

L'objectif n'est pas de remplacer le débat démocratique, mais de l'éclairer. En utilisant l'intelligence artificielle, le site permet à chacun d'interroger directement les propositions des candidats, de confronter leurs visions et de dépasser les petites phrases pour se concentrer sur le fond. C'est un projet citoyen, développé bénévolement, pensé pour rendre la politique plus accessible et transparente.

## Les Fonctionnalités Principales

Le site propose deux expériences immersives pour explorer les programmes :

### 1. L'Entretien Individuel (Le Chat)
Vous vous posez une question précise sur l'écologie, le pouvoir d'achat ou la sécurité ? Sélectionnez un candidat et posez-lui directement votre question. L'IA analyse instantanément son programme officiel et vous formule une réponse claire, sourcée et rédigée dans le ton caractéristique de sa famille politique.

### 2. Le Mode Débat
C'est la fonctionnalité phare du site. Vous devenez le modérateur d'un plateau télévisé virtuel. 
- Choisissez **jusqu'à 5 candidats**.
- Définissez un **sujet libre** (ex: "Le SMIC à 1600 euros", "La sortie du nucléaire").
- L'IA génère un débat dynamique en plusieurs tours : chaque candidat expose sa vision (ouverture), réagit aux propos des autres (tour suivant), ou répond à vos relances spécifiques (intervention). Les échanges sont incisifs, argumentés et fidèles aux convictions de chacun.

## Transparence et Éthique : Nos Engagements

Dans un domaine aussi sensible que la politique, la confiance est primordiale. DemandezLeur.fr repose sur des principes stricts :

*   **Zéro Tracking & Anonymat :** Aucun cookie de suivi, aucune collecte de données personnelles, aucune adresse e-mail requise. Votre navigation et vos questions restent strictement privées.
*   **Fidélité aux Programmes (Anti-Hallucination) :** L'IA ne devine pas et n'invente pas. Si un programme ne traite pas d'un sujet, l'IA le dira honnêtement ou ramènera le débat sur un thème connexe validé par les textes officiels.
*   **Sources Publiques :** Les réponses sont générées *exclusivement* à partir des manifestes, livres et programmes déclarés des candidats. Les sources exactes sont citées pour chaque réponse.
*   **Indépendance Totale :** Le projet n'a aucune affiliation avec un parti, un candidat ou une institution. Il est financé par les citoyens, pour les citoyens, via des dons libres (Liberapay).
*   **Open Source :** Le code source du projet est ouvert, permettant à quiconque de vérifier le fonctionnement des algorithmes et la neutralité du système.

## Sous le Capot : Les Technologies Employées

Pour offrir une expérience fluide tout en maîtrisant les coûts, l'infrastructure s'appuie sur une pile technologique moderne et robuste :

*   **L'Intelligence Artificielle (LLM) :** Le cœur du système utilise **DeepSeek V3.2 (`deepseek-chat`)**, un modèle linguistique de pointe réputé pour ses capacités de raisonnement et sa rapidité. Il génère le texte en temps réel (streaming SSE), donnant l'impression que le candidat vous répond en direct.
*   **RAG (Retrieval-Augmented Generation) :** Pour garantir la véracité des propos, nous utilisons un système de RAG basé sur `scikit-learn` (TF-IDF). Lorsqu'une question est posée, le système recherche d'abord les extraits pertinents dans le programme du candidat avant de demander au modèle IA de formuler la réponse.
*   **Le Backend :** Une API robuste développée en **Python avec FastAPI**, hébergée sur un VPS OVH. Elle gère la logique des débats, la protection contre les abus (Rate Limiting) et les connexions à l'IA.
*   **Le Frontend :** L'interface utilisateur est générée avec **Hugo**, un générateur de site statique extrêmement rapide, offrant un design "mobile-first", sobre et accessible.

## Rejoignez l'Expérience

**DemandezLeur.fr** est plus qu'un simple outil technologique ; c'est une invitation à s'approprier le débat public. Que vous soyez un électeur indécis cherchant à comparer des mesures concrètes, ou un citoyen curieux de voir comment l'IA peut simuler des affrontements idéologiques, ce site est fait pour vous. 

Interrogez, comparez, débattez. L'élection de 2027 se prépare aujourd'hui.
