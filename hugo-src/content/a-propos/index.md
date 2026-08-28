---
title: "À propos"
type: "page"
layout: "single"
description: "Pourquoi demandezleur.fr existe, ce que le site fait, ce qu'il ne fait pas, et qui le fabrique."
---

> Brouillon à valider par l'éditeur avant publication.

## Pourquoi

Pendant une campagne, on entend beaucoup les candidats et on lit peu leurs programmes. Les programmes sont longs, dispersés, écrits pour convaincre. demandezleur.fr les met dans le fauteuil d'en face : vous posez la question, le programme répond — et il ne répond que ce qu'il contient.

## Ce que fait le site

- **Interroger un programme.** Chaque candidat déclaré à la présidentielle 2027 est représenté par une IA qui répond **uniquement** à partir de ses documents officiels (programme, site de campagne, déclaration de candidature). Sous chaque réponse, les extraits utilisés sont affichés.
- **Faire débattre les programmes.** Vous choisissez un sujet, 2 à 5 candidats, et vous menez le débat : ordre de parole, interpellation, clôture.
- **L'Arène.** Les candidats se voient opposer ce qui s'est réellement dit à l'Assemblée nationale (comptes rendus officiels) et le programme de leurs adversaires. Un garde-fou vérifie chaque affirmation faite sur un adversaire : ce qui n'est pas étayé est marqué d'un astérisque et expliqué, ce qui est faux est retiré et signalé.

## Ce que le site ne fait pas

- Il **n'invente pas** de positions : quand un programme ne traite pas un sujet, l'IA le dit.
- Il **ne conseille pas** un vote et ne classe pas les candidats.
- Il **ne trace pas** ses visiteurs : pas de cookie, pas de compte, pas de publicité.
- Il **n'engage pas** les candidats : les réponses sont générées automatiquement, à partir de documents publics, et peuvent contenir des erreurs. Chaque page le rappelle et le [formulaire de feedback](/feedback/) permet de les signaler.

## Comment c'est fabriqué

Les prompts donnés à l'IA sont [publics](/transparence/), le [code est ouvert](https://github.com/Lionel-Alpai/demandezleur.fr). Le modèle de langage est **DeepSeek V4** (DeepSeek, Hangzhou, Chine), interrogé par API depuis un serveur situé au Canada : aucune donnée de visiteur ne lui est transmise — seuls lui parviennent la question posée et les extraits de documents publics du candidat. Ce choix est technique et économique, non éditorial, et il est susceptible de changer ; la page le dira. Les corpus sont constitués à partir des sources officielles de chaque candidat, listées sur sa fiche ; tout document manquant peut être [suggéré](/suggerer/).

## Qui

Lionel Denis. Restaurateur en Maurienne, pas journaliste, pas encarté. Je fabrique ce site le soir et le lundi — mon jour de fermeture — avec une machine d'agents que j'ai montée moi-même et dont le code est ouvert.

Pourquoi : parce qu'on nous demande de choisir entre des gens dont nous ne lisons jamais les programmes, et que ces programmes sont pourtant publics, en ligne, gratuits. Ce site ne fait qu'une chose : les rendre interrogeables. Si vous y trouvez une erreur, elle est de moi, et le [formulaire de feedback](/feedback/) est là pour ça.

Le projet est indépendant, bénévole, sans affiliation avec un parti, un candidat ou une institution. [Soutenir le projet](/soutenir/).
