#!/bin/bash
# Pose prod 01/11/2026 : jetons QG de Gabriel Attal et Bruno Retailleau (ajoutés à l'annuaire après la 1re génération).
# Empreintes seules ; clairs au coffre pass demandezleur/qg/gabriel-attal, bruno-retailleau.
set -e
N=/tmp/claude-1000/-home-lionel/67c84445-cefe-44e0-9d4e-c2f6b723621e/scratchpad/jetons_qg_neufs.json
R=/home/lionel/web/demandezleur.fr/backend/qg/jetons.json
scp -q "$N" cabahargadon:/tmp/jetons_qg_neufs.json
ssh cabahargadon bash -s <<DIST
set -e
sudo cp -p $R $R.bak-20261101-attal-retailleau
sudo python3 - <<'PY'
import json, os
R="$R"; reg=json.load(open(R)); neuf=json.load(open("/tmp/jetons_qg_neufs.json"))
assert sorted(e["slug"] for e in neuf.values()) == ["bruno-retailleau", "gabriel-attal"], "contenu inattendu"
n=0
for h,e in neuf.items():
    if h not in reg: reg[h]=e; n+=1
tmp=R+".tmp"; open(tmp,"w").write(json.dumps(reg,indent=1,sort_keys=True)); os.chmod(tmp,0o640); os.chown(tmp,os.stat(R).st_uid,os.stat(R).st_gid); os.replace(tmp,R)
print("AJOUTES",n,"TOTAL",len(reg))
PY
rm /tmp/jetons_qg_neufs.json
DIST
for s in gabriel-attal bruno-retailleau; do J=$(pass show demandezleur/qg/$s | head -1); sleep 3
  curl -s -o /dev/null -w "$s : %{http_code}\n" "https://demandezleur.fr/api/qg/bilan?j=$J"; done
