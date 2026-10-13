"""Préparation commune à tous les tests.

pytest lit automatiquement ce fichier. Les fonctions marquées
@pytest.fixture peuvent être demandées par un test en les mettant
en paramètre : pytest les exécute et passe le résultat au test.
"""

import pytest

from webapp import appliquer_migrations, create_app
from webapp.modeles import Nom, db


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
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{base_de_test}",
        }
    )
    appliquer_migrations(app)
    return app


@pytest.fixture
def client(app):
    """Un faux navigateur pour appeler les pages sans lancer de serveur."""
    return app.test_client()


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
def id_ben(app):
    """Ajoute le nom "Ben" dans la base et renvoie son numéro (id)."""
    with app.app_context():
        ben = Nom(nom="Ben")
        db.session.add(ben)
        db.session.commit()
        return ben.id
