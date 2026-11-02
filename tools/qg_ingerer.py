#!/usr/bin/env python3
"""qg_ingerer.py — QG page 4/4 : validation MACHINE + ingestion des depots (timer horaire).

Lit backend/qg/depots/<slug|_public>/*.json (ecrits par qg_depot.py), decide seul :
  - URL acceptee ssi son hote (apres redirections) est un domaine officiel du candidat ; agregateurs refuses ;
  - PDF transmis via jeton = accepte (le jeton authentifie l'equipe) ; PDF public sans jeton = refuse ;
  - doublon : sha256 du texte normalise OU URL canonique deja vus (index + sources du corpus) ;
  - blocs {id,page,source,text,theme,annee,source_type} ; theme borne au canon des 13 (Haiku, defaut vision-generale).
Ecrit backend/corpus/<slug>.json (.bak horodate), recalcule bilan.json, journalise, et trace CHAQUE decision
dans backend/qg/decisions.jsonl. Bibliotheque standard seule. Usage : qg_ingerer.py [--racine DIR] [--domaines F]"""
import argparse, fcntl, hashlib, json, os, re, subprocess, sys, tempfile, time, unicodedata
import urllib.error, urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit

THEMES = ["economie-travail", "ecologie-energie", "social-sante", "europe-international", "institutions",
          "education", "securite-protection", "agriculture", "culture-numerique", "immigration",
          "services-publics", "logement", "vision-generale"]
AGREGATEURS = ("monvote2027", "votons-2027", "presitracker", "wikipedia.org", "vie-publique.fr")
MIN_CARS = 400
MAX_OCTETS = 8 * 1024 * 1024
BLOC_CARS = 1500
MAX_ESSAIS = 3
RE_URL = re.compile(r"https?://[^\s)»,]+")
FINAUX = ("accepte", "refuse", "doublon")


def lire_json(p, defaut):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return defaut


def hote(url):
    h = (urlsplit(url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def dom_match(h, domaines):
    h = h.lower().removeprefix("www.")
    return any(h == d or h.endswith("." + d) for d in domaines)


def est_agregateur(h):
    return any(a in h for a in AGREGATEURS)


def url_canonique(url):
    s = urlsplit(url.strip())
    q = sorted((k, v) for k, v in parse_qsl(s.query) if not k.lower().startswith("utm_"))
    return hote(url) + (s.path.rstrip("/") or "") + ("?" + urlencode(q) if q else "")


def normaliser(texte):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", texte)).strip().lower()


class _Texte(HTMLParser):
    SKIP = {"script", "style", "nav", "header", "footer", "noscript", "svg", "form"}
    BLOC = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "tr", "ul", "ol"}

    def __init__(self):
        HTMLParser.__init__(self)
        self.profondeur = 0
        self.morceaux = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.profondeur += 1
        elif tag in self.BLOC:
            self.morceaux.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.profondeur:
            self.profondeur -= 1
        elif tag in self.BLOC:
            self.morceaux.append("\n")

    def handle_data(self, d):
        if not self.profondeur:
            self.morceaux.append(d)


def html_vers_pages(octets):
    p = _Texte()
    p.feed(octets.decode("utf-8", errors="replace"))
    lignes = [re.sub(r"[ \t\r\f\v]+", " ", l).strip() for l in "".join(p.morceaux).split("\n")]
    return ["\n".join(l for l in lignes if l)]


def texte_pdf(octets):
    """liste de pages (pdftotext) ; [] si l'outil manque ou echoue."""
    with tempfile.TemporaryDirectory() as bac:
        f = Path(bac) / "d.pdf"
        f.write_bytes(octets)
        try:
            r = subprocess.run(["pdftotext", "-enc", "UTF-8", str(f), "-"], capture_output=True, timeout=120)
        except (OSError, subprocess.TimeoutExpired):
            return []
    if r.returncode != 0:
        return []
    return [p.strip() for p in r.stdout.decode("utf-8", errors="replace").split("\f") if p.strip()]


class _Redir(urllib.request.HTTPRedirectHandler):
    def __init__(self, doms):
        self.doms = doms

    def redirect_request(self, req, fp, code, msg, hdrs, newurl):
        if not dom_match(hote(newurl), self.doms):
            raise urllib.error.URLError("redirection hors domaine officiel : " + hote(newurl))
        return urllib.request.HTTPRedirectHandler.redirect_request(self, req, fp, code, msg, hdrs, newurl)


def telecharger(url, doms):
    op = urllib.request.build_opener(_Redir(doms))
    req = urllib.request.Request(url, headers={"User-Agent": "demandezleur-qg-ingerer/1.0 (+https://demandezleur.fr)"})
    with op.open(req, timeout=30) as r:
        corps = r.read(MAX_OCTETS + 1)
        return corps, (r.headers.get("Content-Type") or "").lower()


def decouper(pages):
    """[(page, texte)] blocs <= BLOC_CARS caracteres, coupes aux paragraphes."""
    out = []
    for n, page in enumerate(pages, 1):
        tampon = ""
        for para in [p.strip() for p in page.split("\n") if p.strip()]:
            while len(para) > BLOC_CARS:
                coupe = para.rfind(" ", 0, BLOC_CARS) or BLOC_CARS
                out.append((n, para[:coupe].strip()))
                para = para[coupe:].strip()
            if tampon and len(tampon) + len(para) + 1 > BLOC_CARS:
                out.append((n, tampon))
                tampon = ""
            tampon = (tampon + " " + para).strip()
        if tampon:
            out.append((n, tampon))
    return out


def classer_theme(texte, mapping):
    """-> (theme, defaut) ; sortie TOUJOURS bornee au canon des 13."""
    fixe = os.environ.get("QG_THEME_FIXE")
    if fixe in THEMES:
        return fixe, False
    cle = os.environ.get("ANTHROPIC_API_KEY", "")
    if not cle:
        return "vision-generale", True
    corps = {"model": os.environ.get("QG_MODELE", "claude-haiku-5-5"), "max_tokens": 20,
             "system": "Tu ranges un extrait de programme politique dans UN theme. Reponds par le seul identifiant, parmi : "
                       + ", ".join(THEMES),
             "messages": [{"role": "user", "content": texte[:1800]}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(corps).encode("utf-8"),
                                 headers={"x-api-key": cle, "anthropic-version": "2023-06-01",
                                          "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            rep = json.loads(r.read().decode("utf-8"))
        brut = "".join(c.get("text", "") for c in rep.get("content", [])).strip().lower()
    except Exception:
        return "vision-generale", True
    if brut in THEMES:
        return brut, False
    if brut in mapping and mapping[brut] in THEMES:
        return mapping[brut], False
    for t in THEMES:
        if t in brut:
            return t, False
    return "vision-generale", True


def trace(racine, rec):
    rec = dict(rec, ts=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    with open(racine / "backend/qg/decisions.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def ecrire_atomique(chemin, objet, ts):
    chemin = Path(chemin)
    if chemin.exists():
        bak = chemin.with_name(chemin.name + ".bak-qg-" + ts)
        bak.write_bytes(chemin.read_bytes())
    tmp = chemin.with_name(chemin.name + ".tmp-qg")
    tmp.write_text(json.dumps(objet, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o644)
    os.replace(tmp, chemin)


def examiner(racine, depot, slug_dossier, domaines, essais):
    """-> (decision, motif, details) pour un depot ; decision ajourne = a retenter plus tard."""
    meta = lire_json(depot, None)
    if not isinstance(meta, dict):
        return "refuse", "depot-illisible", {}
    public = slug_dossier == "_public"
    slug = str(meta.get("candidat", "")).strip() if public else slug_dossier
    if slug not in domaines:
        return "refuse", "candidat-inconnu", {"candidat": slug}
    doms = domaines[slug]
    url = str(meta.get("url") or "").strip()
    fichier = meta.get("fichier")
    pdf = None if public else fichier
    det = {"slug": slug, "url": url or None, "fichier": fichier}
    if url and not re.match(r"https?://", url):
        return "refuse", "url-invalide", det
    if not pdf:
        if not url:
            return "refuse", ("pdf-public-sans-jeton" if fichier else "ni-url-ni-pdf"), det
        h = hote(url)
        if est_agregateur(h):
            return "refuse", "agregateur", det
        if not dom_match(h, doms):
            return "refuse", "url-hors-domaine-officiel", det
    try:
        if pdf:
            octets = (depot.parent / pdf).read_bytes()
            pages = texte_pdf(octets)
            if not pages:
                return ("ajourne" if essais < MAX_ESSAIS else "refuse"), "pdf-illisible-ou-pdftotext-absent", det
            det["source_ref"] = "pdf:" + str(meta.get("fichier_sha256") or hashlib.sha256(octets).hexdigest())
            det["libelle"] = str(meta.get("titre") or "Document PDF de l'equipe")
        else:
            octets, ctype = telecharger(url, doms)
            if len(octets) > MAX_OCTETS:
                return "refuse", "document-trop-gros", det
            pages = texte_pdf(octets) if ("pdf" in ctype or octets.startswith(b"%PDF-")) else html_vers_pages(octets)
            det["source_ref"] = "url:" + url_canonique(url)
            det["libelle"] = str(meta.get("titre") or url)
    except urllib.error.HTTPError as e:
        return ("refuse" if e.code < 500 else ("ajourne" if essais < MAX_ESSAIS else "refuse")), "http-%d" % e.code, det
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        return ("ajourne" if essais < MAX_ESSAIS else "refuse"), "injoignable: " + str(e)[:120], det
    texte = "\n".join(pages)
    if len(texte.strip()) < MIN_CARS:
        return "refuse", "texte-insuffisant", det
    det["sha"] = hashlib.sha256(normaliser(texte).encode("utf-8")).hexdigest()
    idx = lire_json(racine / "backend/qg/ingere_index.json", {}).get(slug, {})
    corpus = lire_json(racine / ("backend/corpus/%s.json" % slug), [])
    vus_urls = {url_canonique(u) for b in corpus for u in RE_URL.findall(str(b.get("source", "")))}
    if det["sha"] in idx.get("sha", []) or det["source_ref"] in idx.get("refs", []) \
            or (url and url_canonique(url) in vus_urls):
        return "doublon", "deja-au-corpus", det
    det["pages"] = pages
    return "accepte", "valide", det


def ingerer(racine, depot, det, mapping, ts):
    slug = det["slug"]
    chemin = racine / ("backend/corpus/%s.json" % slug)
    corpus = lire_json(chemin, [])
    prochain = max([b.get("id", -1) for b in corpus if isinstance(b.get("id"), int)] + [-1]) + 1
    annee = int(ts[:4])
    ref = det["url"] or ""
    source = "%s — %s (equipe officielle, depose le %s)" % (det["libelle"], ref or "document PDF", ts[:8])
    defauts = 0
    for n, (page, texte) in enumerate(decouper(det["pages"])):
        theme, defaut = classer_theme(texte, mapping)
        defauts += 1 if defaut else 0
        corpus.append({"id": prochain + n, "page": page, "source": source, "text": texte, "theme": theme,
                       "annee": annee, "source_type": "equipe-officielle"})
    ecrire_atomique(chemin, corpus, ts)
    idxp = racine / "backend/qg/ingere_index.json"
    idx = lire_json(idxp, {})
    e = idx.setdefault(slug, {"sha": [], "refs": []})
    e["sha"].append(det["sha"])
    e["refs"].append(det["source_ref"])
    ecrire_atomique(idxp, idx, ts)
    return len(decouper(det["pages"])), defauts


def principal(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--racine", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--domaines", default=None)
    ap.add_argument("--limite", type=int, default=20)
    a = ap.parse_args(argv)
    racine = Path(a.racine)
    (racine / "backend/qg").mkdir(parents=True, exist_ok=True)
    verrou = open(racine / "backend/qg/.ingerer.lock", "w")
    try:
        fcntl.flock(verrou, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("INGESTION_DEJA_EN_COURS")
        return 0
    domaines = lire_json(a.domaines or racine / "backend/qg/domaines_officiels.json", {}).get("domaines", {})
    mapping = {k: v for k, v in lire_json(racine / "tools/reetiquetage_themes.json", {}).items() if not k.startswith("_")}
    deja, essais = set(), {}
    dec = racine / "backend/qg/decisions.jsonl"
    if dec.exists():
        for l in dec.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(l)
            except ValueError:
                continue
            if r.get("decision") in FINAUX or (r.get("decision") == "refuse" and r.get("final")):
                deja.add(r.get("depot"))
            elif r.get("decision") == "ajourne":
                essais[r.get("depot")] = essais.get(r.get("depot"), 0) + 1
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    nb = {"accepte": 0, "refuse": 0, "doublon": 0, "ajourne": 0}
    touches = False
    traites = 0
    for depot in sorted((racine / "backend/qg/depots").glob("*/*.json")):
        rel = str(depot.relative_to(racine / "backend/qg/depots"))
        if rel in deja or traites >= a.limite:
            continue
        traites += 1
        d, motif, det = examiner(racine, depot, depot.parent.name, domaines, essais.get(rel, 0))
        nbl = 0
        if d == "accepte":
            nbl, defauts = ingerer(racine, depot, det, mapping, ts)
            touches = True
            det["themes_par_defaut"] = defauts
        nb[d] += 1
        trace(racine, {"depot": rel, "decision": d, "motif": motif, "candidat": det.get("slug"),
                       "url": det.get("url"), "blocs": nbl, "sha": det.get("sha")})
    if touches:
        bilan = racine / "backend/corpus/bilan.json"
        if bilan.exists():
            (bilan.with_name("bilan.json.bak-qg-" + ts)).write_bytes(bilan.read_bytes())
        r = subprocess.run([sys.executable, str(racine / "tools/bilan_corpus.py"),
                            "--domaines", a.domaines or str(racine / "backend/qg/domaines_officiels.json"),
                            "--candidats", str(racine / "backend/candidats.json"),
                            "--corpus", str(racine / "backend/corpus"), "--out", str(bilan)],
                           capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            print("BILAN_ECHEC", r.stderr[-300:])
            return 1
        journal = racine / "JOURNAL_MAIN.md"
        if journal.exists():
            with open(journal, "a", encoding="utf-8") as f:
                f.write("%s qg_ingerer : %d accepte(s), %d refuse(s), %d doublon(s) — corpus + bilan recalcules (bak .bak-qg-%s)\n"
                        % (ts, nb["accepte"], nb["refuse"], nb["doublon"], ts))
    print("INGESTION_FIN", json.dumps(nb))
    return 0


if __name__ == "__main__":
    sys.exit(principal())
