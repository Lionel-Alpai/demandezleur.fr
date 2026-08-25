#!/usr/bin/env python3
"""Porte de validation du dossier (Lionel). Ne s'édite pas à la main : chaque décision est tracée.
  python3 tools/dossiers_valider.py liste                       → entrées à valider (id, résumé)
  python3 tools/dossiers_valider.py <id> valide|refuse [motif]  → pose le statut, journalise dans backend/dossiers/JOURNAL.jsonl
"""
import json, sys
from datetime import datetime
from pathlib import Path
R = Path(__file__).resolve().parent.parent / "backend/dossiers"
def tous():
    for p in sorted((R / "faits").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        for e in d.get("entrees", []): yield p, d, e, "fait", f"{d['candidat_id']} [{e.get('classe')}] {e['fait'][:130]}"
    for p in sorted((R / "rapports").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        for g in d.get("griefs", []): yield p, d, g, "grief", f"{d['de']}→{d['vers']} {g['grief'][:110]} — ex. {g['exemples'][0].get('auteur','')} ({g['exemples'][0].get('date','')})"
if len(sys.argv) < 2 or sys.argv[1] == "liste":
    for p, d, e, k, s in tous():
        if e.get("statut") == "a_valider": print(f"{e['id']}  {s}")
    sys.exit(0)
eid, statut = sys.argv[1], sys.argv[2]; motif = " ".join(sys.argv[3:])
assert statut in ("valide", "refuse", "a_valider"), "statut : valide | refuse | a_valider"
for p, d, e, k, s in tous():
    if e["id"] == eid:
        e["statut"], e["decide_le"], e["motif"] = statut, datetime.now().isoformat(timespec="minutes"), motif
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        with open(R / "JOURNAL.jsonl", "a", encoding="utf-8") as j: j.write(json.dumps({"quand": e["decide_le"], "id": eid, "type": k, "statut": statut, "motif": motif, "resume": s}, ensure_ascii=False) + "\n")
        print(f"{statut} → {s}"); sys.exit(0)
print("id inconnu"); sys.exit(1)
