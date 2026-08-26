# dossiers_admin.py — pupitre de validation du dossier (Lionel) : http://127.0.0.1:8001/admin/dossiers
# Accès : depuis 127.0.0.1, ou avec ?jeton=<ADMIN_BYPASS_TOKEN>. Chaque décision est journalisée (JOURNAL.jsonl).
import html
import json
from datetime import datetime
from pathlib import Path

R = Path(__file__).resolve().parent / "dossiers"
FAITS, RAPPORTS, JOURNAL = R / "faits", R / "rapports", R / "JOURNAL.jsonl"
STATUTS = ("valide", "refuse", "a_valider")


def _entrees():
    for p in sorted(FAITS.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        for e in d.get("entrees", []):
            yield p, d, e, "fait"
    for p in sorted(RAPPORTS.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        for g in d.get("griefs", []):
            yield p, d, g, "grief"


def decider(eid: str, statut: str, motif: str = "") -> bool:
    if statut not in STATUTS:
        return False
    for p, d, e, k in _entrees():
        if e.get("id") == eid:
            e["statut"], e["decide_le"], e["motif"] = statut, datetime.now().isoformat(timespec="minutes"), motif
            p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            resume = f"{d.get('candidat_id') or (d.get('de') + '→' + d.get('vers'))} : {(e.get('fait') or e.get('grief'))[:140]}"
            with open(JOURNAL, "a", encoding="utf-8") as j:
                j.write(json.dumps({"quand": e["decide_le"], "id": eid, "type": k, "statut": statut, "motif": motif, "resume": resume, "par": "pupitre"}, ensure_ascii=False) + "\n")
            return True
    return False


def _carte(d, e, k, jeton):
    h = html.escape
    if k == "fait":
        titre = f"{d['candidat_id']} · {e.get('classe', '')} · {e.get('date', '')}"
        corps = f"<p class='fait'>{h(e.get('fait', ''))}</p><p class='meta'>{h(e.get('instance', ''))}</p>"
        srcs = "".join(f"<li><a href='{h(s.get('url', ''))}' target='_blank' rel='noopener'>{h(s.get('media') or s.get('url', ''))}</a> {h(s.get('titre', '')[:90])}</li>" for s in e.get("sources", []))
        notes = h(e.get("notes", ""))
    else:
        titre = f"{d['de']} → {d['vers']} · registre {d.get('registre', '')}"
        corps = f"<p class='fait'>{h(e.get('grief', ''))}</p>" + "".join(
            f"<blockquote>« {h(x.get('verbatim', ''))} »<br><span class='meta'>{h(x.get('auteur', ''))}, {h(x.get('date', ''))} · <a href='{h(x.get('source_url', ''))}' target='_blank' rel='noopener'>{h(x.get('media', 'source'))}</a> ({x.get('n_sources', 1)} source{'s' if x.get('n_sources', 1) > 1 else ''})</span></blockquote>"
            for x in e.get("exemples", []))
        srcs, notes = "", ""
    q = f"&jeton={h(jeton)}" if jeton else ""
    return f"""<article class='carte'>
  <h3>{h(titre)}</h3>{corps}
  {('<ul class=sources>' + srcs + '</ul>') if srcs else ''}
  {('<p class=notes>' + notes + '</p>') if notes else ''}
  <form method='post' action='/admin/dossiers/decider?{q.lstrip('&')}' class='actions'>
    <input type='hidden' name='id' value='{h(e['id'])}'>
    <input type='text' name='motif' placeholder='motif (facultatif)'>
    <button name='statut' value='valide' class='ok'>✓ Valider</button>
    <button name='statut' value='refuse' class='non'>✗ Refuser</button>
  </form>
</article>"""


def _budget_html() -> str:
    try:
        import budget, rate_limiter
        e = budget.etat(); pct = int(100 * e["ratio"]); coul = {"normal": "#3fa66b", "degrade": "#f2a93b", "ferme": "#e53946", "ferme_total": "#e53946"}[e["palier"]]
        details = " · ".join(f"{k} {v['eur']:.3f} € ({v['appels']})" for k, v in sorted(e["par_usage"].items(), key=lambda kv: -kv[1]["eur"]))
        return (f"<div class='budget' style='border-left:4px solid {coul};background:rgba(255,255,255,.04);padding:10px 14px;border-radius:8px;margin:12px 0 4px;font-size:14px'>"
                f"<strong>Budget IA du jour</strong> : {e['eur']:.3f} € / {e['plafond_eur']:.2f} € ({pct} %) — palier <strong style='color:{coul}'>{e['palier']}</strong>"
                f"{' · heure de pointe (tarif ×2)' if rate_limiter.en_pointe() else ''} · {e['appels']} appels · cache {e['hit']:,} hit / {e['miss']:,} miss / {e['out']:,} sortie"
                f"<br><span class='meta'>{html.escape(details) or 'aucun appel'}</span></div>")
    except Exception as ex:
        return f"<p class='meta'>budget indisponible : {html.escape(str(ex))}</p>"


def page(jeton: str = "") -> str:
    attente = [(d, e, k) for p, d, e, k in _entrees() if e.get("statut") == "a_valider"]
    recents = []
    if JOURNAL.exists():
        recents = [json.loads(l) for l in JOURNAL.read_text(encoding="utf-8").splitlines() if l.strip()][-12:][::-1]
    h = html.escape
    q = f"?jeton={h(jeton)}" if jeton else ""
    cartes = "".join(_carte(d, e, k, jeton) for d, e, k in attente) or "<p class='vide'>Rien à valider. 🎉</p>"
    journal = "".join(f"<li><span class='meta'>{h(r['quand'])}</span> <strong class='{h(r['statut'])}'>{h(r['statut'])}</strong> {h(r['resume'])}"
                      f"<form method='post' action='/admin/dossiers/decider{q}' class='inline'><input type='hidden' name='id' value='{h(r['id'])}'><input type='hidden' name='statut' value='a_valider'><button class='annuler'>annuler</button></form></li>" for r in recents)
    return f"""<!doctype html><html lang='fr'><head><meta charset='utf-8'><title>Dossier de l'Arène — validation</title>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<style>
body{{margin:0;background:#0a1428;color:#f4f6fb;font:16px/1.55 Inter,system-ui,sans-serif}} .c{{max-width:960px;margin:0 auto;padding:24px 16px 64px}}
h1{{font-size:28px;margin:0 0 4px}} h2{{font-size:20px;margin:40px 0 12px}} h3{{font-size:15px;margin:0 0 8px;color:#ff5f6b;font-weight:600;letter-spacing:.02em}}
.meta{{color:rgba(244,246,251,.55);font-size:14px}} .carte{{background:#111d3a;border:1px solid rgba(255,255,255,.1);border-radius:12px;padding:16px 18px;margin-bottom:14px}}
.fait{{margin:0 0 6px;font-size:17px}} blockquote{{margin:8px 0;padding:8px 12px;border-left:3px solid #8b7bd8;background:rgba(255,255,255,.03)}}
.sources{{margin:6px 0;padding-left:18px;font-size:14px}} .sources a{{color:#ff5f6b}} .notes{{font-size:13px;color:rgba(244,246,251,.55);margin:6px 0 0}}
.actions{{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap}} .actions input[type=text]{{flex:1;min-width:200px;padding:8px 10px;border-radius:6px;border:1px solid rgba(255,255,255,.2);background:#182648;color:#f4f6fb}}
button{{padding:9px 16px;border-radius:6px;border:0;font-weight:600;cursor:pointer;font:inherit}} .ok{{background:#3fa66b;color:#fff}} .non{{background:#e53946;color:#fff}} .annuler{{background:transparent;color:rgba(244,246,251,.55);text-decoration:underline;padding:0 6px}}
.inline{{display:inline}} ul.journal{{list-style:none;padding:0}} ul.journal li{{padding:6px 0;border-bottom:1px solid rgba(255,255,255,.08);font-size:14px}} .valide{{color:#3fa66b}} .refuse{{color:#ff5f6b}} .a_valider{{color:#f2a93b}} .vide{{color:#3fa66b;font-size:20px}}
.bandeau{{background:rgba(242,169,59,.12);border-left:4px solid #f2a93b;padding:10px 14px;border-radius:8px;margin:16px 0 24px;font-size:14px}}
</style></head><body><div class='c'>
<h1>Dossier de l'Arène — à valider</h1>
{_budget_html()}
<p class='meta'>{len(attente)} entrée(s) en attente. Valider = servie dans l'Arène (avec sa qualification exacte). Refuser = jamais servie. Tout est journalisé et réversible.</p>
<div class='bandeau'>Règle : un fait se valide s'il est établi et sourcé ; une procédure en cours se valide seulement si sa qualification est exacte (« en appel », « mis en examen ») ; un reproche se valide comme <em>reproche documenté</em> (ce que le camp dit), jamais comme fait. Vie privée, santé, famille : refuser.</div>
{cartes}
<h2>Décisions récentes</h2><ul class='journal'>{journal or '<li class=meta>aucune</li>'}</ul>
</div></body></html>"""
