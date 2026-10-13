"""Assemblage de l'application.

create_app() fabrique l'application : elle la configure, la relie à la base
de données et y branche les pages. C'est le patron "application factory"
de Flask, qui permet par exemple aux tests de créer leur propre application
avec une base temporaire.
"""

import os
from pathlib import Path

from flask import Flask
from flask_migrate import Migrate, upgrade

from .modeles import db
from .routes import pages

# Fichier de la base de données SQLite. Par défaut à la racine du projet,
# mais la variable d'environnement CHEMIN_BASE_DE_DONNEES peut le changer
# (c'est ce que fait Docker, voir le Dockerfile).
BASE_DE_DONNEES = Path(
    os.environ.get(
        "CHEMIN_BASE_DE_DONNEES",
        Path(__file__).resolve().parents[2] / "noms.db",
    )
)

# Dossier des scripts de migration (l'historique de la structure de la base).
DOSSIER_MIGRATIONS = Path(__file__).resolve().parent / "migrations"

# render_as_batch=True : nécessaire avec SQLite, qui ne sait pas modifier
# une colonne existante. Alembic recopie alors la table de façon sûre.
migrate = Migrate(directory=str(DOSSIER_MIGRATIONS), render_as_batch=True)


def create_app(config=None):
    """Fabrique et renvoie l'application Flask.

    config : réglages à modifier, utilisé par les tests pour changer de base.
    """
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{BASE_DE_DONNEES}"
    if config:
        app.config.update(config)

    db.init_app(app)
    migrate.init_app(app, db)
    app.register_blueprint(pages)
    return app


def appliquer_migrations(app):
    """Met la structure de la base à jour (équivaut à "flask db upgrade")."""
    with app.app_context():
        upgrade()


def main() -> None:
    app = create_app()
    appliquer_migrations(app)
    # debug=True recharge le serveur à chaque modification du code.
    # host="0.0.0.0" rend le site accessible depuis le navigateur Windows.
    app.run(host="0.0.0.0", port=5000, debug=True)
