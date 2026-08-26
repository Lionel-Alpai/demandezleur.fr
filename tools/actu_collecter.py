#!/usr/bin/env python3
"""COLLECTEUR-VÉRIFICATEUR du tiroir ACTU (prototype) : SearXNG → lecture (trafilatura) → extraction (déclarations verbatim + faits)
→ vérification MÉCANIQUE : un verbatim n'est retenu que s'il est présent LITTÉRALEMENT (≥ 85 % des mots, dans l'ordre) dans le texte
d'une page lue ; un fait n'est vérifié que s'il est rapporté par ≥ 2 articles. Sinon a_valider (pupitre).
Usage : DL_MODE=live venv/bin/python tools/actu_collecter.py [--ids a,b] [--themes "retraites,immigration"] [--n 6]"""
import argparse, asyncio, hashlib, json, re, subprocess, sys, unicodedata
from datetime import date
from pathlib import Path
R = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(R / "backend"))
import llm, trafilatura  # noqa: E402
PROMPT = R / "backend/prompts/debat/actu_extraire.txt"
OUT = R / "backend/actu"; OUT.mkdir(exist_ok=True)
REFERENCE = ("lemonde.fr", "afp.com", "francetvinfo.fr", "franceinfo.fr", "lefigaro.fr", "liberation.fr", "ouest-france.fr", "france24.com", "lcp.fr", "publicsenat.fr",
             "lesechos.fr", "lepoint.fr", "lexpress.fr", "nouvelobs.com", "la-croix.com", "20minutes.fr", "bfmtv.com", "radiofrance.fr", "rtl.fr", "europe1.fr", "leparisien.fr",
             "huffingtonpost.fr", "mediapart.fr", "sudouest.fr", "ladepeche.fr", "cnews.fr", "tf1info.fr", "lejdd.fr", "marianne.net", "politico.eu", "contexte.com", "vie-publique.fr")
EXCLUS = ("wikipedia.org", "facebook.com", "x.com", "twitter.com", "youtube.com", "tiktok.com", "reddit.com", "jeuxvideo.com", "forum")


def norm(t): return re.sub(r"\s+", " ", unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()).strip()


def chercher(q, n):
    try:
        out = subprocess.run(["searxng", q, "--json", "--n", str(n * 2), "--language", "fr"], capture_output=True, text=True, timeout=90).stdout
        res = json.loads(out); res = res if isinstance(res, list) else res.get("results", [])
    except Exception as e:
        print("  searxng KO", str(e)[:60]); return []
    vus, ok = set(), []
    for r in res:
        u = r.get("url", "")
        if not u or any(x in u for x in EXCLUS) or u in vus: continue
        vus.add(u); ok.append(r)
    return ok[:n]


def lire(url):
    try:
        html = trafilatura.fetch_url(url)
        meta = trafilatura.extract(html, include_comments=False, favor_precision=True, output_format="json", with_metadata=True) if html else None
        if not meta: return None
        d = json.loads(meta); return {"texte": (d.get("text") or "")[:8000], "date": (d.get("date") or "")[:10], "titre": d.get("title") or ""}
    except Exception:
        return None


def media(url): return re.sub(r"^https?://(www\.)?", "", url).split("/")[0]


def verbatim_present(verbatim, texte, seuil=0.85):
    """≥ seuil des mots du verbatim, dans l'ordre, dans le texte (tolère ponctuation/accents/coupures)."""
    v, t = norm(verbatim), norm(texte)
    if not v: return False
    if v in t: return True
    mots = [m for m in re.findall(r"[a-z0-9']+", v) if len(m) > 1]
    if len(mots) < 4: return False
    pos, trouves = 0, 0
    for m in mots:
        i = t.find(m, pos)
        if i >= 0 and i - pos < 200: trouves += 1; pos = i + len(m)
    return trouves / len(mots) >= seuil


async def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--ids", default=""); ap.add_argument("--themes", default=""); ap.add_argument("--n", type=int, default=6); a = ap.parse_args()
    cands = json.loads((R / "hugo-src/data/candidats.json").read_text(encoding="utf-8")); par_id = {c["id"]: c for c in cands}
    ids = a.ids.split(",") if a.ids else [c["id"] for c in cands]
    import locale
    mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    m_now, m_prev = mois[date.today().month - 1], mois[(date.today().month - 2) % 12]
    requetes = ([f"{par_id[i]['nom']} {m_now} 2026" for i in ids] + [f"{par_id[i]['nom']} {m_prev} 2026 déclaration" for i in ids]
                + [f"{par_id[i]['nom']} a déclaré" for i in ids] + [f"{t.strip()} {m_now} 2026" for t in a.themes.split(",") if t.strip()])
    arts, vus = [], set()
    for q in requetes:
        for r in chercher(q, a.n):
            if r["url"] in vus: continue
            vus.add(r["url"]); pg = lire(r["url"])
            if pg and len(pg["texte"]) > 500:
                arts.append({"url": r["url"], "media": media(r["url"]), "titre": pg["titre"] or r.get("title", ""), "date": pg["date"], "texte": pg["texte"]})
    print(f"{len(arts)} articles lus ({sum(1 for x in arts if any(m in x['media'] for m in REFERENCE))} de référence)")
    if not arts: return
    liste = ", ".join(f"{c['id']} ({c['nom']})" for c in cands)
    jour = OUT / f"{date.today().isoformat()}.json"; doc = json.loads(jour.read_text(encoding="utf-8")) if jour.exists() else {"jour": date.today().isoformat(), "entrees": []}
    existants = {e["id"]: e for e in doc["entrees"]}
    for lot in [arts[i:i + 8] for i in range(0, len(arts), 8)]:
        txt_arts = "\n\n".join(f"[S{i+1}] {x['media']} — {x['titre']} — {x['date']} — {x['url']}\n{x['texte'][:5000]}" for i, x in enumerate(lot))
        prompt = PROMPT.read_text(encoding="utf-8").replace("{candidats}", liste).replace("{articles}", txt_arts)
        rep = await llm.completer_texte([{"role": "user", "content": prompt}], cle_demo=("actu", hashlib.sha1(txt_arts.encode()).hexdigest()[:10]), max_tokens=2500, temperature=0, extra={"response_format": {"type": "json_object"}})
        try: d = json.loads(rep[rep.find("{"): rep.rfind("}") + 1])
        except Exception: d = {}
        def src(refs):
            out = []
            for s_ in refs or []:
                m = re.match(r"^S(\d+)$", str(s_))
                if m and 0 < int(m.group(1)) <= len(lot): out.append(lot[int(m.group(1)) - 1])
            return out
        for dcl in d.get("declarations", []):
            cid, vb = dcl.get("candidat_id"), (dcl.get("verbatim") or "").strip(" «»\"")
            if cid not in par_id or len(vb.split()) < 6: continue
            pages = src(dcl.get("sources"))
            preuve = [p for p in pages if verbatim_present(vb, p["texte"])]
            statut = "verifie_auto" if preuve and any(m in preuve[0]["media"] for m in REFERENCE) else ("a_valider" if pages else "refuse")
            eid = hashlib.sha1(norm(vb).encode()).hexdigest()[:10]
            if eid in existants and existants[eid].get("statut") in ("valide", "refuse"): continue
            existants[eid] = {"id": eid, "type": "declaration", "candidat_id": cid, "verbatim": vb, "date": dcl.get("date") or (preuve[0]["date"] if preuve else ""), "ou": dcl.get("ou", ""),
                              "media": (preuve or pages or [{"media": ""}])[0]["media"], "url": (preuve or pages or [{"url": ""}])[0]["url"],
                              "sources": [{"url": p["url"], "media": p["media"], "titre": p["titre"][:90]} for p in pages][:4], "themes": [t.lower() for t in (dcl.get("themes") or [])][:6],
                              "statut": statut, "verifie_le": date.today().isoformat(), "preuve": "verbatim retrouvé littéralement dans la page" if preuve else "verbatim NON retrouvé dans les pages lues"}
            print(f"  [{statut:12}] {par_id[cid]['nom']:20} « {vb[:90]} » ({existants[eid]['media']})")
        for f in d.get("faits", []):
            ft = (f.get("fait") or "").strip()
            if len(ft.split()) < 5: continue
            pages = src(f.get("sources")); medias = {p["media"] for p in pages}
            statut = "verifie_auto" if len(medias) >= 2 and any(any(m in x for m in REFERENCE) for x in medias) else ("a_valider" if pages else "refuse")
            eid = hashlib.sha1(norm(ft).encode()).hexdigest()[:10]
            if eid in existants and existants[eid].get("statut") in ("valide", "refuse"): continue
            existants[eid] = {"id": eid, "type": "fait", "fait": ft, "date": f.get("date") or (pages[0]["date"] if pages else ""), "media": ", ".join(sorted(medias))[:80],
                              "url": pages[0]["url"] if pages else "", "sources": [{"url": p["url"], "media": p["media"], "titre": p["titre"][:90]} for p in pages][:4],
                              "themes": [t.lower() for t in (f.get("themes") or [])][:6], "statut": statut, "verifie_le": date.today().isoformat(), "preuve": f"{len(medias)} média(s) concordant(s)"}
            print(f"  [{statut:12}] FAIT « {ft[:100]} » ({len(medias)} médias)")
    doc["entrees"] = list(existants.values()); jour.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    print("par candidat :", dict(Counter(e["candidat_id"] for e in doc["entrees"] if e["type"] == "declaration")))
    print("fichier :", jour)

asyncio.run(main())
