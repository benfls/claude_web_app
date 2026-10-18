"""Préparation commune à tous les tests.

pytest lit automatiquement ce fichier. Les fonctions marquées
@pytest.fixture peuvent être demandées par un test en les mettant
en paramètre : pytest les exécute et passe le résultat au test.
"""

import os

import pytest
from flask_migrate import downgrade

from webapp import appliquer_migrations, create_app
from webapp.modeles import Nom, Utilisateur, db

# Compte créé pour les tests qui ont besoin d'être connectés.
NOM_UTILISATEUR_TEST = "testeur"
MOT_DE_PASSE_TEST = "motdepasse123"

# Pour lancer les tests sur PostgreSQL plutôt que SQLite, par exemple :
#   TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost/tests uv run pytest
# (la CI le fait automatiquement). Attention : la base indiquée est vidée.
URL_BASE_DE_TEST = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture
def base_de_test(tmp_path):
    """Chemin d'une base vide, propre à chaque test.

    tmp_path est un dossier temporaire fourni par pytest : votre noms.db
    n'est jamais touché.
    """
    return tmp_path / "test.db"


@pytest.fixture
def app(base_de_test):
    """Une application branchée sur la base de test, créée par les migrations."""
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": URL_BASE_DE_TEST or f"sqlite:///{base_de_test}",
            "SECRET_KEY": "cle-pour-les-tests",
            # La vérification CSRF et la limitation des tentatives sont
            # désactivées pour simplifier la plupart des tests ;
            # test_comptes.py et test_production.py les réactivent.
            "WTF_CSRF_ENABLED": False,
            "RATELIMIT_ENABLED": False,
        }
    )
    appliquer_migrations(app)
    yield app

    # Après le test : avec PostgreSQL, la base n'est pas un fichier jetable,
    # on annule donc les migrations pour la laisser vide pour le test suivant.
    if URL_BASE_DE_TEST:
        with app.app_context():
            db.session.remove()
            downgrade(revision="base")
            db.engine.dispose()


@pytest.fixture
def creer_utilisateur(app):
    """Renvoie une fonction qui crée un compte dans la base et renvoie son id."""

    def creer(nom_utilisateur=NOM_UTILISATEUR_TEST, mot_de_passe=MOT_DE_PASSE_TEST):
        with app.app_context():
            utilisateur = Utilisateur(nom_utilisateur=nom_utilisateur)
            utilisateur.definir_mot_de_passe(mot_de_passe)
            db.session.add(utilisateur)
            db.session.commit()
            return utilisateur.id

    return creer


def navigateur_connecte(app, nom_utilisateur):
    """Un faux navigateur connecté avec le compte indiqué."""
    navigateur = app.test_client()
    navigateur.post(
        "/connexion",
        data={"nom_utilisateur": nom_utilisateur, "mot_de_passe": MOT_DE_PASSE_TEST},
    )
    return navigateur


@pytest.fixture
def id_testeur(creer_utilisateur):
    """Crée le compte de test et renvoie son id."""
    return creer_utilisateur()


@pytest.fixture
def visiteur(app):
    """Un faux navigateur, non connecté."""
    return app.test_client()


@pytest.fixture
def client(app, id_testeur):
    """Un faux navigateur déjà connecté avec le compte de test."""
    return navigateur_connecte(app, NOM_UTILISATEUR_TEST)


@pytest.fixture
def client_autre(app, creer_utilisateur):
    """Un faux navigateur connecté avec un autre compte que celui de test."""
    creer_utilisateur("autre")
    return navigateur_connecte(app, "autre")


@pytest.fixture
def lire_noms(app):
    """Renvoie une fonction qui lit les noms directement dans la base."""

    def lire():
        # app_context() : SQLAlchemy a besoin de savoir de quelle
        # application (donc de quelle base) il s'agit.
        with app.app_context():
            return list(db.session.scalars(db.select(Nom.nom).order_by(Nom.id)))

    return lire


@pytest.fixture
def id_ben(app, id_testeur):
    """Ajoute le nom "Ben", écrit par le compte de test, et renvoie son id."""
    with app.app_context():
        ben = Nom(nom="Ben", auteur_id=id_testeur)
        db.session.add(ben)
        db.session.commit()
        return ben.id
