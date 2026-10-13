"""Assemblage de l'application.

create_app() fabrique l'application : elle la configure, la relie à la base
de données et y branche les pages. C'est le patron "application factory"
de Flask, qui permet par exemple aux tests de créer leur propre application
avec une base temporaire.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask
from flask_migrate import Migrate, upgrade
from flask_wtf.csrf import CSRFProtect

from .auth import auth, login_manager
from .modeles import db
from .routes import pages

# Lit le fichier .env du projet (SECRET_KEY...) quand on lance sans Docker.
# Les variables déjà définies (par Docker par exemple) ne sont pas écrasées.
load_dotenv()

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

# Protection CSRF : chaque formulaire doit contenir un jeton secret
# ({{ csrf_token() }} dans les templates). Un autre site ne connaît pas ce
# jeton, il ne peut donc pas envoyer de formulaire à votre place.
csrf = CSRFProtect()


def create_app(config=None):
    """Fabrique et renvoie l'application Flask.

    config : réglages à modifier, utilisé par les tests pour changer de base.
    """
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{BASE_DE_DONNEES}"
    # Clé qui signe les cookies de session : sans elle, n'importe qui
    # pourrait fabriquer un cookie et se faire passer pour un autre.
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
    # Le navigateur n'envoie pas le cookie de session lors d'un envoi de
    # formulaire depuis un autre site (protection supplémentaire contre CSRF).
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    if config:
        app.config.update(config)

    if not app.config["SECRET_KEY"]:
        raise RuntimeError(
            "SECRET_KEY manquante : ajoutez-la dans le fichier .env "
            "(voir .env.example)."
        )

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)
    app.register_blueprint(pages)
    app.register_blueprint(auth)
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
