import os
import sqlite3
from pathlib import Path

from flask import Flask, redirect, render_template, request, url_for

# L'objet "app" représente toute l'application web.
app = Flask(__name__)

# Fichier de la base de données SQLite. Par défaut à la racine du projet,
# mais la variable d'environnement CHEMIN_BASE_DE_DONNEES peut le changer
# (c'est ce que fait Docker, voir compose.yaml).
BASE_DE_DONNEES = Path(
    os.environ.get(
        "CHEMIN_BASE_DE_DONNEES",
        Path(__file__).resolve().parents[2] / "noms.db",
    )
)


def connexion():
    """Ouvre une connexion à la base de données."""
    conn = sqlite3.connect(BASE_DE_DONNEES)
    # Permet d'écrire ligne["nom"] au lieu de ligne[0].
    conn.row_factory = sqlite3.Row
    return conn


def creer_table():
    """Crée la table "noms" si elle n'existe pas encore."""
    conn = connexion()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS noms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            date_ajout TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
        """
    )
    conn.commit()
    conn.close()


creer_table()


# Chaque fonction décorée par @app.route répond à une adresse (URL).
@app.route("/")
def accueil():
    return render_template("accueil.html")


# Cette page accepte GET (afficher le formulaire) et POST (formulaire envoyé).
@app.route("/bonjour", methods=["GET", "POST"])
def bonjour():
    if request.method == "POST":
        nom = request.form.get("nom", "").strip()
        if nom:
            conn = connexion()
            # Le "?" est remplacé par la valeur de nom de façon sécurisée :
            # ne jamais coller le texte de l'utilisateur directement dans le SQL.
            conn.execute("INSERT INTO noms (nom) VALUES (?)", (nom,))
            conn.commit()
            conn.close()
        # Redirection après l'envoi : recharger la page (F5) ne renverra
        # pas le formulaire une deuxième fois.
        return redirect(url_for("bonjour", nom=nom))

    conn = connexion()
    noms = conn.execute(
        "SELECT nom, date_ajout FROM noms ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return render_template("bonjour.html", nom=request.args.get("nom"), noms=noms)


def main() -> None:
    # debug=True recharge le serveur à chaque modification du code.
    # host="0.0.0.0" rend le site accessible depuis le navigateur Windows.
    app.run(host="0.0.0.0", port=5000, debug=True)
