#!/usr/bin/env python3
"""Ajoute `themes` (3-6 thèmes politiques) à chaque fait/grief du dossier qui n'en a pas — une passe modèle par fichier."""
import asyncio, json, sys
from pathlib import Path
R = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(R / "backend"))
import llm
D = R / "backend/dossiers"
PROMPT = """Pour chaque élément ci-dessous (fait ou reproche politique), donne 3 à 6 THÈMES de débat auxquels il peut légitimement servir (mots simples : probité, justice, argent public, immigration, sécurité, police, liberté de la presse, écologie, nucléaire, économie, travail, retraites, institutions, Europe, laïcité, terrorisme, santé, école, logement…). Réponds en JSON : {"themes": {"<id>": ["...", "..."]}}\n\n"""
async def main():
    for p in sorted(list((D / "faits").glob("*.json")) + list((D / "rapports").glob("*.json"))):
        d = json.loads(p.read_text(encoding="utf-8")); items = d.get("entrees") or d.get("griefs") or []
        todo = [e for e in items if not e.get("themes")]
        if not todo: continue
        txt = "\n".join(f"- {e['id']} : {e.get('fait') or (e.get('grief') + ' — ' + ' / '.join(x.get('verbatim','') for x in (e.get('exemples') or [])[:2]))}" for e in todo)
        rep = await llm.completer_texte([{"role": "user", "content": PROMPT + txt}], cle_demo=("themes", p.stem), max_tokens=800, temperature=0, extra={"response_format": {"type": "json_object"}})
        try: themes = json.loads(rep[rep.find("{"): rep.rfind("}") + 1]).get("themes", {})
        except Exception: themes = {}
        for e in todo: e["themes"] = [t.strip().lower() for t in themes.get(e["id"], [])][:6]
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8"); print(p.name, len(todo), "thémés")
asyncio.run(main())
