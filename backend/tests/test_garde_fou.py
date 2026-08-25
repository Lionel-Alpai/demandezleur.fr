# Tests déterministes du garde-fou Arène (sans réseau). Lancer : venv/bin/python -m pytest backend/tests -q
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import garde_fou as g

LE_PEN = {"id": "marine-le-pen", "nom": "Marine Le Pen"}
PHILIPPE = {"id": "edouard-philippe", "nom": "Édouard Philippe"}
ATTAL = {"id": "gabriel-attal", "nom": "Gabriel Attal"}
FAITS = {"marine-le-pen": {"a_gouverne": False, "depute": True},
         "edouard-philippe": {"a_gouverne": True, "depute": False},
         "gabriel-attal": {"a_gouverne": True, "depute": True}}


def test_decoupe_phrases():
    t = "Première phrase. Deuxième, avec « guillemets » ! Troisième ? « Quatrième citée. »"
    assert len(g.decouper_phrases(t)) == 4


def test_cibles_nommees_et_vous():
    advs = [LE_PEN, PHILIPPE]
    assert g.cibles_dans_phrase("Madame Le Pen, votre programme est vide.", advs) == ["marine-le-pen"]
    assert g.cibles_dans_phrase("Vous n'avez rien fait.", advs, cible_par_defaut="edouard-philippe") == ["edouard-philippe"]
    assert g.cibles_dans_phrase("La sécurité est une priorité.", advs, cible_par_defaut="edouard-philippe") == []


def test_gouvernement_prete_a_le_pen_retire():
    texte = "Madame Le Pen, votre gouvernement a laissé exploser la délinquance. Nous proposons 10 000 policiers. Qu'en dites-vous ?"
    net, rev = g.verifier_faits(texte, [LE_PEN], FAITS, cible_par_defaut="marine-le-pen")
    assert len(rev) == 1 and rev[0]["cible"] == "marine-le-pen" and rev[0]["type"] == "faits"
    assert "votre gouvernement" not in net and "10 000 policiers" in net


def test_gouvernement_de_philippe_conserve():
    texte = "Monsieur Philippe, votre gouvernement a supprimé des lits d'hôpital. Nous les rouvrirons."
    net, rev = g.verifier_faits(texte, [PHILIPPE], FAITS, cible_par_defaut="edouard-philippe")
    assert rev == [] and net == " ".join(g.decouper_phrases(texte))


def test_vous_suit_la_derniere_cible():
    texte = "Gabriel Attal parle de fermeté. Pendant que vous étiez à Matignon, rien n'a bougé. Marine Le Pen, quand vous étiez ministre, où étiez-vous ?"
    net, rev = g.verifier_faits(texte, [ATTAL, LE_PEN], FAITS)
    # Attal a gouverné : phrase 2 conservée ; Le Pen jamais ministre : phrase 3 retirée
    assert [r["cible"] for r in rev] == ["marine-le-pen"]
    assert "Matignon" in net and "ministre" not in net


def test_vote_prete_a_non_depute():
    texte = "Monsieur Philippe, vous avez voté contre ce texte. C'est votre droit."
    net, rev = g.verifier_faits(texte, [PHILIPPE], FAITS, cible_par_defaut="edouard-philippe")
    assert len(rev) == 1 and "député" in rev[0]["raison"]


def test_extraction_json_tolerante():
    assert g._extraire_json('Voici : {"affirmations": [{"phrase": "x", "ancree": false}]} merci')["affirmations"][0]["ancree"] is False
    assert g._extraire_json("pas du json") == {}


def test_retirer_phrases_appariement_souple():
    texte = "Vous avez fermé 200 commissariats dans nos campagnes. Nous, nous en ouvrirons. Combien en avez-vous créé ?"
    rev = [{"type": "juge", "phrase": "vous avez fermé 200 commissariats", "cible": "gabriel-attal", "raison": "aucune pièce"}]
    net = g._retirer_phrases(texte, rev)
    assert "commissariats dans nos campagnes" not in net and "nous en ouvrirons" in net
