#!/bin/bash
# Pose prod : correctif cosmétique des cartes de /corpus/ (fond blanc -> jetons du thème sombre). 01/11/2026.
set -e
SRC=/home/lionel/web/demandezleur.fr/hugo-src/themes/demandezleur/static/css/corpus.css
P=/home/lionel/web/demandezleur.fr/public_html/css/corpus.css
scp -q "$SRC" cabahargadon:/tmp/corpus.css.neuf
ssh -t cabahargadon "sudo cp -p $P $P.bak-20261101 && sudo install -m 644 -o lionel -g lionel /tmp/corpus.css.neuf $P && rm /tmp/corpus.css.neuf && md5sum $P"
md5sum "$SRC"
curl -s https://demandezleur.fr/css/corpus.css | grep -c 'var(--bg-3)' | sed 's/^/jetons en ligne: /'
