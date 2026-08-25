#!/usr/bin/env python3
"""COLLECTEUR-VÉRIFICATEUR du dossier de l'Arène. Sources VIVANTES (searxng + lecture des pages), jamais la mémoire du modèle.

  faits    : venv/bin/python tools/dossiers_collecter.py faits <candidat_id> [--categorie "condamnations"] [--n 12]
  rapports : venv/bin/python tools/dossiers_collecter.py rapport <famille_de> <famille_vers> [--n 12]

Vérification mécanique d'un FAIT : extraction (dossier_extraire) → réfutation adverse (dossier_refuter) →
  verifie_auto si verdict=confirme ET ≥3 sources concordantes ET classe ∉ {mise_en_examen, condamnation_appel}
  a_valider   sinon (« lapin trop gros » → listé dans backend/dossiers/A_VALIDER.md)
  refuse      si verdict=refute
Un GRIEF : verifie_auto si ≥2 sources pour son meilleur verbatim, a_valider sinon.
Les entrées existantes sont conservées (fusion par empreinte du fait/grief) ; statut `valide`/`refuse` posé par Lionel jamais écrasé.
"""
import argparse, asyncio, hashlib, json, re, subprocess, sys
from datetime import date
from pathlib import Path
R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "backend"))
import llm  # noqa: E402
import trafilatura  # noqa: E402
PROMPTS = R / "backend/prompts/debat"
DOSSIERS = R / "backend/dossiers"
MEDIAS_REFERENCE = ("lemonde.fr", "afp.com", "francetvinfo.fr", "franceinfo.fr", "lefigaro.fr", "liberation.fr", "ouest-france.fr", "france24.com", "lcp.fr",
                    "publicsenat.fr", "assemblee-nationale.fr", "senat.fr", "justice.fr", "legifrance.gouv.fr", "vie-publique.fr", "lesechos.fr", "lepoint.fr",
                    "lexpress.fr", "nouvelobs.com", "la-croix.com", "20minutes.fr", "bfmtv.com", "radiofrance.fr", "rtl.fr", "europe1.fr", "leparisien.fr", "huffingtonpost.fr", "mediapart.fr", "leclubdesjuristes.com", "sudouest.fr", "ladepeche.fr", "cnews.fr", "tf1info.fr")
EXCLUS = ("wikipedia.org", "facebook.com", "x.com", "twitter.com", "youtube.com", "tiktok.com", "reddit.com", "defense.gouv.fr")


def chercher(requete: str, n: int) -> list:
    try:
        out = subprocess.run(["searxng", requete, "--json", "--n", str(n * 2), "--language", "fr"], capture_output=True, text=True, timeout=90).stdout
        res = json.loads(out); res = res if isinstance(res, list) else res.get("results", [])
    except Exception as e:
        print("  searxng KO :", e); return []
    vus, ok = set(), []
    for r in res:
        u = r.get("url", "")
        if not u or any(x in u for x in EXCLUS) or u in vus: continue
        vus.add(u); ok.append(r)
    return ok[:n]


def lire(url: str) -> str:
    try:
        html = trafilatura.fetch_url(url)
        txt = trafilatura.extract(html, include_comments=False, favor_precision=True) if html else ""
        return (txt or "")[:6000]
    except Exception:
        return ""


def media(url: str) -> str:
    m = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
    return m


def articles_texte(arts: list) -> str:
    return "\n\n".join(f"[S{i+1}] {a['media']} — {a.get('title','')} — {a['url']}\n{a['texte']}" for i, a in enumerate(arts))


def empreinte(t: str) -> str:
    return hashlib.sha1(re.sub(r"\W+", " ", t.lower()).strip().encode()).hexdigest()[:10]


def _json(txt: str) -> dict:
    try: return json.loads(txt[txt.find("{"): txt.rfind("}") + 1])
    except Exception: return {}


async def collecter_faits(cid: str, categorie: str, n: int):
    cands = {c["id"]: c for c in json.loads((R / "hugo-src/data/candidats.json").read_text(encoding="utf-8"))}
    c = cands[cid]; nom = c["nom"]
    requetes = [f"{nom} condamnation tribunal", f"{nom} condamné cour d'appel", f"{nom} mise en examen", f"{nom} jugement justice décision"] if categorie == "condamnations" else [f"{nom} {categorie}"]
    arts, vus = [], set()
    for q in requetes:
        for r in chercher(q, n):
            if r["url"] in vus: continue
            vus.add(r["url"]); t = lire(r["url"])
            if len(t) > 400: arts.append({"url": r["url"], "title": r.get("title", ""), "media": media(r["url"]), "texte": t})
    print(f"  {len(arts)} articles lus pour {nom}")
    if not arts: return
    prompt = PROMPTS.joinpath("dossier_extraire.txt").read_text(encoding="utf-8").replace("{nom}", nom).replace("{categorie}", categorie).replace("{articles}", articles_texte(arts))
    d = _json(await llm.completer_texte([{"role": "user", "content": prompt}], cle_demo=("dossier", cid, categorie), max_tokens=1500, temperature=0, extra={"response_format": {"type": "json_object"}}))
    p = DOSSIERS / "faits" / f"{cid}.json"; dossier = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"candidat_id": cid, "entrees": []}
    existants = {e["id"]: e for e in dossier["entrees"]}
    for f in d.get("faits", []):
        if not f.get("fait"): continue
        srcs = [arts[int(s[1:]) - 1] for s in f.get("sources", []) if re.match(r"^S\d+$", s) and 0 < int(s[1:]) <= len(arts)]
        prompt_r = PROMPTS.joinpath("dossier_refuter.txt").read_text(encoding="utf-8").replace("{fait}", f["fait"]).replace("{articles}", articles_texte(arts))
        v = _json(await llm.completer_texte([{"role": "user", "content": prompt_r}], cle_demo=("refuter", cid, empreinte(f["fait"])), max_tokens=500, temperature=0, extra={"response_format": {"type": "json_object"}}))
        verdict, concord = v.get("verdict", "nuance"), int(v.get("sources_concordantes", 0) or 0)
        fait = v.get("fait_corrige") or f["fait"] if verdict == "nuance" and v.get("fait_corrige") else f["fait"]
        medias_ref = sum(1 for s in srcs if any(m in s["media"] for m in MEDIAS_REFERENCE))
        if verdict == "refute": statut = "refuse"
        elif verdict == "confirme" and concord >= 3 and medias_ref >= 2 and f.get("classe") not in ("mise_en_examen", "condamnation_appel") and not f.get("divergences"): statut = "verifie_auto"
        else: statut = "a_valider"
        eid = empreinte(fait)
        anc = existants.get(eid)
        if anc and anc.get("statut") in ("valide", "refuse"): continue  # décision de Lionel, jamais écrasée
        existants[eid] = {"id": eid, "classe": f.get("classe", ""), "fait": fait, "date": f.get("date", ""), "instance": f.get("instance", ""), "statut": statut,
                          "sources": [{"url": s["url"], "media": s["media"], "titre": s.get("title", "")} for s in srcs][:5],
                          "verifie_le": date.today().isoformat(), "notes": f"réfutation : {verdict} ({concord} sources concordantes, {medias_ref} médias de référence) — {v.get('raison', '')}" + (f" | divergences : {f['divergences']}" if f.get("divergences") else "")}
        print(f"  [{statut:12}] {f.get('classe','')}: {fait[:110]}")
    dossier["entrees"] = list(existants.values()); dossier["maj"] = date.today().isoformat()
    p.write_text(json.dumps(dossier, ensure_ascii=False, indent=1), encoding="utf-8")


async def collecter_rapport(de: str, vers: str, n: int):
    familles = json.loads((R / "hugo-src/data/familles.json").read_text(encoding="utf-8"))
    cands = json.loads((R / "hugo-src/data/candidats.json").read_text(encoding="utf-8"))
    noms_de = [c["nom"] for c in cands if c["famille"] == de][:3]; noms_vers = [c["nom"] for c in cands if c["famille"] == vers][:3]
    partis_de = sorted({c["parti_court"] for c in cands if c["famille"] == de}); partis_vers = sorted({c["parti_court"] for c in cands if c["famille"] == vers})
    requetes = [f"{a} attaque {b}" for a in noms_de[:2] for b in noms_vers[:2]] + [f"{' '.join(partis_de[:1])} accuse {' '.join(partis_vers[:1])}", f"{noms_de[0]} contre {noms_vers[0]} déclaration"]
    arts, vus = [], set()
    for q in requetes:
        for r in chercher(q, max(4, n // 2)):
            if r["url"] in vus: continue
            vus.add(r["url"]); t = lire(r["url"])
            if len(t) > 400: arts.append({"url": r["url"], "title": r.get("title", ""), "media": media(r["url"]), "texte": t})
    print(f"  {len(arts)} articles lus pour {de} → {vers}")
    if not arts: return
    prompt = (PROMPTS.joinpath("rapport_extraire.txt").read_text(encoding="utf-8").replace("{de}", de).replace("{de_libelle}", familles[de]["libelle"] + " : " + ", ".join(noms_de))
              .replace("{vers}", vers).replace("{vers_libelle}", familles[vers]["libelle"] + " : " + ", ".join(noms_vers)).replace("{articles}", articles_texte(arts)))
    d = _json(await llm.completer_texte([{"role": "user", "content": prompt}], cle_demo=("rapport", de, vers), max_tokens=1800, temperature=0, extra={"response_format": {"type": "json_object"}}))
    p = DOSSIERS / "rapports" / f"{de}__{vers}.json"; rap = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"de": de, "vers": vers, "registre": "neutre", "griefs": []}
    existants = {g["id"]: g for g in rap.get("griefs", [])}
    if d.get("registre") in ("ennemi_principal", "concurrent_meme_electorat", "rival_interne", "adversaire_respecte", "neutre"):
        rap["registre"], rap["justification"] = d["registre"], d.get("justification", "")
    for g in d.get("griefs", []):
        if not g.get("grief"): continue
        ex = []
        for e in g.get("exemples", []):
            srcs = [arts[int(s[1:]) - 1] for s in e.get("sources", []) if re.match(r"^S\d+$", s) and 0 < int(s[1:]) <= len(arts)]
            if e.get("verbatim") and srcs: ex.append({"auteur": e.get("auteur", ""), "date": e.get("date", ""), "verbatim": e["verbatim"], "media": srcs[0]["media"], "source_url": srcs[0]["url"], "n_sources": len(srcs)})
        if not ex: continue
        gid = empreinte(g["grief"]); anc = existants.get(gid)
        if anc and anc.get("statut") in ("valide", "refuse"): continue
        statut = "verifie_auto" if max(x["n_sources"] for x in ex) >= 2 or len(ex) >= 2 else "a_valider"
        existants[gid] = {"id": gid, "grief": g["grief"], "statut": statut, "exemples": ex[:3], "verifie_le": date.today().isoformat()}
        print(f"  [{statut:12}] {g['grief'][:100]} — ex. {ex[0]['auteur']} ({ex[0]['date']})")
    rap["griefs"] = list(existants.values()); rap["maj"] = date.today().isoformat()
    p.write_text(json.dumps(rap, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  registre : {rap['registre']} — {rap.get('justification', '')[:120]}")


def ecrire_a_valider():
    lignes = ["# Dossier de l'Arène — à valider par Lionel (« lapins trop gros »)", ""]
    for p in sorted((DOSSIERS / "faits").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        for e in d.get("entrees", []):
            if e.get("statut") == "a_valider": lignes.append(f"- **{d['candidat_id']}** [{e.get('classe')}] {e['fait']}\n  - {e.get('notes','')}\n  - sources : " + ", ".join(s['url'] for s in e.get('sources', [])))
    for p in sorted((DOSSIERS / "rapports").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        for g in d.get("griefs", []):
            if g.get("statut") == "a_valider": lignes.append(f"- **{d['de']} → {d['vers']}** {g['grief']} — ex. {g['exemples'][0].get('auteur')} : « {g['exemples'][0].get('verbatim','')[:120]} » ({g['exemples'][0].get('source_url')})")
    (DOSSIERS / "A_VALIDER.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")
    print(f"A_VALIDER.md : {sum(1 for l in lignes if l.startswith('- '))} entrée(s)")


async def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("faits"); f.add_argument("candidat_id"); f.add_argument("--categorie", default="condamnations"); f.add_argument("--n", type=int, default=10)
    r = sub.add_parser("rapport"); r.add_argument("de"); r.add_argument("vers"); r.add_argument("--n", type=int, default=10)
    a = ap.parse_args()
    if a.cmd == "faits": await collecter_faits(a.candidat_id, a.categorie, a.n)
    else: await collecter_rapport(a.de, a.vers, a.n)
    ecrire_a_valider()

asyncio.run(main())
