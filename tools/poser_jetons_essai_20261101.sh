#!/bin/bash
# Pose prod 01/11/2026 : 2 jetons d'ESSAI (Roussel, Durif) au registre backend/qg/jetons.json — empreintes seules, marque test.
# Clairs au coffre : pass demandezleur/qg/_test-fabien-roussel, _test-sylvain-durif. Pour le courrier d'essai vers Lionel.
set -e
N=/tmp/claude-1000/-home-lionel/05d40212-e2e8-4f9e-9b56-c4015003b958/scratchpad/jetons_essai_neufs.json
R=/home/lionel/web/demandezleur.fr/backend/qg/jetons.json
scp -q "$N" cabahargadon:/tmp/jetons_essai_neufs.json
ssh cabahargadon bash -s <<DIST
set -e
sudo cp -p $R $R.bak-20261101-essais
sudo python3 - <<'PY'
import json, os
R="$R"; reg=json.load(open(R)); neuf=json.load(open("/tmp/jetons_essai_neufs.json"))
assert all(e.get("test") is True for e in neuf.values()), "entrée sans marque test"
n=0
for h,e in neuf.items():
    if h not in reg: reg[h]=e; n+=1
tmp=R+".tmp"; open(tmp,"w").write(json.dumps(reg,indent=1,sort_keys=True)); os.chmod(tmp,0o640); os.chown(tmp,os.stat(R).st_uid,os.stat(R).st_gid); os.replace(tmp,R)
print("AJOUTES",n,"TOTAL",len(reg))
PY
rm /tmp/jetons_essai_neufs.json
DIST
for s in fabien-roussel sylvain-durif nicolas-dupont-aignan; do J=$(pass show demandezleur/qg/_test-$s | head -1)
  curl -s -o /dev/null -w "$s : %{http_code}\n" "https://demandezleur.fr/api/qg/bilan?j=$J"; done
