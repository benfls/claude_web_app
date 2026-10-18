"""Tests des migrations : la structure de la base doit pouvoir évoluer
sans perdre les données déjà enregistrées."""

import sqlite3

from flask_migrate import downgrade, upgrade

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


def lister_colonnes(chemin, table):
    lignes = sqlite3.connect(chemin).execute(f"PRAGMA table_info({table})").fetchall()
    return {ligne[1] for ligne in lignes}


def test_une_ancienne_base_est_mise_a_jour(tmp_path):
    chemin = tmp_path / "ancienne.db"
    creer_ancienne_base(chemin)
    app = application_migree(chemin)

    assert {"noms", "utilisateurs"} <= lister_tables(chemin)
    assert "auteur_id" in lister_colonnes(chemin, "noms")
    # Les noms sans auteur ont été supprimés par la migration 21be5141fa9f.
    assert "Ancien nom" not in app.test_client().get("/bonjour").text


def test_mise_a_jour_d_une_base_avec_comptes_et_noms_sans_auteur(tmp_path):
    """Reproduit la base de production avant la migration des auteurs."""
    chemin = tmp_path / "production.db"
    app = create_app(
        {"SQLALCHEMY_DATABASE_URI": f"sqlite:///{chemin}", "SECRET_KEY": "test"}
    )
    # On s'arrête à la migration précédente (comptes, mais pas d'auteurs).
    with app.app_context():
        upgrade(revision="8c4e85f807c7")
    conn = sqlite3.connect(chemin)
    conn.execute(
        "INSERT INTO utilisateurs (nom_utilisateur, mot_de_passe_hash, date_creation)"
        " VALUES ('ben', 'empreinte', '2026-10-14 10:00:00')"
    )
    conn.execute("INSERT INTO noms (nom, date_ajout) VALUES ('Ancien nom', '2026-10-14 10:00:00')")
    conn.commit()
    conn.close()

    appliquer_migrations(app)

    conn = sqlite3.connect(chemin)
    # Les noms sont supprimés, les comptes sont conservés.
    assert conn.execute("SELECT count(*) FROM noms").fetchone() == (0,)
    assert conn.execute("SELECT nom_utilisateur FROM utilisateurs").fetchall() == [("ben",)]


def test_on_peut_ajouter_un_nom_apres_la_migration(tmp_path):
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
    assert lignes == [("Nouveau nom",)]


def test_les_migrations_peuvent_etre_annulees(tmp_path):
    chemin = tmp_path / "test.db"
    app = application_migree(chemin)
    assert {"noms", "utilisateurs"} <= lister_tables(chemin)

    # Annuler la dernière migration retire la colonne auteur_id.
    with app.app_context():
        downgrade(revision="8c4e85f807c7")
    assert "auteur_id" not in lister_colonnes(chemin, "noms")

    # downgrade() annule les migrations, de la plus récente à la plus ancienne.
    with app.app_context():
        downgrade(revision="base")
    tables = lister_tables(chemin)
    assert "noms" not in tables
    assert "utilisateurs" not in tables
