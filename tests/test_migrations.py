"""Tests des migrations : la structure de la base doit pouvoir évoluer
sans perdre les données déjà enregistrées."""

import sqlite3

from flask_migrate import downgrade

from webapp import appliquer_migrations, create_app
from webapp.modeles import Utilisateur, db


def creer_ancienne_base(chemin):
    """Crée une base comme le faisait l'application avant Flask-Migrate."""
    conn = sqlite3.connect(chemin)
    conn.execute(
        """
        CREATE TABLE noms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            date_ajout TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
        """
    )
    conn.execute("INSERT INTO noms (nom) VALUES ('Ancien nom')")
    conn.commit()
    conn.close()


def application_migree(chemin):
    """Crée une application sur la base donnée et applique les migrations."""
    app = create_app(
        {
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{chemin}",
            "SECRET_KEY": "test",
            "WTF_CSRF_ENABLED": False,
        }
    )
    appliquer_migrations(app)
    return app


def lister_tables(chemin):
    lignes = sqlite3.connect(chemin).execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {ligne[0] for ligne in lignes}


def test_une_ancienne_base_garde_ses_noms(tmp_path):
    chemin = tmp_path / "ancienne.db"
    creer_ancienne_base(chemin)
    app = application_migree(chemin)

    # Le nom enregistré avant la migration s'affiche toujours,
    # avec sa date au nouveau format.
    page = app.test_client().get("/bonjour").text
    assert "Ancien nom" in page
    assert " à " in page


def test_une_ancienne_base_recoit_la_table_utilisateurs(tmp_path):
    chemin = tmp_path / "ancienne.db"
    creer_ancienne_base(chemin)
    application_migree(chemin)
    assert {"noms", "utilisateurs"} <= lister_tables(chemin)


def test_on_peut_ajouter_un_nom_dans_une_ancienne_base(tmp_path):
    chemin = tmp_path / "ancienne.db"
    creer_ancienne_base(chemin)
    app = application_migree(chemin)

    with app.app_context():
        utilisateur = Utilisateur(nom_utilisateur="ben")
        utilisateur.definir_mot_de_passe("motdepasse123")
        db.session.add(utilisateur)
        db.session.commit()

    client = app.test_client()
    client.post("/connexion", data={"nom_utilisateur": "ben", "mot_de_passe": "motdepasse123"})
    client.post("/bonjour", data={"nom": "Nouveau nom"})

    lignes = sqlite3.connect(chemin).execute("SELECT nom FROM noms ORDER BY id").fetchall()
    assert lignes == [("Ancien nom",), ("Nouveau nom",)]


def test_les_migrations_peuvent_etre_annulees(tmp_path):
    chemin = tmp_path / "test.db"
    app = application_migree(chemin)
    assert {"noms", "utilisateurs"} <= lister_tables(chemin)

    # downgrade() annule les migrations, de la plus récente à la plus ancienne.
    with app.app_context():
        downgrade(revision="base")
    tables = lister_tables(chemin)
    assert "noms" not in tables
    assert "utilisateurs" not in tables
