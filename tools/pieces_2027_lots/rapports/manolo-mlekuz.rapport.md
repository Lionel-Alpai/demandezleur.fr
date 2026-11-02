# Manolo Mlekuz — rapport de collecte (01/11/2026)

Domaine épinglé : trajectoire2027.fr. Sitemap de 8 URL, toutes au lastmod 2026-10-03. Le site rend son contenu en JS : la FAQ est chargée depuis /data/faq.json.

## Dates réelles du corpus existant
- Pages trajectoire2027.fr (accueil, programme, tour de France, équipe) : lastmod 2026-10-03, donc 2026 vérifié. Mais le bloc « programme » du corpus **ne correspond plus** à la page en ligne : le calendrier, le référendum d'initiative constituante et le tirage au sort n'y figurent pas. Le corpus a donc été pris sur une version antérieure ou incomplète.
- **Le corpus contient des sources NON officielles** : Wikipédia (01-wikipedia-bio.txt), RMC BFM « Les Grandes Gueules » du 3 juillet 2026 et Valeurs actuelles. C'est contraire à la règle 2, et c'est à purger lors de la refonte.

## Pièces retenues (2, ~55 000 car.)
| Fichier | Date (source) | Thème |
|---|---|---|
| mm-programme-detaille-livre-blanc-2026-10.txt — PDF « programme détaillé » lié depuis /programme : livre blanc « Nouvelle démocratie » de l'ONG Démocratie Ouverte, publié « avec l'accord de ses auteurs », 22 p., ~51 500 car. | 2026-10-22 | institutions |
| mm-faq-assemblee-constituante-2026-10.txt — /faq, contenu servi par /data/faq.json (7 Q/R, ~3 300 car.) | 2026-10-22 | institutions |

La date des deux pièces est **faible** : c'est l'en-tête HTTP `Last-Modified: Thu, 22 Oct 2026` du serveur, sans date éditoriale. Le PDF n'a ni CreationDate ni date interne. Ce même horodatage vaut pour plusieurs fichiers, il s'agit vraisemblablement d'un déploiement. La pièce est donc publiée au plus tard le 22/10/2026. À écarter si une date éditoriale est exigée.

## Absent / à noter
- Le programme est **uniquement institutionnel** (processus constituant : référendum en juin-juillet 2027, assemblée tirée au sort, référendum d'adoption en décembre 2028). Il n'y a rien sur les autres thèmes.
- La page /presse est vide. /soutenir n'a pas de contenu programmatique. /data/maires.json ne contient que l'itinéraire.
- robots.txt (Cloudflare) déclare `Content-Signal: search=yes, ai-train=no, use=reference`. Il ne dit rien de `ai-input`. Je le signale pour l'usage RAG.
- La page /programme en ligne (4 800 car.) a été extraite en raw/ mais **non retenue**, parce qu'elle double le PDF. Elle pourrait remplacer le bloc programme périmé du corpus.
- Pièces non datées écartées : aucune. Domaines à épingler : aucun.
