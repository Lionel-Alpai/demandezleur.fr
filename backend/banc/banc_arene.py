#!/usr/bin/env python3
"""BANC de l'Arène — mesure ce que le garde-fou attrape et ce qui reste.

  venv/bin/python -m banc.banc_arene --paires 4 --sujets fixe --tours 1 [--sans-gate] [--json]

Sans HTTP ni quota : appelle directement construire_prompt_debat + generer_replique_validee.
Métriques par réplique :
  brut       : affirmations non ancrées détectées sur le texte BRUT (juge + regex)
  residuel   : affirmations non soutenues dans le texte FINAL, mesurées par un AUDIT INDÉPENDANT
               (autre prompt, température 0) — on ne mesure pas avec l'instrument qui filtre
  repli      : répliques tombées sur « je vous renvoie à mon programme »
Rapport : banc/rapports/<date>-arene.md (+ .json)
"""
import argparse, asyncio, json, sys, time
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import llm, garde_fou, debat, parlement  # noqa: E402
from debat import construire_prompt_debat, charger_candidat, charger_faits, MAX_TOKENS_ARENE, TEMPERATURE_ARENE  # noqa: E402

PAIRES = [("marine-le-pen", "gabriel-attal"), ("jean-luc-melenchon", "edouard-philippe"), ("jerome-guedj", "bruno-retailleau"),
          ("nathalie-arthaud", "xavier-bertrand"), ("florian-philippot", "bernard-cazeneuve"), ("delphine-batho", "nicolas-dupont-aignan"),
          ("francois-asselineau", "gabriel-attal"), ("anasse-kazib", "marine-le-pen")]
SUJETS_FIXES = ["les retraites", "l'immigration", "le nucléaire", "l'école", "la sécurité du quotidien"]
AUDIT = Path(__file__).resolve().parent.parent / "prompts" / "debat" / "audit_arene.txt"


async def auditer(texte, orateur, adversaires, preuves, faits, historique):
    docs = garde_fou._formater_pieces(preuves) + "\nFAITS :\n" + garde_fou._formater_faits(adversaires, faits) + "\nASSEMBLÉE :\n" + garde_fou._formater_piece_assemblee(preuves) + "\nHISTORIQUE :\n" + garde_fou._formater_historique(historique, adversaires)
    prompt = AUDIT.read_text(encoding="utf-8").replace("{adversaires}", ", ".join(f"{a['id']} → {a['nom']}" for a in adversaires)).replace("{documents}", docs).replace("{replique}", texte)
    txt = await llm.completer_texte([{"role": "user", "content": prompt}], cle_demo=("audit", orateur["id"], llm.normaliser(texte)[:80]), max_tokens=600, temperature=0,
                                    extra={"response_format": {"type": "json_object"}})
    d = garde_fou._extraire_json(txt)
    return [a for a in d.get("affirmations", []) if isinstance(a, dict) and a.get("soutenue") is False]


async def une_replique(orateur, adversaires, sujet, tours, gate):
    faits = charger_faits(); cache = {}; historique = []; lignes = []
    for tour in range(1, tours + 1):
        type_tour = "ouverture" if tour == 1 else "tour_suivant"
        interventions = []
        for c in [orateur] + adversaires:
            advs = [x for x in [orateur] + adversaires if x["id"] != c["id"]]
            prompt, preuves = construire_prompt_debat(candidat=c, tour=tour, type_tour=type_tour, sujet=sujet, historique=historique,
                                                      position_dans_tour=0, cache_rag=cache, mode="arene", adversaires=advs)
            msgs = [{"role": "system", "content": prompt}, {"role": "user", "content": "Prends la parole maintenant."}]
            t0 = time.time()
            if gate:
                texte, revisions, annotations, meta = await garde_fou.generer_replique_validee(msgs, params=dict(max_tokens=MAX_TOKENS_ARENE, temperature=TEMPERATURE_ARENE),
                    orateur=c, adversaires=advs, preuves=preuves, faits=faits, historique=historique, cle_demo=("banc", c["id"], sujet, tour), juger_actif=True,
                    cible_par_defaut=(advs[0]["id"] if len(advs) == 1 else None))
                brut = meta["brut"]
            else:
                morceaux = []
                async for d in llm.completer(msgs, cle_demo=("banc", c["id"], sujet, tour), max_tokens=MAX_TOKENS_ARENE, temperature=TEMPERATURE_ARENE):
                    morceaux.append(d)
                texte = brut = "".join(morceaux); revisions, annotations, meta = [], [], {"regenerations": 0, "fallback": False}
            latence = time.time() - t0
            non_soutenues = await auditer(texte, c, advs, preuves, faits, historique)
            lignes.append({"sujet": sujet, "tour": tour, "orateur": c["id"], "adversaires": [a["id"] for a in advs], "brut": brut, "final": texte,
                           "revisions": revisions, "annotations": annotations, "regenerations": meta.get("regenerations", 0), "fallback": meta.get("fallback", False),
                           "residuel": non_soutenues, "latence_s": round(latence, 1)})
            interventions.append({"candidat_id": c["id"], "candidat_nom": c["nom"], "texte": texte})
            print(f"  {sujet[:22]:22} T{tour} {c['id']:22} retirées={len(revisions)} annotées={len(annotations)} regen={meta.get('regenerations',0)} résiduel={len(non_soutenues)} {latence:.1f}s", flush=True)
        historique.append({"tour": tour, "type": type_tour, "interventions": interventions})
    return lignes


async def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--paires", type=int, default=4); ap.add_argument("--sujets", default="fixe")
    ap.add_argument("--tours", type=int, default=1); ap.add_argument("--sans-gate", action="store_true"); ap.add_argument("--max-sujets", type=int, default=3)
    a = ap.parse_args()
    sujets = []
    if "fixe" in a.sujets: sujets += SUJETS_FIXES
    if "feed" in a.sujets:
        import themes_parlement
        sujets += [s["question"] or s["theme"] for s in themes_parlement.enrichir(parlement.sujets(n=64)["sujets"])[:5]]
    sujets = sujets[:a.max_sujets]
    resultats = []
    for i, (o, adv) in enumerate(PAIRES[:a.paires]):
        sujet = sujets[i % len(sujets)]
        print(f"[{i+1}/{a.paires}] {o} vs {adv} — {sujet}")
        resultats += await une_replique(charger_candidat(o), [charger_candidat(adv)], sujet, a.tours, gate=not a.sans_gate)
    n = len(resultats)
    brut = sum(len(r["revisions"]) + len(r.get("annotations", [])) for r in resultats)
    res = sum(len(r["residuel"]) for r in resultats)
    repl = sum(1 for r in resultats if r["fallback"])
    regen = sum(r["regenerations"] for r in resultats)
    lat = sorted(r["latence_s"] for r in resultats)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    md = [f"# Banc Arène — {stamp} — gate {'OFF' if a.sans_gate else 'ON'}", "",
          f"- répliques : **{n}** ({a.paires} paires × {a.tours} tour(s) × 2 orateurs)",
          f"- affirmations traitées par le garde-fou : **{brut}** ({brut/max(1,n):.2f}/réplique) — retirées (fausses, A.2) : {sum(len(r['revisions']) for r in resultats)} · annotées (non étayées, A.3) : {sum(len(r.get('annotations', [])) for r in resultats)}",
          f"- affirmations NON SOUTENUES restantes (audit indépendant) : **{res}** ({res/max(1,n):.2f}/réplique) → taux résiduel {100*sum(1 for r in resultats if r['residuel'])/max(1,n):.0f} % des répliques",
          f"- replis « je vous renvoie à mon programme » : {repl} ({100*repl/max(1,n):.0f} %) · régénérations : {regen}",
          f"- latence par réplique : p50 {lat[len(lat)//2] if lat else 0}s · max {lat[-1] if lat else 0}s", "", "## Détail", ""]
    for r in resultats:
        md.append(f"### {r['orateur']} vs {', '.join(r['adversaires'])} — {r['sujet']} (T{r['tour']})")
        md.append(f"**Final :** {r['final']}\n")
        for v in r["revisions"]: md.append(f"- retiré (fausse) : « {v['phrase'][:160]} » — {v['raison'][:120]}")
        for v in r.get("annotations", []): md.append(f"- annoté* (non étayée) : « {v['phrase'][:160]} » — {v['raison'][:120]}")
        for v in r["residuel"]: md.append(f"- ⚠ résiduel : « {str(v.get('phrase',''))[:160]} » — {str(v.get('raison',''))[:120]}")
        md.append("")
    out = Path(__file__).resolve().parent / "rapports"; out.mkdir(exist_ok=True)
    (out / f"{stamp}-arene{'-sansgate' if a.sans_gate else ''}.md").write_text("\n".join(md), encoding="utf-8")
    (out / f"{stamp}-arene{'-sansgate' if a.sans_gate else ''}.json").write_text(json.dumps(resultats, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(md[:8])); print("rapport :", out / f"{stamp}-arene.md")

asyncio.run(main())
