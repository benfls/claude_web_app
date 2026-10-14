"""Tests des réglages de production : base de données, sécurité, santé
et limitation des tentatives."""

import pytest

from webapp import adresse_base_de_donnees, appliquer_migrations, create_app
from webapp.modeles import Utilisateur, db

from conftest import MOT_DE_PASSE_TEST, NOM_UTILISATEUR_TEST


def nouvelle_application(tmp_path, **reglages):
    """Application de test sur une base SQLite temporaire."""
    config = {
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
        "SECRET_KEY": "test",
        "WTF_CSRF_ENABLED": False,
    }
    config.update(reglages)
    app = create_app(config)
    appliquer_migrations(app)
    return app


# --- Choix de la base de données ------------------------------------------------


@pytest.mark.parametrize(
    "url_hebergeur",
    ["postgresql://moi:secret@serveur:5432/base", "postgres://moi:secret@serveur:5432/base"],
)
def test_database_url_utilise_postgresql_avec_psycopg(monkeypatch, url_hebergeur):
    monkeypatch.setenv("DATABASE_URL", url_hebergeur)
    assert adresse_base_de_donnees() == "postgresql+psycopg://moi:secret@serveur:5432/base"


def test_sans_database_url_on_garde_sqlite(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert adresse_base_de_donnees().startswith("sqlite:///")


# --- Sécurité ---------------------------------------------------------------------


def test_entetes_de_securite_sur_chaque_page(visiteur):
    entetes = visiteur.get("/").headers
    assert entetes["X-Frame-Options"] == "DENY"
    assert entetes["X-Content-Type-Options"] == "nosniff"
    assert entetes["Referrer-Policy"] == "same-origin"


def test_hors_production_pas_de_https_obligatoire(visiteur, app):
    assert app.config["SESSION_COOKIE_SECURE"] is False
    assert "Strict-Transport-Security" not in visiteur.get("/").headers


def test_en_production_https_obligatoire(tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCTION", "1")
    app = nouvelle_application(tmp_path)
    # Le cookie de session ne circule qu'en HTTPS.
    assert app.config["SESSION_COOKIE_SECURE"] is True
    entetes = app.test_client().get("/").headers
    assert entetes["Strict-Transport-Security"] == "max-age=31536000"


# --- Page de santé -------------------------------------------------------------------


def test_page_de_sante(visiteur):
    reponse = visiteur.get("/sante")
    assert reponse.status_code == 200
    assert reponse.json == {"etat": "ok"}


# --- Limitation des tentatives ----------------------------------------------------------


@pytest.fixture
def app_limitee(tmp_path):
    """Application avec la limitation des tentatives activée, et un compte."""
    app = nouvelle_application(tmp_path, RATELIMIT_ENABLED=True)
    with app.app_context():
        for nom in [NOM_UTILISATEUR_TEST, "autre"]:
            utilisateur = Utilisateur(nom_utilisateur=nom)
            utilisateur.definir_mot_de_passe(MOT_DE_PASSE_TEST)
            db.session.add(utilisateur)
        db.session.commit()
    return app


def connecter(client, nom_utilisateur=NOM_UTILISATEUR_TEST, mot_de_passe=MOT_DE_PASSE_TEST):
    return client.post(
        "/connexion", data={"nom_utilisateur": nom_utilisateur, "mot_de_passe": mot_de_passe}
    )


def test_connexion_bloquee_apres_5_echecs(app_limitee):
    client = app_limitee.test_client()
    for _ in range(5):
        assert connecter(client, mot_de_passe="mauvais").status_code == 400
    # 6e tentative : bloquée, même avec le bon mot de passe.
    reponse = connecter(client)
    assert reponse.status_code == 429
    assert "Trop de tentatives" in reponse.text


def test_le_blocage_ne_touche_que_le_compte_vise(app_limitee):
    client = app_limitee.test_client()
    for _ in range(5):
        connecter(client, mot_de_passe="mauvais")
    assert connecter(client).status_code == 429
    # Un autre compte peut toujours se connecter.
    assert connecter(app_limitee.test_client(), nom_utilisateur="autre").status_code == 302


def test_les_connexions_reussies_ne_comptent_pas(app_limitee):
    for _ in range(8):
        client = app_limitee.test_client()
        assert connecter(client).status_code == 302


def inscrire(client, nom_utilisateur, mot_de_passe="motdepasse123"):
    return client.post(
        "/inscription",
        data={
            "nom_utilisateur": nom_utilisateur,
            "mot_de_passe": mot_de_passe,
            "confirmation": mot_de_passe,
        },
    )


def test_inscriptions_limitees_a_20_par_heure(app_limitee):
    for numero in range(20):
        assert inscrire(app_limitee.test_client(), f"compte{numero}").status_code == 302
    reponse = inscrire(app_limitee.test_client(), "compte20")
    assert reponse.status_code == 429


def test_les_inscriptions_refusees_ne_comptent_pas(app_limitee):
    for _ in range(25):
        # Mot de passe trop court : inscription refusée (400), non comptée.
        assert inscrire(app_limitee.test_client(), "compte", mot_de_passe="court").status_code == 400
    assert inscrire(app_limitee.test_client(), "compte").status_code == 302
