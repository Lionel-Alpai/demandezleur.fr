#!/bin/bash
# poser_flag.sh <candidat_id> '<sources json>' — lève sans_source_officielle en prod (backend/candidats.json) + local (backend, hugo-src/data), .bak + JOURNAL_MAIN.md
set -e
C=$1; TS=$(date +%Y%m%d-%H%M); P=/home/lionel/web/demandezleur.fr/backend; T=/home/lionel/web/demandezleur.fr/tools; W=$(mktemp)
scp -q cabahargadon:$P/candidats.json $W
python3 $T/flag_officiel.py $W $C "$2"
scp -q $W cabahargadon:/tmp/dl-candidats.json
ssh cabahargadon "cd $P && sudo -n cp -p candidats.json candidats.json.bak-main-$TS && sudo -n cp /tmp/dl-candidats.json candidats.json && sudo -n chown lionel:lionel candidats.json && sudo -n chmod 644 candidats.json && rm /tmp/dl-candidats.json && echo PROD_OK"
rm -f $W
L=~/web/demandezleur.fr; mkdir -p $L/hugo-src/bak
cp -p $L/backend/candidats.json $L/hugo-src/bak/backend-candidats.json.bak-main-$TS; python3 $T/flag_officiel.py $L/backend/candidats.json $C "$2"
cp -p $L/hugo-src/data/candidats.json $L/hugo-src/bak/candidats.json.bak-main-$TS; python3 $T/flag_officiel.py $L/hugo-src/data/candidats.json $C "$2"
echo "$TS candidats.json : $C sans_source_officielle=False + sources officielles (prod backend + local backend/hugo-src) — bak .bak-main-$TS" >> $L/JOURNAL_MAIN.md
