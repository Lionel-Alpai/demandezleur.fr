#!/bin/bash
# poser_corpus.sh <fichier.json> <candidat_id> "<note>" — pose un corpus en prod (cabahargadon) + local, .bak horodaté + JOURNAL_MAIN.md
set -e
F=$1; C=$2; TS=$(date +%Y%m%d-%H%M); P=/home/lionel/web/demandezleur.fr/backend/corpus
python3 -c "import json,sys;d=json.load(open(sys.argv[1]));assert all(set(b)>={'text','source','page','theme','id'} for b in d);print('blocs',len(d))" "$F"
scp -q "$F" cabahargadon:/tmp/$C.json
ssh cabahargadon "cd $P && sudo -n cp -p $C.json $C.json.bak-main-$TS && sudo -n cp /tmp/$C.json $C.json && sudo -n chown lionel:lionel $C.json && sudo -n chmod 644 $C.json && rm /tmp/$C.json && echo PROD_OK"
L=~/web/demandezleur.fr/backend/corpus; [ -f $L/$C.json ] && cp -p $L/$C.json $L/$C.json.bak-main-$TS; cp "$F" $L/$C.json
echo "$TS corpus $C remplacé à la main — $3 — bak .bak-main-$TS (prod+local)" >> ~/web/demandezleur.fr/JOURNAL_MAIN.md
