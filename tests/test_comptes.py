"""Tests des comptes utilisateurs et des protections de sécurité."""

import re

import pytest

from webapp import create_app
from webapp.modeles import Utilisateur, db

from conftest import MOT_DE_PASSE_TEST, NOM_UTILISATEUR_TEST


def inscrire(client, nom_utilisateur="nouveau", mot_de_passe="motdepasse123", confirmation=None):
    return client.post(
        "/inscription",
        data={
            "nom_utilisateur": nom_utilisateur,
            "mot_de_passe": mot_de_passe,
            "confirmation": mot_de_passe if confirmation is None else confirmation,
        },
    )


def connecter(client, nom_utilisateur=NOM_UTILISATEUR_TEST, mot_de_passe=MOT_DE_PASSE_TEST, adresse="/connexion"):
    return client.post(
        adresse, data={"nom_utilisateur": nom_utilisateur, "mot_de_passe": mot_de_passe}
    )


# --- Inscription ------------------------------------------------------------------


def test_inscription_cree_le_compte_et_connecte(visiteur, app):
    reponse = inscrire(visiteur)
    assert reponse.status_code == 302
    page = visiteur.get("/bonjour").text
    assert "Bienvenue nouveau, votre compte est créé." in page
    assert "Connecté : <strong>nouveau</strong>" in page


def test_le_mot_de_passe_n_est_pas_stocke_en_clair(visiteur, app):
    inscrire(visiteur, mot_de_passe="motdepasse123")
    with app.app_context():
        utilisateur = db.session.scalar(db.select(Utilisateur))
        assert utilisateur.mot_de_passe_hash != "motdepasse123"
        assert "motdepasse123" not in utilisateur.mot_de_passe_hash
        assert utilisateur.verifier_mot_de_passe("motdepasse123")
        assert not utilisateur.verifier_mot_de_passe("mauvais")


def test_nom_utilisateur_deja_pris_est_refuse(visiteur, creer_utilisateur):
    creer_utilisateur("ben")
    # "Ben" et "ben" désignent le même compte.
    reponse = inscrire(visiteur, nom_utilisateur="Ben")
    assert reponse.status_code == 400
    assert "Ce nom d&#39;utilisateur est déjà pris." in reponse.text


@pytest.mark.parametrize(
    "nom_utilisateur",
    ["ab", "a" * 31, "avec espace", "accentué", "<script>"],
)
def test_nom_utilisateur_invalide_est_refuse(visiteur, nom_utilisateur):
    # parametrize : ce test est lancé une fois pour chaque valeur ci-dessus.
    reponse = inscrire(visiteur, nom_utilisateur=nom_utilisateur)
    assert reponse.status_code == 400
    assert "De 3 à 30 caractères" in reponse.text


def test_mot_de_passe_trop_court_est_refuse(visiteur):
    reponse = inscrire(visiteur, mot_de_passe="court")
    assert reponse.status_code == 400
    assert "au moins 8 caractères" in reponse.text


def test_confirmation_differente_est_refusee(visiteur):
    reponse = inscrire(visiteur, mot_de_passe="motdepasse123", confirmation="autrechose")
    assert reponse.status_code == 400
    assert "ne correspondent pas" in reponse.text


# --- Connexion et déconnexion -------------------------------------------------------


def test_connexion_avec_bon_mot_de_passe(visiteur, creer_utilisateur):
    creer_utilisateur()
    reponse = connecter(visiteur)
    assert reponse.status_code == 302
    assert "Connecté : <strong>testeur</strong>" in visiteur.get("/").text


def test_connexion_avec_mauvais_mot_de_passe(visiteur, creer_utilisateur):
    creer_utilisateur()
    reponse = connecter(visiteur, mot_de_passe="mauvais")
    assert reponse.status_code == 400
    assert "Nom d&#39;utilisateur ou mot de passe incorrect." in reponse.text


def test_meme_message_si_le_compte_n_existe_pas(visiteur):
    # On ne doit pas pouvoir deviner quels comptes existent.
    reponse = connecter(visiteur, nom_utilisateur="inconnu")
    assert reponse.status_code == 400
    assert "Nom d&#39;utilisateur ou mot de passe incorrect." in reponse.text


def test_deconnexion(client, lire_noms):
    reponse = client.post("/deconnexion")
    assert reponse.status_code == 302
    assert "Vous êtes déconnecté." in client.get("/").text
    # Une fois déconnecté, on ne peut plus ajouter de nom.
    client.post("/bonjour", data={"nom": "Alice"})
    assert lire_noms() == []


def test_deconnexion_par_un_simple_lien_est_refusee(client):
    assert client.get("/deconnexion").status_code == 405


# --- Pages réservées aux personnes connectées ----------------------------------------


def test_un_visiteur_voit_la_liste_mais_pas_le_formulaire(visiteur, id_ben):
    page = visiteur.get("/bonjour").text
    assert "Ben" in page
    assert 'name="nom"' not in page
    assert "Supprimer" not in page
    assert "Connectez-vous" in page


def test_un_visiteur_ne_peut_pas_ajouter_de_nom(visiteur, lire_noms):
    reponse = visiteur.post("/bonjour", data={"nom": "Alice"})
    # Il est renvoyé vers la connexion, avec la page où revenir ensuite.
    assert reponse.status_code == 302
    assert reponse.headers["Location"].startswith("/connexion?next=")
    assert lire_noms() == []


def test_un_visiteur_ne_peut_pas_modifier(visiteur, id_ben, lire_noms):
    reponse = visiteur.post(f"/noms/{id_ben}/modifier", data={"nom": "Pirate"})
    assert reponse.status_code == 302
    assert "/connexion" in reponse.headers["Location"]
    assert lire_noms() == ["Ben"]


def test_un_visiteur_ne_peut_pas_supprimer(visiteur, id_ben, lire_noms):
    reponse = visiteur.post(f"/noms/{id_ben}/supprimer")
    assert reponse.status_code == 302
    assert lire_noms() == ["Ben"]


def test_retour_a_la_page_demandee_apres_connexion(visiteur, creer_utilisateur, id_ben):
    creer_utilisateur()
    reponse = visiteur.get(f"/noms/{id_ben}/modifier")
    adresse_connexion = reponse.headers["Location"]
    reponse = connecter(visiteur, adresse=adresse_connexion)
    assert reponse.headers["Location"] == f"/noms/{id_ben}/modifier"


@pytest.mark.parametrize(
    "suivante", ["https://site-pirate.com", "//site-pirate.com", "/\\site-pirate.com"]
)
def test_pas_de_redirection_vers_un_autre_site(visiteur, creer_utilisateur, suivante):
    creer_utilisateur()
    reponse = connecter(visiteur, adresse=f"/connexion?next={suivante}")
    assert reponse.headers["Location"] == "/bonjour"


# --- Protection CSRF -----------------------------------------------------------------


def lire_jeton_csrf(page):
    return re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)


def test_formulaire_sans_jeton_csrf_est_refuse(client, app, lire_noms):
    app.config["WTF_CSRF_ENABLED"] = True
    reponse = client.post("/bonjour", data={"nom": "Alice"})
    assert reponse.status_code == 400
    assert lire_noms() == []


def test_formulaire_avec_mauvais_jeton_csrf_est_refuse(client, app, lire_noms):
    app.config["WTF_CSRF_ENABLED"] = True
    reponse = client.post("/bonjour", data={"nom": "Alice", "csrf_token": "faux"})
    assert reponse.status_code == 400
    assert lire_noms() == []


def test_formulaire_avec_jeton_csrf_est_accepte(client, app, lire_noms):
    app.config["WTF_CSRF_ENABLED"] = True
    jeton = lire_jeton_csrf(client.get("/bonjour").text)
    reponse = client.post("/bonjour", data={"nom": "Alice", "csrf_token": jeton})
    assert reponse.status_code == 302
    assert lire_noms() == ["Alice"]


# --- Configuration --------------------------------------------------------------------


def test_l_application_refuse_de_demarrer_sans_secret_key(tmp_path, monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SECRET_KEY manquante"):
        create_app({"SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}"})
