#!/usr/bin/env python3
"""Régénère la section « prompts » de content/transparence/index.md depuis backend/prompts/**.
Usage : python3 tools/transparence_sync.py"""
import re
from pathlib import Path
R = Path(__file__).resolve().parent.parent
PAGE = R / "hugo-src/content/transparence/index.md"
PROMPTS = R / "backend/prompts"
ORDRE = [("base.txt", "Question à un candidat (chat)"), ("debat/base_ouverture.txt", "Débat — ouverture"), ("debat/base_tour_suivant.txt", "Débat — tour suivant"),
         ("debat/base_interpelle.txt", "Débat — candidat interpellé"), ("debat/base_reaction.txt", "Débat — réaction à une interpellation"),
         ("debat/consigne_arene.txt", "Arène — consigne"), ("debat/juge_arene.txt", "Arène — juge (garde-fou)"), ("debat/theme_parlement.txt", "Assemblée — dérivation d'un thème lisible")]
TONS = sorted(PROMPTS.glob("ton_*.txt"))
parts = []
for rel, titre in ORDRE:
    p = PROMPTS / rel
    if p.exists():
        parts.append(f"### {titre}\n`{rel}`\n\n```text\n{p.read_text(encoding='utf-8').strip()}\n```\n")
parts.append("### Tons par famille politique\n" + "\n".join(f"\n`{t.name}`\n\n```text\n{t.read_text(encoding='utf-8').strip()}\n```" for t in TONS) + "\n")
s = PAGE.read_text(encoding="utf-8")
s = re.sub(r"<!-- prompts:debut -->.*?<!-- prompts:fin -->", "<!-- prompts:debut -->\n" + "\n".join(parts) + "<!-- prompts:fin -->", s, flags=re.S)
PAGE.write_text(s, encoding="utf-8")
print(f"transparence : {len(parts)} sections, {len(s)} caractères")
