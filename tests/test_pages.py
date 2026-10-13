"""Tests des pages de l'application.

Chaque fonction qui commence par "test_" est un test. Une ligne
"assert ..." vérifie qu'une condition est vraie : si elle est fausse,
le test échoue et pytest affiche pourquoi.
"""

import sqlite3


def ajouter(client, nom):
    """Envoie le formulaire comme le ferait un utilisateur."""
    return client.post("/bonjour", data={"nom": nom})


def test_accueil_s_affiche(client):
    reponse = client.get("/")
    assert reponse.status_code == 200
    assert "Bienvenue" in reponse.text


def test_page_inexistante_renvoie_404(client):
    assert client.get("/cette-page-n-existe-pas").status_code == 404


def test_page_bonjour_vide_au_depart(client):
    reponse = client.get("/bonjour")
    assert reponse.status_code == 200
    assert "Aucun nom pour l'instant." in reponse.text


def test_envoi_du_formulaire_redirige(client):
    reponse = ajouter(client, "Ben")
    # 302 = redirection, pour que F5 ne renvoie pas le formulaire.
    assert reponse.status_code == 302
    assert reponse.headers["Location"] == "/bonjour?nom=Ben"


def test_nom_ajoute_apparait_dans_la_liste(client):
    # follow_redirects=True suit la redirection, comme un navigateur.
    reponse = client.post(
        "/bonjour", data={"nom": "Ben"}, follow_redirects=True
    )
    assert "Bonjour Ben !" in reponse.text
    assert "Noms enregistrés (1)" in reponse.text


def test_nom_est_bien_enregistre_dans_la_base(client, base_de_test):
    ajouter(client, "Alice")
    lignes = sqlite3.connect(base_de_test).execute("SELECT nom FROM noms").fetchall()
    assert lignes == [("Alice",)]


def test_espaces_autour_du_nom_sont_retires(client, base_de_test):
    ajouter(client, "  Alice  ")
    lignes = sqlite3.connect(base_de_test).execute("SELECT nom FROM noms").fetchall()
    assert lignes == [("Alice",)]


def test_nom_vide_n_est_pas_enregistre(client):
    ajouter(client, "")
    ajouter(client, "   ")
    assert "Aucun nom pour l'instant." in client.get("/bonjour").text


def test_noms_les_plus_recents_en_premier(client):
    ajouter(client, "Premier")
    ajouter(client, "Second")
    page = client.get("/bonjour").text
    assert page.index("Second") < page.index("Premier")


def test_injection_sql_est_sans_effet(client, base_de_test):
    nom_piege = "Alice'); DROP TABLE noms;--"
    ajouter(client, nom_piege)
    # La table existe toujours et contient le texte tel quel.
    lignes = sqlite3.connect(base_de_test).execute("SELECT nom FROM noms").fetchall()
    assert lignes == [(nom_piege,)]


def test_html_saisi_n_est_pas_execute(client):
    # Un utilisateur malveillant pourrait essayer d'injecter du JavaScript.
    ajouter(client, "<script>alert(1)</script>")
    page = client.get("/bonjour").text
    # Flask le transforme en texte inoffensif (&lt;script&gt;).
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page
