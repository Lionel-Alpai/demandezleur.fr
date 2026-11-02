#!/bin/bash
# Pose prod 01/11/2026 :
#  (1) bilan_corpus.py : titre de document sans le « — » orphelin laissé par l'URL retirée (18 titres) ;
#  (2) rejoue l'ingestion QG maintenant (poppler posé) -> les 2 PDF ajournés doivent passer ;
#  (3) régénère bilan.json (si l'ingestion n'a rien touché, on le régénère nous-mêmes).
set -e
R=/home/lionel/web/demandezleur.fr
SRC=$R/tools/bilan_corpus.py
scp -q "$SRC" cabahargadon:/tmp/bilan_corpus.py.neuf
ssh -t cabahargadon "set -e
sudo cp -p $R/tools/bilan_corpus.py $R/tools/bilan_corpus.py.bak-20261101-titre
sudo install -m 644 -o lionel -g lionel /tmp/bilan_corpus.py.neuf $R/tools/bilan_corpus.py && rm /tmp/bilan_corpus.py.neuf
md5sum $R/tools/bilan_corpus.py
echo '--- ingestion QG (rejeu) ---'
sudo systemctl start demandezleur-qg-ingerer.service
tail -n 4 $R/backend/qg/decisions.jsonl | cut -c1-220
echo '--- bilan.json ---'
sudo cp -p $R/backend/corpus/bilan.json $R/backend/corpus/bilan.json.bak-20261101-titre
sudo -u lionel python3 $R/tools/bilan_corpus.py --domaines $R/backend/qg/domaines_officiels.json \
  --candidats $R/backend/candidats.json --corpus $R/backend/corpus --out $R/backend/corpus/bilan.json
grep -c ' —  (' $R/backend/corpus/bilan.json | sed 's/^/titres a tiret orphelin restants: /' || true"
md5sum "$SRC"
