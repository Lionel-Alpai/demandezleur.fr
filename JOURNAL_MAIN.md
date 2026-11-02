20261029-0640 corpus jean-luc-melenchon remplacé à la main (80 blocs officiels melenchon2027.fr + laec.fr 2022) — feu vert Lionel 29/10 ; bak .bak-main-20261029-0640 prod+local
20261029-0643 corpus gabriel-attal remplacé à la main — 80 blocs verbatim attalpresident.fr + conventions Renaissance 2025 — bak .bak-main-20261029-0643 (prod+local)
20261029-0644 corpus eric-zemmour remplacé à la main — 79 blocs verbatim ericzemmour.fr (priorités + 18 discours 2022-2024) + budget2027.fr ; Attac et Public Sénat retirés — bak .bak-main-20261029-0644 (prod+local)
20261029-0644 candidats.json : eric-zemmour sans_source_officielle=False + sources officielles (prod backend + local backend/hugo-src) — bak .bak-main-20261029-0644
20261029-0647 corpus marine-le-pen remplacé à la main — 77 blocs verbatim manifeste 2022, 22 mesures, livrets, contre-budget 2026, lettres ouvertes 2024-2026, discours — bak .bak-main-20261029-0647 (prod+local)
20261029-0646 public_html redéployé à la main (hugo build local) : 6 portraits (Polony, Becht = portrait local u2net ; 4 cartes initiales) + Zemmour sans marquage — tar prod public_html.bak-main-20261029-0646.tgz
20261029-0737 corpus raphael-glucksmann remplacé à la main — 77 blocs verbatim Place publique Acte I + lettre aux Français 25/08/2026 + glucks2027.fr — vague 2 — bak .bak-main-20261029-0737 (prod+local)
20261029-0737 corpus fabien-roussel remplacé à la main — 76 blocs verbatim fabienroussel2027.fr + PCF programme Pour des jours heureux + cahiers thématiques — vague 2 — bak .bak-main-20261029-0737 (prod+local)
20261029-0737 corpus mira-markovic remplacé à la main — 62 blocs verbatim parti-animaliste.fr (programme 2022, communiqués 2026, page campagne) — vague 2 — bak .bak-main-20261029-0737 (prod+local)
20261029-0737 corpus natacha-polony remplacé à la main — 45 blocs verbatim natachapolony2027.fr + npolony.fr — vague 2 — bak .bak-main-20261029-0737 (prod+local)
20261029-0737 corpus francois-ruffin remplacé à la main — 80 blocs verbatim nouspresident.fr + debout.fr manifeste + francoisruffin.fr — vague 2 — bak .bak-main-20261029-0737 (prod+local)
20261029-0737 corpus marine-tondelier remplacé à la main — 71 blocs verbatim marinetondelier.fr (blog, journal, livrets et carnets PDF) — vague 2 — bak .bak-main-20261029-0737 (prod+local)
20261029-0737 corpus olivier-becht remplacé à la main — 46 blocs : 33 verbatim auditions Assemblée nationale 2022-2023 + bio/déclaration + 10 blocs de l'ancien corpus (thèmes manquants) ; reste sans programme officiel — vague 2 — bak .bak-main-20261029-0737 (prod+local)
20261029-0738 candidats.json : raphael-glucksmann sans_source_officielle=False + sources officielles (prod backend + local backend/hugo-src) — bak .bak-main-20261029-0738
20261029-0738 candidats.json : fabien-roussel sans_source_officielle=False + sources officielles (prod backend + local backend/hugo-src) — bak .bak-main-20261029-0738
20261029-0738 candidats.json : mira-markovic sans_source_officielle=False + sources officielles (prod backend + local backend/hugo-src) — bak .bak-main-20261029-0738
20261029-0738 candidats.json : natacha-polony sans_source_officielle=False + sources officielles (prod backend + local backend/hugo-src) — bak .bak-main-20261029-0738
20261029-0738 candidats.json : francois-ruffin sans_source_officielle=False + sources officielles (prod backend + local backend/hugo-src) — bak .bak-main-20261029-0738
20261029-0739 candidats.json : marine-tondelier sans_source_officielle=False + sources officielles (prod backend + local backend/hugo-src) — bak .bak-main-20261029-0739
20261029-0749 public_html redéployé à la main (hugo build local, rsync sudo + chown lionel) : vague 2 — Ruffin, Glucksmann, Roussel, Tondelier, Markovic, Polony sortis de « sans programme » ; restent Becht, Platret, Durif — tar prod public_html.bak-main-20261029-0749.tgz (root)
20261029-0845 éditeur = ALPAI (point 1 de dl-repositionnement-vitrine-alpai) : mentions-legales (EI Lionel Denis, marque ALPAI, RCS/SIREN 409 776 861, 55 Grande Rue 73220 Val-d'Arc, TVA 293 B ; exemption LCEN 6 III 2 retirée), pied de page, llms.txt, llms-full.txt, schema.org éditeur (brand + RCS) — baks hugo-src/bak/*bak-main-20261029-editeur ; build local prêt, déploiement public_html par Lionel au !
- 30/10/2026 08:01 — éditeur ALPAI DÉPLOYÉ en prod (rsync par Lionel, sauvegarde public_html.bak-main-*.tgz sur cabahargadon) ; vérifié en ligne : mentions 3× SIREN, llms.txt, pied accueil + fiches.
- 30/10/2026 08:13 — page /soutenir/ RETIRÉE (Liberapay inexistant = 404, contradiction avec éditeur EI) → alias vers /a-propos/ ; « citoyen/bénévole » retirés du pied, feedback, a-propos, dl.js/debat.js/chat.js. Baks hugo-src/bak/*bak-20261030-soutenir. Build prêt, déploiement au ! par Lionel.
- 30/10/2026 14:18 — /a-propos/ RÉÉCRIT : brouillon retiré, éditeur ALPAI (zéro restaurant, règle 25/10), puce actualité, section Neutralité (L52-8), modèle = choix d'ALPAI. Bak hugo-src/bak/a-propos.index.md.bak-20261030-reecriture.
- 30/10/2026 14:29 — /a-propos/ : modèle corrigé DeepSeek → Claude Sonnet 5.5 (orateur) + Haiku 5.5 (juge), en prod depuis dl-orateur-claude-credits-api (23/10), vérifié journaux (api.anthropic.com). Bak a-propos.index.md.bak-20261030-modele.
- 30/10/2026 14:33 — /a-propos/ : section « Du même atelier » (Cassandria, L'Adieu à la Chair, IATV) — UNIQUEMENT sur l'à-propos, hors débats/fiches/accueil. Bak a-propos.index.md.bak-20261030-bloc-alpai.
- 30/10/2026 15:29 — AVERTISSEMENT « projection statistique » (Lionel 30/10) : partial avertissement-projection.html sur fiches (remplace « Vous interrogez le programme officiel »), Arène (setup + bandeau en cours), débat partagé /d/, pied de page, export texte et image ; style .avertissement-projection. Baks hugo-src/bak/*bak-20261030-projection.
- 30/10/2026 15:39 — avertissement « projection statistique » DÉPLOYÉ en prod (rsync lancé par Claude en mode manuel, sauvegarde public_html.bak-main-*.tgz), vérifié en ligne.
- 30/10/2026 20:38 — BILAN DE CORPUS (brique dl-corpus-bilan-quatre-mesures, à la main) : script déterministe zéro LLM tools/bilan_corpus.py (NOUVEAU) → backend/corpus/bilan.json (NOUVEAU, local seulement, rien posé en prod). Lancé sur candidats.json de PROD (29, copie lecture /tmp/claude-1000/.../scratchpad/candidats_prod.json) + corpus local (24) + 5 corpus récupérés de prod par scp en lecture (antoine-mikolajczak, benoit-mathieu, gilles-platret, manolo-mlekuz, sylvain-durif, md5 = prod ; ABSENTS du local). Juge : 29 entrées OK ; Dupont-Aignan fraîcheur 0,0 % OK ; Roussel officialité 100,0 % OK. Commande : python3 tools/bilan_corpus.py --corpus backend/corpus --corpus <dossier_des_5> --candidats <candidats_prod.json>. Bak JOURNAL_MAIN.md.bak-main-*.
- 31/10/2026 06:45 — MENTION DE FRAÎCHEUR (brique dl-fiche-mention-programme-2022, à la main) : tools/fraicheur_hugo.py (NOUVEAU) → hugo-src/data/fraicheur.json ; partial fraicheur-corpus.html (NOUVEAU) appelé dans candidats/single.html (bak hugo-src/bak/single.html.bak-*-fraicheur). Ligne si 2026-27 < 50 % ET part 2022-ou-avant > 0 : 8 fiches.
- 31/10/2026 06:50 — INCIDENT constaté : la prod sert depuis le 30/10 15:33 un rendu du SERVEUR DE DEV (livereload.js + canonical/og/sitemap en http://10.0.0.3:1313, 37 pages HTML, sitemap 35 URL). Cause : le déploiement de l'avertissement a envoyé un rendu `hugo server` et non `hugo --config hugo.toml --destination`. Réparé par le build propre de 06:45 (0 trace dev), déployé par Lionel.
- 31/10/2026 07:00 — DÉPLOYÉ par Lionel (rsync, bak public_html.bak-main-*.tgz) ; vérifié en ligne : 0 trace dev (/, sitemap, fiches, à-propos), canonical https://demandezleur.fr, mention fraîcheur présente sur Le Pen, absente sur Roussel. Incident 10.0.0.3 clos.
- 31/10/2026 07:30 — RÉÉTIQUETAGE AU CANON (préalable de dl-qg-page-bilan-et-envoi) : 61 étiquettes libres → 13 thèmes (2 vers méta : campagne-parrainages → declaration-candidature, vie-du-parti → bio-parcours) ; table tools/reetiquetage_themes.json (NOUVEAU) ; 124 blocs dans 15 corpus, étiquette d'origine gardée au bloc (theme_origine). Posé en LOCAL (bak backend/corpus/*.bak-main-20261031-0723-reetiq) ; PROD à poser par Lionel (scratchpad poser_reetiq_prod.sh — ssh en écriture refusé à Claude). bilan_corpus.py relancé : non classés 72 → 0, thèmes couverts cumulés 199 → 248 (bak bilan.json.bak-main-20261031-0723-reetiq) ; fraicheur_hugo.py relancé : inchangé hors horodatage. Build propre prêt, 0 trace dev.

## 2026-10-31 07:50 — chaîne STYLE : fiches pilotes vertes, banc de validation ROUGE (critère mal posé)
- `style/fiches/{marine-le-pen,jean-luc-melenchon}.yaml` (+ .json compilé) : 11 / 12 traits, 2 preuves mot pour mot chacun, juge `style/outils/verif_fiche.py` VERT. Brique dl-style-fiche-pilote done.
- Banc hors prod (`style/outils/banc_attribution.py`, `banc_paires.py`, `calibrer_juge.py`) : attribution à 4 = mesure du FOND (sans fiche déjà 90 % au juge Sonnet ; Haiku ne reconnaît les vrais pilotes qu'à 45 %). Test en paires à fond constant : la fiche ne gagne pas (≈ 50 %). Cadre arène (parle sec, 1-4 phrases, moule d'adresse) diagnostiqué comme l'écraseur. Rien posé en prod.
20261031-0746 corpus réétiquetés posés en PROD (15 candidats, 124 blocs, canon 13 thèmes, theme_origine gardé) — bak .bak-main-20261031-0746-reetiq

## 2026-10-31 09:40 — Arène : règles PING-PONG posées en LOCAL (prod préparée, pas posée)
- Banc avec garde-fou de prod (`style/outils/banc_attribution.py --tours 3 --sans-seul --gate`, 30 répliques, Sonnet 5.5 / audit Haiku 5.5) :
  prod `style/banc/20261031-0940-attribution-gate.json` vs proto `…-proto-gate.json` → inventions résiduelles 25 = 25 (répliques touchées 19 → 16) ;
  ouverture « Madame/Monsieur » 90 % → 33 % ; tours avec coupure 0 % → 90 % ; 64 → 89 mots en moyenne. Critère « résiduel ≤ prod » TENU.
- Posé en local (bak `.bak-dl-pingpong-20261031-0940`) : `backend/prompts/debat/consigne_arene.txt` + `base_{interpelle,ouverture,reaction,tour_suivant}.txt` (copies de `style/proto/prompts/debat/`),
  `backend/debat.py` `bloc_forme_arene` = logique de `bloc_forme_proto` (vérifié identique en sortie).
- ⚠ Les `base_*` servent AUSSI au mode standard (case « standard » du site) : sa longueur passe de « 2-3 phrases max » à « 3 mots à 4 phrases » — non mesurée au banc.
- Prod : identique au local d'avant pose (md5 vérifiés). Script prêt : `poser_pingpong_prod.sh` (scratchpad session 8d98c6df), à lancer par Lionel.

## 2026-11-01 06:30 — PIÈCES OFFICIELLES 2027 (brique dl-corpus-pieces-officielles-2027), pilote 4 candidats
- Outil NOUVEAU `tools/pieces_2027.py` (zéro LLM) : pages de projet d'un domaine OFFICIEL épinglé → blocs ~600 car. avec `annee` (= année de mise à jour de la page), `date_piece`, `origine: pieces-officielles-2027` ; thème donné par table (canon 13), jamais deviné ; refus du lot si un hôte n'est pas épinglé ; rejouable sans doublon. Texte extrait par extraire.py (scratchpad session 9c528d06).
- Dupont-Aignan : 32 cahiers « projet » de debout-la-france.fr (mis à jour 2024→27/10/2026) + « 20 mesures » dupontaignan.fr (23/10/2026) → 990 blocs neufs, 99 anciens gardés. Bilan local : fraîcheur 2026-27 0 % → 45,2 % (2023-25 44,9 %, ≤2022 9,9 %), couverture 4 → 13/13, 47 k → 480 k car. PROD à poser par Lionel (poser_corpus.sh).
- Le Pen : rien de neuf sur rassemblementnational.fr (contre-budget 2026 d'oct. 2025 déjà au corpus ; le « contre-budget du 06/10/2026 » n'y est PAS publié, seule une source faible le cite → non ingéré).
- Zemmour : leprogrammepourlafrance.fr = plateforme de propositions CITOYENNES de Sarah Knafo → non ingérée (ce n'est pas la parole du candidat).
- Asselineau : upr.fr/notre-programme dit « programme présidentiel 2027 publié prochainement » → rien à ingérer.
20261101-0633 corpus nicolas-dupont-aignan remplacé à la main — pièces officielles 2026-2027 : 33 pages DLF + dupontaignan.fr — bak .bak-main-20261101-0633 (prod+local)

## 2026-11-01 07:10 — COURRIER QG : générateur posé (aperçu local, rien envoyé)
- Outil NOUVEAU `tools/qg_courrier.py` (zéro LLM, gabarit fixe + champs de bilan.json, juge intégré : clause « sauf erreur ou omission », formules interdites, aucun autre nom). 3 aperçus (Dupont-Aignan, Roussel, Durif) JUGE_OK dans le qg/apercus-courrier/ (hors git). Bilan.json posé en prod par Lionel à 07:00 (Dupont-Aignan 45,2 % frais, 13/13).

## 2026-11-01 07:40 — ANNUAIRE QG : canaux complétés (agent contacts, preuves dans p2027/contacts du scratchpad 9c528d06)
- qg/annuaire.yaml (bak .bak-20261101-*) : 27 → 29 entrées (Attal contact@attalpresident.fr ; Retailleau formulaire republicains.fr/contact) ; +7 mails officiels (Batho, Mlekuz, Mathieu, Becht, Philippe, Bertrand, Kazib) ; Dupont-Aignan : afe2027@ en contact_doublon seulement (données structurées, jamais affiché). Restent sans mail : Arthaud, Lalanne, Platret, Dupont-Aignan, Retailleau (formulaires) ; Durif (aucun canal : sites hors ligne). Champs canal_secours (postal, réseaux liés) ajoutés.
- domaines_officiels.json (bak) : retirés generation-ecologie.fr (→ alice-ecologie.fr), xavierbertrand.fr (à vendre), olivierbecht.fr (hors ligne) ; ajoutés generationecologie.fr, delphinebatho.fr, becht2027.fr, benoitmathieu2027.fr. Dolibarr (tiers QG) PAS resynchronisé.

## 2026-11-01 08:30 — PIÈCES OFFICIELLES 2025-2027 : 21 candidats de plus préparés (5 agents de collecte, relus)
- Lots + rapports : tools/pieces_2027_lots/ (pièces, rapports/, bilan_apres.json). pieces_2027.py : règle « lien_depuis » (PDF hébergé hors domaine accepté seulement si une page officielle le lie, vérifié en relisant la page) ; 10 tracts Roussel écartés faute de lien prouvé. PDF Kazib + Mlekuz ré-extraits (colonnes mêlées en -layout).
- domaines_officiels.json : + la-convention.fr (Cazeneuve), dieudolalanne2027.com (Lalanne).
- Inchangés (rien d'officiel daté de neuf) : Bouamrane, Platret, Mathieu, Durif, Le Pen, Zemmour, Asselineau. Mélenchon : 5e version de L'Avenir en commun attendue au Bourget le 07/11 → repasser.
- Fausses fraîcheurs corrigées par les dates réelles : Philippe 100 → 47 %, Cazeneuve 100 → 78 %, Batho 100 → 92 %.
- Pose prod : tools/pieces_2027_lots/poser_lot_20261101.sh (par Lionel).
20261101-0657 corpus anasse-kazib remplacé à la main — pièces officielles 2025-2027 (agents 01/11, rapport /home/lionel/web/demandezleur.fr/tools/pieces_2027_lots/rapports/anasse-kazib.rapport.md) — bak .bak-main-20261101-0657 (prod+local)
20261101-0657 corpus antoine-mikolajczak remplacé à la main — pièces officielles 2025-2027 (agents 01/11, rapport /home/lionel/web/demandezleur.fr/tools/pieces_2027_lots/rapports/antoine-mikolajczak.rapport.md) — bak .bak-main-20261101-0657 (prod+local)
20261101-0657 corpus bernard-cazeneuve remplacé à la main — pièces officielles 2025-2027 (agents 01/11, rapport /home/lionel/web/demandezleur.fr/tools/pieces_2027_lots/rapports/bernard-cazeneuve.rapport.md) — bak .bak-main-20261101-0657 (prod+local)
20261101-0657 corpus bruno-retailleau remplacé à la main — pièces officielles 2025-2027 (agents 01/11, rapport /home/lionel/web/demandezleur.fr/tools/pieces_2027_lots/rapports/bruno-retailleau.rapport.md) — bak .bak-main-20261101-0657 (prod+local)
20261101-0657 corpus delphine-batho remplacé à la main — pièces officielles 2025-2027 (agents 01/11, rapport /home/lionel/web/demandezleur.fr/tools/pieces_2027_lots/rapports/delphine-batho.rapport.md) — bak .bak-main-20261101-0657 (prod+local)
20261101-0657 corpus edouard-philippe remplacé à la main — pièces officielles 2025-2027 (agents 01/11, rapport /home/lionel/web/demandezleur.fr/tools/pieces_2027_lots/rapports/edouard-philippe.rapport.md) — bak .bak-main-20261101-0657 (prod+local)
20261101-0658 corpus fabien-roussel remplacé à la main — pièces officielles 2025-2027 (agents 01/11, rapport /home/lionel/web/demandezleur.fr/tools/pieces_2027_lots/rapports/fabien-roussel.rapport.md) — bak .bak-main-20261101-0658 (prod+local)
20261101-0658 corpus florian-philippot remplacé à la main — pièces officielles 2025-2027 (agents 01/11, rapport /home/lionel/web/demandezleur.fr/tools/pieces_2027_lots/rapports/florian-philippot.rapport.md) — bak .bak-main-20261101-0658 (prod+local)
20261101-0658 corpus francis-lalanne remplacé à la main — pièces officielles 2025-2027 (agents 01/11, rapport /home/lionel/web/demandezleur.fr/tools/pieces_2027_lots/rapports/francis-lalanne.rapport.md) — bak .bak-main-20261101-0658 (prod+local)
20261101-0658 corpus francois-ruffin remplacé à la main — pièces officielles 2025-2027 (agents 01/11, rapport /home/lionel/web/demandezleur.fr/tools/pieces_2027_lots/rapports/francois-ruffin.rapport.md) — bak .bak-main-20261101-0658 (prod+local)
20261101-0658 corpus gabriel-attal remplacé à la main — pièces officielles 2025-2027 (agents 01/11, rapport /home/lionel/web/demandezleur.fr/tools/pieces_2027_lots/rapports/gabriel-attal.rapport.md) — bak .bak-main-20261101-0658 (prod+local)
20261101-0658 corpus jean-luc-melenchon remplacé à la main — pièces officielles 2025-2027 (agents 01/11, rapport /home/lionel/web/demandezleur.fr/tools/pieces_2027_lots/rapports/jean-luc-melenchon.rapport.md) — bak .bak-main-20261101-0658 (prod+local)
20261101-0658 corpus manolo-mlekuz remplacé à la main — pièces officielles 2025-2027 (agents 01/11, rapport /home/lionel/web/demandezleur.fr/tools/pieces_2027_lots/rapports/manolo-mlekuz.rapport.md) — bak .bak-main-20261101-0658 (prod+local)
20261101-0658 corpus marine-tondelier remplacé à la main — pièces officielles 2025-2027 (agents 01/11, rapport /home/lionel/web/demandezleur.fr/tools/pieces_2027_lots/rapports/marine-tondelier.rapport.md) — bak .bak-main-20261101-0658 (prod+local)
20261101-0658 corpus mira-markovic remplacé à la main — pièces officielles 2025-2027 (agents 01/11, rapport /home/lionel/web/demandezleur.fr/tools/pieces_2027_lots/rapports/mira-markovic.rapport.md) — bak .bak-main-20261101-0658 (prod+local)
20261101-0658 corpus nathalie-arthaud remplacé à la main — pièces officielles 2025-2027 (agents 01/11, rapport /home/lionel/web/demandezleur.fr/tools/pieces_2027_lots/rapports/nathalie-arthaud.rapport.md) — bak .bak-main-20261101-0658 (prod+local)
20261101-0658 corpus natacha-polony remplacé à la main — pièces officielles 2025-2027 (agents 01/11, rapport /home/lionel/web/demandezleur.fr/tools/pieces_2027_lots/rapports/natacha-polony.rapport.md) — bak .bak-main-20261101-0658 (prod+local)
20261101-0658 corpus olivier-becht remplacé à la main — pièces officielles 2025-2027 (agents 01/11, rapport /home/lionel/web/demandezleur.fr/tools/pieces_2027_lots/rapports/olivier-becht.rapport.md) — bak .bak-main-20261101-0658 (prod+local)
20261101-0658 corpus raphael-glucksmann remplacé à la main — pièces officielles 2025-2027 (agents 01/11, rapport /home/lionel/web/demandezleur.fr/tools/pieces_2027_lots/rapports/raphael-glucksmann.rapport.md) — bak .bak-main-20261101-0658 (prod+local)
20261101-0658 corpus selma-labib remplacé à la main — pièces officielles 2025-2027 (agents 01/11, rapport /home/lionel/web/demandezleur.fr/tools/pieces_2027_lots/rapports/selma-labib.rapport.md) — bak .bak-main-20261101-0658 (prod+local)
20261101-0659 corpus xavier-bertrand remplacé à la main — pièces officielles 2025-2027 (agents 01/11, rapport /home/lionel/web/demandezleur.fr/tools/pieces_2027_lots/rapports/xavier-bertrand.rapport.md) — bak .bak-main-20261101-0659 (prod+local)
- 01/11/2026 07:20 — /corpus/ : cartes illisibles (fond #fff forcé sous thème sombre) corrigées → jetons du thème dans corpus.css ; POSÉ par Lionel (tools/poser_corpus_css_20261101.sh, bak prod corpus.css.bak-20261101), md5 prod = local, vérifié en ligne. Entrée partition dl-qg-page-2 alignée.
- 01/11/2026 07:45 — heure de pointe : justification « l'IA coûte le double » retirée (plus vraie depuis le crédit API Claude) → « budget d'IA fixé à l'avance, à partager entre tous ». Limite (1 débat/pers.) et horaires (8h-12h, 3h-6h) INCHANGÉS. Bandeau dl.js + MESSAGE_POINTE api.py (édité EN PROD, local api.py toujours en retard). POSÉ par Lionel (tools/poser_pointe_texte_20261101.sh ; bak dl.js.bak-20261101, api.py.bak-20261101-pointe) ; service actif, 0 « coûte le double », site 200.
- 01/11/2026 08:15 — 4 portraits posés (Markovic, Mlekuz, Mathieu, Mikolajczak) : silhouettes « initiales » remplacées. Commons sans photo (homonymes écartés pour B. Mathieu) → photos officielles de campagne (provenance photos-sources/<id>/provenance.json, choix officiel-01.jpg), rendu tools/portrait_local.py (crédit OpenAI à 0, 429). POSÉ par Lionel (tools/poser_portraits4_20261101.sh ; bak prod *.bak-initiales-20261101) ; md5 8/8 en ligne = local.
- 01/11/2026 07:58 — 3 courriers QG d'ESSAI envoyés à lionel.denis@alpai.eu (tools/qg_envoi_essai.py) ; jetons d'essai Roussel + Durif créés (coffre) et posés en prod par Lionel (tools/poser_jetons_essai_20261101.sh, bak jetons.json.bak-20261101-essais).
- 01/11/2026 08:05 — parcours QG joué de bout en bout par Claude (Chrome station) : dépôt communiqué Limoges NDA → accepté par la machine, bilan recalculé (34→35 docs). Brique dl-qg-pdf-poppler-prod ouverte (pdftotext absent en prod).

## 20261101-1914 — dl-durcir-api (partition)
- backend/api.py : 4 correctifs [durcir] (IP réelle lue depuis nginx seulement, CORS sans joker, débat partagé = textes émis seulement, stats admin sur jeton). Bak : api.py.bak-durcir-20261101-1914.
- backend/emis.py : nouveau (registre des textes émis, debats/emis/AAAAMMJJ.txt, 7 jours).
- backend/silence_electoral.py : rapatrié de la prod s'il manquait.
- Prod : mêmes correctifs + drop-in systemd durcir.conf + limit_req nginx dl_api (5 r/s, rafale 20) — voir audit de la partition.

## 20261101-1916 — dl-durcir-api (partition)
- backend/api.py : 4 correctifs [durcir] (IP réelle lue depuis nginx seulement, CORS sans joker, débat partagé = textes émis seulement, stats admin sur jeton). Bak : api.py.bak-durcir-20261101-1916.
- backend/emis.py : nouveau (registre des textes émis, debats/emis/AAAAMMJJ.txt, 7 jours).
- backend/silence_electoral.py : rapatrié de la prod s'il manquait.
- Prod : mêmes correctifs + drop-in systemd durcir.conf + limit_req nginx dl_api (5 r/s, rafale 20) — voir audit de la partition.

## 20261101-1918 — dl-durcir-api (partition)
- backend/api.py : 4 correctifs [durcir] (IP réelle lue depuis nginx seulement, CORS sans joker, débat partagé = textes émis seulement, stats admin sur jeton). Bak : api.py.bak-durcir-20261101-1918.
- backend/emis.py : nouveau (registre des textes émis, debats/emis/AAAAMMJJ.txt, 7 jours).
- backend/silence_electoral.py : rapatrié de la prod s'il manquait.
- Prod : mêmes correctifs + drop-in systemd durcir.conf + limit_req nginx dl_api (5 r/s, rafale 20) — voir audit de la partition.

## 20261101-1923 — dl-durcir-api (partition)
- backend/api.py : 4 correctifs [durcir] (IP réelle lue depuis nginx seulement, CORS sans joker, débat partagé = textes émis seulement, stats admin sur jeton). Bak : api.py.bak-durcir-20261101-1923.
- backend/emis.py : nouveau (registre des textes émis, debats/emis/AAAAMMJJ.txt, 7 jours).
- backend/silence_electoral.py : rapatrié de la prod s'il manquait.
- Prod : mêmes correctifs + drop-in systemd durcir.conf + limit_req nginx dl_api (5 r/s, rafale 20) — voir audit de la partition.
