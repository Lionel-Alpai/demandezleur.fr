#!/bin/bash
# Pose en prod des pièces officielles 2025-2027 (22 candidats) + bilan.json — préparé par Claude le 01/11/2026.
set -e
L=/home/lionel/web/demandezleur.fr/tools/pieces_2027_lots
for s in anasse-kazib antoine-mikolajczak bernard-cazeneuve bruno-retailleau delphine-batho edouard-philippe fabien-roussel florian-philippot francis-lalanne francois-ruffin gabriel-attal jean-luc-melenchon manolo-mlekuz marine-tondelier mira-markovic nathalie-arthaud natacha-polony olivier-becht raphael-glucksmann selma-labib xavier-bertrand; do
  bash /home/lionel/web/demandezleur.fr/tools/poser_corpus.sh $L/$s.json $s "pièces officielles 2025-2027 (agents 01/11, rapport $L/rapports/$s.rapport.md)"
done
B=/home/lionel/web/demandezleur.fr/backend/corpus
cp -p $B/bilan.json $B/bilan.json.bak-main-$(date +%Y%m%d-%H%M)-lot; python3 /home/lionel/web/demandezleur.fr/tools/bilan_corpus.py
scp -q $B/bilan.json cabahargadon:/tmp/bilan.json
ssh cabahargadon 'cd /home/lionel/web/demandezleur.fr/backend/corpus && sudo -n cp -p bilan.json bilan.json.bak-main-$(date +%Y%m%d-%H%M) && sudo -n cp /tmp/bilan.json bilan.json && sudo -n chown lionel:lionel bilan.json && rm /tmp/bilan.json && echo BILAN_PROD_OK'
