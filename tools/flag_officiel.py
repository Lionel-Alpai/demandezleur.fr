# flag.py <candidats.json> <id> <sources_json> — sans_source_officielle=False + sources officielles ; ABSENT si l'id n'y est pas
import json,sys
p,cid,src=sys.argv[1],sys.argv[2],json.loads(sys.argv[3])
d=json.load(open(p)); lst=d if isinstance(d,list) else d["candidats"]
for c in lst:
    if c["id"]==cid:
        c["sans_source_officielle"]=False; c["sources"]=src
        json.dump(d,open(p,"w"),ensure_ascii=False,indent=2); print("FLAG_OK",p); break
else: print("ABSENT",p)
