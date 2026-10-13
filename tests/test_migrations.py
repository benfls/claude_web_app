"""Tests des migrations : la structure de la base doit pouvoir évoluer
sans perdre les données déjà enregistrées."""

import sqlite3

from flask_migrate import downgrade

from webapp import appliquer_migrations, create_app


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


def test_une_ancienne_base_garde_ses_noms(tmp_path):
    chemin = tmp_path / "ancienne.db"
    creer_ancienne_base(chemin)

    app = create_app({"SQLALCHEMY_DATABASE_URI": f"sqlite:///{chemin}"})
    appliquer_migrations(app)

    # Le nom enregistré avant la migration s'affiche toujours,
    # avec sa date au nouveau format.
    page = app.test_client().get("/bonjour").text
    assert "Ancien nom" in page
    assert " à " in page


def test_on_peut_ajouter_un_nom_dans_une_ancienne_base(tmp_path):
    chemin = tmp_path / "ancienne.db"
    creer_ancienne_base(chemin)

    app = create_app({"SQLALCHEMY_DATABASE_URI": f"sqlite:///{chemin}"})
    appliquer_migrations(app)
    app.test_client().post("/bonjour", data={"nom": "Nouveau nom"})

    lignes = sqlite3.connect(chemin).execute("SELECT nom FROM noms ORDER BY id").fetchall()
    assert lignes == [("Ancien nom",), ("Nouveau nom",)]


def test_la_migration_peut_etre_annulee(tmp_path):
    chemin = tmp_path / "test.db"
    app = create_app({"SQLALCHEMY_DATABASE_URI": f"sqlite:///{chemin}"})
    appliquer_migrations(app)

    # downgrade() annule la migration : la table noms doit disparaître.
    with app.app_context():
        downgrade(revision="base")
    tables = sqlite3.connect(chemin).execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    assert ("noms",) not in tables
