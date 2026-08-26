#!/usr/bin/env python3
"""Stock d'AFFICHES pour l'accueil (data/affiches.json) : paires variées × sujets variés × accroches créatives.

- Paires : les 8 manuelles (conservées, "manuel": true) + toutes les paires dont la flèche a un registre marqué
  (ennemi_principal, concurrent_meme_electorat, rival_interne) + des croisements inattendus (familles éloignées).
- Sujets : thèmes de fond + thèmes du feed de l'Assemblée (si le backend tourne) + « probité » quand les deux ont un dossier.
- Accroches : DeepSeek, 3 à 6 mots, registres variés (formule, question, opposition « X ou Y », chiffre du programme),
  SANS jugement sur une personne, sans nom, sans fait — la tension, pas l'accusation. Filtre mécanique ensuite.
Usage : DL_MODE=live venv/bin/python tools/affiches_generer.py [--total 40]"""
import argparse, asyncio, itertools, json, random, re, sys, urllib.request
from pathlib import Path
R = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(R / "backend"))
import llm  # noqa: E402
DATA = R / "hugo-src/data"; RAP = R / "backend/dossiers/rapports"; FAITS = R / "backend/dossiers/faits"
THEMES = ["l'immigration", "les retraites", "le pouvoir d'achat", "l'école", "la sécurité du quotidien", "le nucléaire", "l'hôpital", "le logement",
          "l'Europe", "la laïcité", "les impôts", "le climat", "le travail et les salaires", "la justice", "les institutions et la VIe République",
          "l'agriculture", "l'intelligence artificielle et l'emploi", "la dette publique", "les banlieues", "la ruralité"]
INTERDITS = re.compile(r"menteur|corrompu|fasciste|raciste|antis[ée]mite|voleur|escroc|traître|condamn|prison|nazi|idiot|nul", re.I)
REGISTRE_KICKER = {"ennemi_principal": "Le choc", "concurrent_meme_electorat": "Le même électorat", "rival_interne": "Querelle de famille", "adversaire_respecte": "Le duel des idées"}


def charger():
    cands = json.loads((DATA / "candidats.json").read_text(encoding="utf-8"))
    rapports = {}
    for p in RAP.glob("*.json"):
        d = json.loads(p.read_text(encoding="utf-8")); rapports[(d["de"], d["vers"])] = d.get("registre", "neutre")
    dossiers = {p.stem for p in FAITS.glob("*.json") if any(e.get("statut") in ("valide", "verifie_auto") for e in json.loads(p.read_text(encoding="utf-8")).get("entrees", []))}
    return cands, rapports, dossiers


def themes_assemblee():
    try:
        d = json.load(urllib.request.urlopen("http://127.0.0.1:8001/api/parlement/sujets?n=6", timeout=5))
        return [s["question"] or s["theme"] for s in d.get("sujets", []) if s.get("theme")]
    except Exception:
        return []


def paires(cands, rapports, rng, n_inattendues=8):
    par_id = {c["id"]: c for c in cands}
    poids = ["jean-luc-melenchon", "marine-le-pen", "gabriel-attal", "edouard-philippe", "bruno-retailleau", "xavier-bertrand", "bernard-cazeneuve"]
    out, vus = [], set()
    def ajouter(a, b, motif):
        k = tuple(sorted((a, b)))
        if a == b or k in vus or a not in par_id or b not in par_id: return
        vus.add(k); out.append((a, b, motif))
    for a, b in itertools.combinations(poids, 2): ajouter(a, b, "poids")
    for c1 in cands:
        for c2 in cands:
            r = rapports.get((c1["famille"], c2["famille"]), "neutre")
            if r in ("ennemi_principal", "concurrent_meme_electorat", "rival_interne") and c1["id"] != c2["id"]: ajouter(c1["id"], c2["id"], r)
    tous = [c["id"] for c in cands]; essais = 0
    while n_inattendues > 0 and essais < 200:
        a, b = rng.sample(tous, 2); essais += 1
        if par_id[a]["famille"] != par_id[b]["famille"] and tuple(sorted((a, b))) not in vus: ajouter(a, b, "inattendu"); n_inattendues -= 1
    return out


async def accroches(lots):
    """lots : [{i, a_nom, a_parti, b_nom, b_parti, registre, sujet}] → {i: accroche}"""
    prompt = ("Tu écris des ACCROCHES d'affiche pour des débats politiques fictifs entre programmes de candidats (site citoyen neutre). Pour chaque ligne, "
              "une accroche de 2 à 6 mots, en majuscules d'usage, SANS nom de personne, SANS jugement sur une personne, SANS fait ni chiffre sur une personne, "
              "sans insulte : la TENSION du sujet entre deux camps, pas une accusation. Varie les registres d'une ligne à l'autre : opposition (« Sortir ou relancer »), "
              "question (« Qui paie ? »), formule (« Le même électorat »), enjeu (« 64 ans ou 60 ans »), image (« Deux Frances »). Jamais deux accroches identiques.\n"
              "Réponds en JSON : {\"accroches\": {\"<i>\": \"...\"}}\n\n" +
              "\n".join(f"{l['i']} | {l['a_parti']} ({l['registre']}) contre {l['b_parti']} | sujet : {l['sujet']}" for l in lots))
    txt = await llm.completer_texte([{"role": "user", "content": prompt}], cle_demo=("affiches", len(lots)), max_tokens=2500, temperature=0.9, extra={"response_format": {"type": "json_object"}})
    try: return {str(k): str(v).strip(" .«»\"") for k, v in json.loads(txt[txt.find("{"): txt.rfind("}") + 1]).get("accroches", {}).items()}
    except Exception: return {}


async def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--total", type=int, default=40); ap.add_argument("--graine", type=int, default=2027); a = ap.parse_args()
    rng = random.Random(a.graine); cands, rapports, dossiers = charger(); par_id = {c["id"]: c for c in cands}
    existantes = json.loads((DATA / "affiches.json").read_text(encoding="utf-8")) if (DATA / "affiches.json").exists() else []
    manuelles = [x for x in existantes if x.get("manuel") or x in existantes[:8]]
    for m in manuelles: m["manuel"] = True
    sujets = THEMES + themes_assemblee()
    lots, k = [], 0
    for (x, y, motif) in paires(cands, rapports, rng):
        if len(lots) >= a.total: break
        if rng.random() < 0.5: x, y = y, x
        ca, cb = par_id[x], par_id[y]; registre = rapports.get((ca["famille"], cb["famille"]), "neutre")
        pool = sujets + (["la probité en politique"] * 2 if x in dossiers and y in dossiers else [])
        sujet = rng.choice(pool)
        lots.append({"i": str(k), "a": x, "b": y, "a_nom": ca["nom"], "a_parti": ca["parti_court"], "b_nom": cb["nom"], "b_parti": cb["parti_court"], "registre": registre, "sujet": sujet, "motif": motif}); k += 1
    acc = await accroches(lots)
    nouvelles, vues = [], {m["accroche"].lower() for m in manuelles}
    for l in lots:
        k_ = acc.get(l["i"], "") or REGISTRE_KICKER.get(l["registre"], "Face à face")
        if INTERDITS.search(k_) or any(n.split()[-1].lower() in k_.lower() for n in (l["a_nom"], l["b_nom"])) or len(k_) > 40 or k_.lower() in vues:
            k_ = REGISTRE_KICKER.get(l["registre"], "Face à face")
        vues.add(k_.lower())
        nouvelles.append({"a": l["a"], "b": l["b"], "sujet": l["sujet"], "accroche": k_, "registre": l["registre"], "motif": l["motif"]})
    stock = manuelles + nouvelles
    (DATA / "affiches.json").write_text(json.dumps(stock, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(stock)} affiches ({len(manuelles)} manuelles + {len(nouvelles)} générées)")
    for x in nouvelles[:12]: print(f"  {par_id[x['a']]['nom']:22} vs {par_id[x['b']]['nom']:22} · {x['sujet'][:34]:34} · « {x['accroche']} »")

asyncio.run(main())
