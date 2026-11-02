#!/usr/bin/env python3
"""BANC EN PAIRES — mesure la VOIX à fond constant (remplace l'attribution à 4, 31/10/2026).

Constat du 31/10 : l'attribution à l'aveugle mesure le FOND (les extraits de programme trahissent
l'orateur) : sans fiche, Sonnet attribue déjà 90 % des répliques (+25 points impossibles) ; Haiku ne
reconnaît les VRAIS pilotes que dans 45 % de leurs vrais verbatims (Sonnet 72 %).
Ici, pour chaque (sujet, tour, orateur) du rapport banc_attribution, le juge voit les deux
répliques — AVEC et SANS fiche, ordre tiré au sort, noms masqués — et 6 vrais verbatims de
l'orateur (hors citations de la fiche), et désigne celle qui sonne le plus comme lui.

Juge d'effet : la réplique AVEC fiche gagne >= 70 % des paires pour CHAQUE pilote (juge constant),
et le rapport source est vert sur copie / caricature / tics.
  python3 ../style/outils/banc_paires.py ../style/banc/<ts>-attribution.json
"""
import asyncio, json, random, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import banc_attribution as b  # noqa: E402

SEUIL = 70.0
JUGE = """Voici comment {nom} parle VRAIMENT (extraits authentiques de ses interventions) :
{refs}

Deux répliques de débat, écrites pour {nom}, défendent les mêmes idées. Les noms propres sont masqués par [X].
A : « {a} »
B : « {b} »
Laquelle sonne le plus comme {nom} parle réellement — rythme, tournures, manière d'attaquer et d'encaisser — sans tomber dans la caricature ? Ignore le fond, juge la VOIX.
Réponds UNIQUEMENT par un JSON : {{"choix": "A" ou "B", "raison": "<courte>"}}"""


def references(p, fiche, n=6):
    exclus = {b.mots(c).__str__() for c in [x for t in fiche["traits"] for x in t["preuves"]] + fiche["exemples"]}
    rows = [json.loads(l)["texte"] for f in sorted((b.STYLE / "verbatims").glob(f"{p}.*.jsonl")) for l in open(f, encoding="utf-8")]
    rows = [t for t in rows if 25 <= len(t.split()) <= 90 and not any(c in t for c in exclus)]
    return random.sample(rows, n)


async def main(chemin):
    random.seed(1031)
    d = json.loads(Path(chemin).read_text(encoding="utf-8"))
    fiches = {i: b.fiche_prompt.charger_fiche(i) for i in b.PILOTES}
    noms = {i: b.charger_candidat(i)["nom"] for i in b.PILOTES}
    refs = {p: "\n".join(f"— « {b.MASQUE.sub('[X]', t)} »" for t in references(p, fiches[p])) for p in b.PILOTES}
    cle = lambda l: (l["sujet"], l["tour"], l["orateur"])
    avec = {cle(l): l for l in d["repliques"] if l["avec_fiche"]}
    sans = {cle(l): l for l in d["repliques"] if not l["avec_fiche"]}

    async def une(k):
        p = k[2]; inverse = random.random() < 0.5
        x, y = b.MASQUE.sub("[X]", avec[k]["texte"]), b.MASQUE.sub("[X]", sans[k]["texte"])
        a_, b_ = (y, x) if inverse else (x, y)
        r = b.json_tolerant(await b.llm.completer_texte(
            [{"role": "user", "content": JUGE.format(nom=noms[p], refs=refs[p], a=a_, b=b_) + b.llm.CONSIGNE_JSON}],
            cle_demo=("banc-style-paire",) + k, max_tokens=200, temperature=0))
        gagne = (r.get("choix") == ("B" if inverse else "A")) if r.get("choix") in ("A", "B") else None  # JSON illisible = non jugée
        return {"sujet": k[0], "tour": k[1], "orateur": p, "avec_gagne": gagne, "raison": r.get("raison")}

    res = await asyncio.gather(*[une(k) for k in sorted(avec) if k in sans])
    juges = [r for r in res if r["avec_gagne"] is not None]
    mes = {p: round(100 * sum(r["avec_gagne"] for r in juges if r["orateur"] == p) / max(1, sum(r["orateur"] == p for r in juges)), 1) for p in b.PILOTES}
    mes["non_jugees"] = len(res) - len(juges)
    vert = all(mes[p] >= SEUIL for p in b.PILOTES) and mes["non_jugees"] <= len(res) // 5 and d["mesures"]["copies"] == 0 and d["mesures"]["caricature_a_3"] == 0 \
        and (d["mesures"]["caricature_moyenne"] or 9) < 1 and d["mesures"]["tics_hors_plafond"] == 0
    sortie = Path(chemin).with_name(Path(chemin).stem + f"-paires-{b.llm.MODELE_JUGE}.json")
    sortie.write_text(json.dumps({"juge": b.llm.MODELE_JUGE, "avec_gagne_pct": mes, "vert": vert, "paires": res}, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in res:
        print(("AVEC " if r["avec_gagne"] else "sans ") + f"{r['orateur'][:12]:12} {r['sujet'][:20]:20} T{r['tour']} {r['raison']}")
    print("juge", b.llm.MODELE_JUGE, "AVEC gagne :", mes, "→", sortie)
    print("VERDICT", "VERT" if vert else "ROUGE")

asyncio.run(main(sys.argv[1]))
