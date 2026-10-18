"""Assemblage de l'application.

create_app() fabrique l'application : elle la configure, la relie à la base
de données et y branche les pages. C'est le patron "application factory"
de Flask, qui permet par exemple aux tests de créer leur propre application
avec une base temporaire.
"""

import os
import re
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template
from flask_migrate import Migrate, upgrade
from flask_wtf.csrf import CSRFProtect

from .auth import auth, limiter, login_manager
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


def adresse_base_de_donnees():
    """Adresse de la base : PostgreSQL si DATABASE_URL existe, sinon SQLite.

    En production, l'hébergeur (Render) fournit DATABASE_URL, de la forme
    "postgresql://utilisateur:motdepasse@serveur/base". En local, on garde
    le fichier SQLite.
    """
    url = os.environ.get("DATABASE_URL")
    if url:
        # On précise à SQLAlchemy d'utiliser le pilote psycopg (version 3).
        return re.sub(r"^postgres(ql)?://", "postgresql+psycopg://", url)
    return f"sqlite:///{BASE_DE_DONNEES}"


def create_app(config=None):
    """Fabrique et renvoie l'application Flask.

    config : réglages à modifier, utilisé par les tests pour changer de base.
    """
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = adresse_base_de_donnees()
    # Vérifie que la connexion à la base est toujours ouverte avant de
    # l'utiliser (un serveur PostgreSQL peut fermer les connexions inactives).
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
    # Clé qui signe les cookies de session : sans elle, n'importe qui
    # pourrait fabriquer un cookie et se faire passer pour un autre.
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
    # Le navigateur n'envoie pas le cookie de session lors d'un envoi de
    # formulaire depuis un autre site (protection supplémentaire contre CSRF).
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    # En production (PRODUCTION=1), le site est servi en HTTPS : le cookie de
    # session ne doit alors jamais circuler sur une connexion non chiffrée.
    app.config["PRODUCTION"] = os.environ.get("PRODUCTION") == "1"
    app.config["SESSION_COOKIE_SECURE"] = app.config["PRODUCTION"]
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
    limiter.init_app(app)
    app.register_blueprint(pages)
    app.register_blueprint(auth)

    @app.errorhandler(403)
    def acces_interdit(erreur):
        """Page affichée quand on essaie de modifier le nom d'un autre."""
        return render_template("acces_interdit.html"), 403

    @app.errorhandler(429)
    def trop_de_tentatives(erreur):
        """Page affichée quand la limite de tentatives est dépassée."""
        return render_template("trop_de_tentatives.html"), 429

    @app.after_request
    def entetes_de_securite(reponse):
        """Ajoute des consignes de sécurité pour le navigateur à chaque page."""
        # Interdit d'afficher le site dans un cadre sur un autre site
        # (technique utilisée pour piéger les clics : "clickjacking").
        reponse.headers["X-Frame-Options"] = "DENY"
        # Le navigateur ne doit pas deviner le type d'un fichier.
        reponse.headers["X-Content-Type-Options"] = "nosniff"
        # N'envoie pas l'adresse complète de nos pages aux autres sites.
        reponse.headers["Referrer-Policy"] = "same-origin"
        if app.config["PRODUCTION"]:
            # Le navigateur doit toujours utiliser HTTPS pour ce site, un an.
            reponse.headers["Strict-Transport-Security"] = "max-age=31536000"
        return reponse

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
