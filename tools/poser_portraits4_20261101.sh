#!/bin/bash
# Pose prod 01/11/2026 : 4 portraits (silhouettes « initiales » remplacées) — Markovic, Mlekuz, Mathieu, Mikolajczak.
# Sources : photos officielles de campagne (provenance dans hugo-src/photos-sources/<id>/provenance.json), rendu portrait_local.py.
set -e
L=/home/lionel/web/demandezleur.fr/hugo-src/static/img/portraits
R=/home/lionel/web/demandezleur.fr/public_html/img/portraits
IDS="mira-markovic manolo-mlekuz benoit-mathieu antoine-mikolajczak"
F=""; for id in $IDS; do F="$F $L/$id.webp $L/$id-320.webp"; done
ssh cabahargadon "mkdir -p /tmp/p4neuf"; scp -q $F cabahargadon:/tmp/p4neuf/
ssh cabahargadon bash -s <<DIST
set -e
for f in /tmp/p4neuf/*.webp; do b=\$(basename \$f)
  sudo cp -p $R/\$b $R/\$b.bak-initiales-20261101
  sudo install -m 664 -o lionel -g lionel \$f $R/\$b
done
rm -rf /tmp/p4neuf
DIST
for id in $IDS; do for v in "" -320; do
  a=$(md5sum < $L/$id$v.webp | cut -c1-32); b=$(curl -s "https://demandezleur.fr/img/portraits/$id$v.webp?x=$RANDOM" | md5sum | cut -c1-32)
  [ "$a" = "$b" ] && echo "OK $id$v" || echo "ÉCART $id$v"; done; done
