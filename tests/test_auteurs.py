"""Tests des auteurs : chaque nom a un propriétaire, seul à pouvoir le
modifier ou le supprimer."""

from webapp.modeles import Nom, Utilisateur, db


def test_l_ajout_enregistre_l_auteur(client, app, id_testeur):
    client.post("/bonjour", data={"nom": "Alice"})
    with app.app_context():
        nom = db.session.scalar(db.select(Nom))
        assert nom.auteur_id == id_testeur
        # La relation donne directement l'objet Utilisateur.
        assert nom.auteur.nom_utilisateur == "testeur"


def test_un_utilisateur_retrouve_ses_noms(client, app, id_testeur):
    client.post("/bonjour", data={"nom": "Alice"})
    client.post("/bonjour", data={"nom": "Bob"})
    with app.app_context():
        utilisateur = db.session.get(Utilisateur, id_testeur)
        assert sorted(nom.nom for nom in utilisateur.noms) == ["Alice", "Bob"]


def test_la_liste_affiche_l_auteur(visiteur, id_ben):
    assert "par testeur" in visiteur.get("/bonjour").text


def test_l_auteur_voit_les_boutons(client, id_ben):
    page = client.get("/bonjour").text
    assert f"/noms/{id_ben}/modifier" in page
    assert f"/noms/{id_ben}/supprimer" in page


def test_un_autre_utilisateur_ne_voit_pas_les_boutons(client_autre, id_ben):
    page = client_autre.get("/bonjour").text
    assert "Ben" in page
    assert f"/noms/{id_ben}/modifier" not in page
    assert f"/noms/{id_ben}/supprimer" not in page


def test_un_autre_utilisateur_ne_peut_pas_modifier(client_autre, id_ben, lire_noms):
    # Même en tapant l'adresse lui-même : 403 = accès interdit.
    assert client_autre.get(f"/noms/{id_ben}/modifier").status_code == 403
    reponse = client_autre.post(f"/noms/{id_ben}/modifier", data={"nom": "Pirate"})
    assert reponse.status_code == 403
    assert "Seul l'auteur d'un nom peut le modifier" in reponse.text
    assert lire_noms() == ["Ben"]


def test_un_autre_utilisateur_ne_peut_pas_supprimer(client_autre, id_ben, lire_noms):
    assert client_autre.post(f"/noms/{id_ben}/supprimer").status_code == 403
    assert lire_noms() == ["Ben"]


def test_chacun_gere_ses_propres_noms(client, client_autre, id_ben, lire_noms):
    client_autre.post("/bonjour", data={"nom": "Nom de autre"})
    page = client_autre.get("/bonjour").text
    # "autre" voit les boutons sur son nom, pas sur celui de testeur.
    assert page.count("Supprimer</button>") == 1

    # testeur supprime son nom ; celui de "autre" reste.
    client.post(f"/noms/{id_ben}/supprimer")
    assert lire_noms() == ["Nom de autre"]
