"""Tests de l'adresse e-mail, du mot de passe oublié et de la page Mon compte."""

import re

import pytest
import requests

from webapp import jetons
from webapp.emails import envoyer_email
from webapp.modeles import Utilisateur, db

from conftest import ADRESSE_DU_SITE_TEST, MOT_DE_PASSE_TEST, NOM_UTILISATEUR_TEST

NOUVEAU_MOT_DE_PASSE = "nouveau-mdp-456"


def lien_dans(email):
    """Extrait le lien (http...) contenu dans le texte d'un e-mail."""
    return re.search(r"http\S+", email["texte"]).group(0)


def chemin_de(lien):
    """Transforme "http://site-de-test/page" en "/page" pour le client de test."""
    return lien.removeprefix(ADRESSE_DU_SITE_TEST)


def lire_utilisateur(app, nom_utilisateur=NOM_UTILISATEUR_TEST):
    with app.app_context():
        return db.session.scalar(db.select(Utilisateur).filter_by(nom_utilisateur=nom_utilisateur))


def connecter(client, mot_de_passe=MOT_DE_PASSE_TEST):
    return client.post(
        "/connexion",
        data={"nom_utilisateur": NOM_UTILISATEUR_TEST, "mot_de_passe": mot_de_passe},
    )


def demander_lien(client, email=f"{NOM_UTILISATEUR_TEST}@exemple.fr"):
    return client.post("/mot-de-passe-oublie", data={"email": email})


# --- Adresse e-mail à l'inscription -----------------------------------------------------


def inscrire(client, email, nom_utilisateur="nouveau"):
    return client.post(
        "/inscription",
        data={
            "nom_utilisateur": nom_utilisateur,
            "email": email,
            "mot_de_passe": "motdepasse123",
            "confirmation": "motdepasse123",
        },
    )


@pytest.mark.parametrize("email", ["", "pas-une-adresse", "a@b", "avec espace@exemple.fr"])
def test_inscription_refuse_une_adresse_invalide(visiteur, email):
    reponse = inscrire(visiteur, email)
    assert reponse.status_code == 400
    assert "Cette adresse e-mail n&#39;est pas valide." in reponse.text


def test_inscription_refuse_une_adresse_deja_utilisee(visiteur, id_testeur):
    # Majuscules et espaces ne changent rien : c'est la même adresse.
    reponse = inscrire(visiteur, "  TESTEUR@exemple.fr ")
    assert reponse.status_code == 400
    assert "déjà utilisée" in reponse.text


def test_inscription_envoie_un_lien_de_confirmation(visiteur, app, boite_mail):
    inscrire(visiteur, "Nouveau@Exemple.fr")
    utilisateur = lire_utilisateur(app, "nouveau")
    # Adresse enregistrée en minuscules, pas encore confirmée.
    assert utilisateur.email == "nouveau@exemple.fr"
    assert utilisateur.email_verifie is False

    assert len(boite_mail) == 1
    assert boite_mail[0]["destinataire"] == "nouveau@exemple.fr"
    assert lien_dans(boite_mail[0]).startswith(f"{ADRESSE_DU_SITE_TEST}/confirmer-email/")
    assert "Un e-mail de confirmation a été envoyé" in visiteur.get("/bonjour").text


# --- Confirmation de l'adresse ----------------------------------------------------------


def test_le_lien_de_confirmation_valide_l_adresse(visiteur, app, boite_mail):
    inscrire(visiteur, "nouveau@exemple.fr")
    reponse = visiteur.get(chemin_de(lien_dans(boite_mail[0])), follow_redirects=True)
    assert "Votre adresse e-mail est confirmée." in reponse.text
    assert lire_utilisateur(app, "nouveau").email_verifie is True


def test_un_lien_de_confirmation_modifie_est_refuse(visiteur, app, boite_mail):
    inscrire(visiteur, "nouveau@exemple.fr")
    lien = chemin_de(lien_dans(boite_mail[0]))
    reponse = visiteur.get(lien[:-3] + "abc", follow_redirects=True)
    assert "invalide ou a expiré" in reponse.text
    assert lire_utilisateur(app, "nouveau").email_verifie is False


def test_l_ancien_lien_de_confirmation_ne_vaut_plus_apres_changement_d_adresse(
    client, app, boite_mail
):
    client.post("/compte/email", data={"email": "premiere@exemple.fr", "mot_de_passe": MOT_DE_PASSE_TEST})
    ancien_lien = chemin_de(lien_dans(boite_mail[0]))
    client.post("/compte/email", data={"email": "seconde@exemple.fr", "mot_de_passe": MOT_DE_PASSE_TEST})

    client.get(ancien_lien)
    utilisateur = lire_utilisateur(app)
    assert utilisateur.email == "seconde@exemple.fr"
    assert utilisateur.email_verifie is False


# --- Mot de passe oublié ------------------------------------------------------------------


def test_la_page_de_connexion_propose_le_mot_de_passe_oublie(visiteur):
    assert "/mot-de-passe-oublie" in visiteur.get("/connexion").text


def test_mot_de_passe_oublie_envoie_un_lien(visiteur, id_testeur, boite_mail):
    reponse = demander_lien(visiteur)
    assert reponse.status_code == 302
    assert len(boite_mail) == 1
    assert boite_mail[0]["destinataire"] == "testeur@exemple.fr"
    assert lien_dans(boite_mail[0]).startswith(f"{ADRESSE_DU_SITE_TEST}/reinitialiser/")


@pytest.mark.parametrize("email", ["inconnu@exemple.fr", "testeur@exemple.fr"])
def test_meme_message_que_l_adresse_existe_ou_non(visiteur, id_testeur, email):
    # On ne doit pas pouvoir deviner quelles adresses ont un compte.
    reponse = demander_lien(visiteur, email)
    page = visiteur.get(reponse.headers["Location"]).text
    assert "Si un compte avec une adresse e-mail confirmée correspond" in page


def test_aucun_email_pour_une_adresse_inconnue(visiteur, id_testeur, boite_mail):
    demander_lien(visiteur, "inconnu@exemple.fr")
    assert boite_mail == []


def test_aucun_email_pour_une_adresse_non_confirmee(visiteur, creer_utilisateur, boite_mail):
    creer_utilisateur("distrait", email="distrait@exemple.fr", email_verifie=False)
    demander_lien(visiteur, "distrait@exemple.fr")
    assert boite_mail == []


def test_le_lien_utilise_l_adresse_configuree_et_pas_celle_de_la_requete(
    visiteur, id_testeur, boite_mail
):
    # Attaque "password reset poisoning" : le pirate fait croire au site
    # qu'il s'appelle site-pirate.com. Le lien envoyé doit rester le bon.
    visiteur.post(
        "/mot-de-passe-oublie",
        data={"email": "testeur@exemple.fr"},
        base_url="http://site-pirate.com",
    )
    assert lien_dans(boite_mail[0]).startswith(ADRESSE_DU_SITE_TEST)
    assert "site-pirate" not in boite_mail[0]["texte"]


# --- Réinitialisation ----------------------------------------------------------------------


@pytest.fixture
def lien_reinitialisation(visiteur, id_testeur, boite_mail):
    demander_lien(visiteur)
    return chemin_de(lien_dans(boite_mail[0]))


def reinitialiser(client, lien, mot_de_passe=NOUVEAU_MOT_DE_PASSE, confirmation=None):
    return client.post(
        lien,
        data={
            "mot_de_passe": mot_de_passe,
            "confirmation": mot_de_passe if confirmation is None else confirmation,
        },
    )


def test_la_page_de_reinitialisation_s_affiche(visiteur, lien_reinitialisation):
    reponse = visiteur.get(lien_reinitialisation)
    assert reponse.status_code == 200
    assert "Nouveau mot de passe" in reponse.text


def test_reinitialiser_change_le_mot_de_passe(visiteur, app, lien_reinitialisation):
    reponse = reinitialiser(visiteur, lien_reinitialisation)
    assert reponse.status_code == 302
    assert reponse.headers["Location"] == "/connexion"

    assert connecter(app.test_client(), MOT_DE_PASSE_TEST).status_code == 400
    assert connecter(app.test_client(), NOUVEAU_MOT_DE_PASSE).status_code == 302


def test_le_lien_ne_sert_qu_une_fois(visiteur, lien_reinitialisation):
    reinitialiser(visiteur, lien_reinitialisation)
    reponse = reinitialiser(visiteur, lien_reinitialisation, mot_de_passe="pirate-mdp-789")
    assert reponse.status_code == 400
    assert "a déjà été utilisé" in reponse.text


def test_le_lien_expire(visiteur, lien_reinitialisation, monkeypatch):
    # Durée de validité négative : le lien est considéré comme expiré.
    monkeypatch.setattr(jetons, "DUREE_LIEN_REINITIALISATION", -1)
    assert visiteur.get(lien_reinitialisation).status_code == 400


def test_un_lien_invente_est_refuse(visiteur, id_testeur):
    assert visiteur.get("/reinitialiser/un-jeton-invente").status_code == 400


def test_un_lien_de_confirmation_ne_permet_pas_de_reinitialiser(client, boite_mail):
    # Le sel ("usage") empêche d'utiliser un jeton pour autre chose.
    client.post("/compte/email", data={"email": "neuve@exemple.fr", "mot_de_passe": MOT_DE_PASSE_TEST})
    jeton = lien_dans(boite_mail[0]).rsplit("/", 1)[1]
    assert client.get(f"/reinitialiser/{jeton}").status_code == 400


def test_mot_de_passe_trop_court_refuse(visiteur, lien_reinitialisation):
    reponse = reinitialiser(visiteur, lien_reinitialisation, mot_de_passe="court")
    assert reponse.status_code == 400
    assert "au moins 8 caractères" in reponse.text


def test_la_reinitialisation_deconnecte_les_sessions_ouvertes(client, app, boite_mail):
    # "client" est connecté. Quelqu'un réinitialise le mot de passe ailleurs.
    assert client.get("/compte").status_code == 200
    autre_navigateur = app.test_client()
    demander_lien(autre_navigateur)
    reinitialiser(autre_navigateur, chemin_de(lien_dans(boite_mail[0])))
    # La session de "client" n'est plus valable : retour à la connexion.
    reponse = client.get("/compte")
    assert reponse.status_code == 302
    assert "/connexion" in reponse.headers["Location"]


# --- Page Mon compte ------------------------------------------------------------------------


def test_mon_compte_est_reserve_aux_connectes(visiteur):
    reponse = visiteur.get("/compte")
    assert reponse.status_code == 302
    assert "/connexion" in reponse.headers["Location"]


def test_mon_compte_affiche_l_adresse(client):
    page = client.get("/compte").text
    assert "testeur@exemple.fr" in page
    assert "(confirmée)" in page


def test_ajouter_une_adresse_a_un_ancien_compte(app, creer_utilisateur, boite_mail):
    creer_utilisateur("ancien", email=None)
    navigateur = app.test_client()
    navigateur.post("/connexion", data={"nom_utilisateur": "ancien", "mot_de_passe": MOT_DE_PASSE_TEST})
    # Rappel affiché tant qu'aucune adresse n'est confirmée.
    assert "Sans adresse e-mail confirmée" in navigateur.get("/bonjour").text
    assert "pas encore d'adresse e-mail" in navigateur.get("/compte").text

    navigateur.post("/compte/email", data={"email": "ancien@exemple.fr", "mot_de_passe": MOT_DE_PASSE_TEST})
    assert lire_utilisateur(app, "ancien").email == "ancien@exemple.fr"
    assert boite_mail[0]["destinataire"] == "ancien@exemple.fr"


def test_changer_d_adresse_demande_le_mot_de_passe(client, app):
    reponse = client.post("/compte/email", data={"email": "pirate@exemple.fr", "mot_de_passe": "mauvais"})
    assert reponse.status_code == 400
    assert "Mot de passe incorrect." in reponse.text
    assert lire_utilisateur(app).email == "testeur@exemple.fr"


def test_changer_d_adresse_demande_une_nouvelle_confirmation(client, app, boite_mail):
    client.post("/compte/email", data={"email": "neuve@exemple.fr", "mot_de_passe": MOT_DE_PASSE_TEST})
    utilisateur = lire_utilisateur(app)
    assert utilisateur.email == "neuve@exemple.fr"
    assert utilisateur.email_verifie is False
    assert boite_mail[0]["destinataire"] == "neuve@exemple.fr"


def test_on_ne_peut_pas_prendre_l_adresse_d_un_autre(client, creer_utilisateur):
    creer_utilisateur("autre")
    reponse = client.post("/compte/email", data={"email": "autre@exemple.fr", "mot_de_passe": MOT_DE_PASSE_TEST})
    assert reponse.status_code == 400
    assert "déjà utilisée" in reponse.text


def test_renvoyer_l_email_de_confirmation(app, creer_utilisateur, boite_mail):
    creer_utilisateur("distrait", email="distrait@exemple.fr", email_verifie=False)
    navigateur = app.test_client()
    navigateur.post("/connexion", data={"nom_utilisateur": "distrait", "mot_de_passe": MOT_DE_PASSE_TEST})
    navigateur.post("/compte/renvoyer-confirmation")
    assert boite_mail[0]["destinataire"] == "distrait@exemple.fr"


def changer_mot_de_passe(client, actuel, nouveau=NOUVEAU_MOT_DE_PASSE):
    return client.post(
        "/compte/mot-de-passe",
        data={"actuel": actuel, "mot_de_passe": nouveau, "confirmation": nouveau},
    )


def test_changer_de_mot_de_passe_demande_l_actuel(client):
    reponse = changer_mot_de_passe(client, actuel="mauvais")
    assert reponse.status_code == 400
    assert "Mot de passe actuel incorrect." in reponse.text


def test_changer_de_mot_de_passe(client, app):
    autre_session = app.test_client()
    connecter(autre_session)

    reponse = changer_mot_de_passe(client, actuel=MOT_DE_PASSE_TEST)
    assert reponse.status_code == 302
    # Cette session reste connectée...
    assert client.get("/compte").status_code == 200
    # ... mais l'autre session est déconnectée.
    assert autre_session.get("/compte").status_code == 302
    assert connecter(app.test_client(), NOUVEAU_MOT_DE_PASSE).status_code == 302


# --- Envoi réel par Brevo (simulé) ---------------------------------------------------------


class FausseReponse:
    def __init__(self, code):
        self.status_code = code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"Erreur {self.status_code}")


def configurer_brevo(app):
    app.config.update(
        EMAIL_MODE="brevo",
        BREVO_API_KEY="cle-de-test",
        EMAIL_EXPEDITEUR="expediteur@exemple.fr",
        NOM_EXPEDITEUR="webapp-noms",
    )


def test_envoi_par_l_api_brevo(app, monkeypatch):
    configurer_brevo(app)
    appels = []
    # On remplace requests.post pour ne rien envoyer vraiment.
    monkeypatch.setattr(
        requests, "post", lambda url, **options: appels.append((url, options)) or FausseReponse(201)
    )
    with app.app_context():
        assert envoyer_email("dest@exemple.fr", "Sujet", "Texte") is True

    url, options = appels[0]
    assert url == "https://api.brevo.com/v3/smtp/email"
    assert options["headers"]["api-key"] == "cle-de-test"
    assert options["json"]["sender"]["email"] == "expediteur@exemple.fr"
    assert options["json"]["to"] == [{"email": "dest@exemple.fr"}]
    assert options["json"]["textContent"] == "Texte"


def test_un_echec_de_brevo_ne_fait_pas_planter_le_site(app, visiteur, monkeypatch):
    configurer_brevo(app)
    monkeypatch.setattr(requests, "post", lambda url, **options: FausseReponse(401))
    reponse = inscrire(visiteur, "nouveau@exemple.fr")
    # Le compte est créé, et l'utilisateur est prévenu du problème.
    assert reponse.status_code == 302
    assert "n&#39;a pas pu être envoyé" in visiteur.get("/bonjour").text
