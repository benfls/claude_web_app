"""Préparation commune à tous les tests.

pytest lit automatiquement ce fichier. Les fonctions marquées
@pytest.fixture peuvent être demandées par un test en les mettant
en paramètre : pytest les exécute et passe le résultat au test.
"""

import pytest

import webapp


@pytest.fixture
def base_de_test(tmp_path, monkeypatch):
    """Remplace la vraie base par une base vide, propre à chaque test.

    tmp_path est un dossier temporaire fourni par pytest, et monkeypatch
    remet la valeur d'origine à la fin du test : votre noms.db n'est
    jamais touché.
    """
    chemin = tmp_path / "test.db"
    monkeypatch.setattr(webapp, "BASE_DE_DONNEES", chemin)
    webapp.creer_table()
    return chemin


@pytest.fixture
def client(base_de_test):
    """Un faux navigateur pour appeler les pages sans lancer de serveur."""
    webapp.app.config["TESTING"] = True
    return webapp.app.test_client()
