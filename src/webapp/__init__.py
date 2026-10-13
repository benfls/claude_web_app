import os
import sqlite3
from pathlib import Path

from flask import Flask, abort, redirect, render_template, request, url_for

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

# Nombre maximum de caractères autorisés pour un nom.
LONGUEUR_MAX_NOM = 50


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


def valider_nom(nom):
    """Renvoie un message d'erreur si le nom est invalide, sinon None."""
    if not nom:
        return "Le nom ne peut pas être vide."
    if len(nom) > LONGUEUR_MAX_NOM:
        return f"Le nom ne doit pas dépasser {LONGUEUR_MAX_NOM} caractères."
    return None


def lister_noms():
    """Renvoie tous les noms, du plus récent au plus ancien."""
    conn = connexion()
    noms = conn.execute(
        "SELECT id, nom, date_ajout FROM noms ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return noms


# Chaque fonction décorée par @app.route répond à une adresse (URL).
@app.route("/")
def accueil():
    return render_template("accueil.html")


# Cette page accepte GET (afficher le formulaire) et POST (formulaire envoyé).
@app.route("/bonjour", methods=["GET", "POST"])
def bonjour():
    if request.method == "POST":
        nom = request.form.get("nom", "").strip()
        erreur = valider_nom(nom)
        if erreur:
            # On réaffiche la page avec le message d'erreur.
            # Le code 400 signifie "la demande envoyée est incorrecte".
            return render_template(
                "bonjour.html",
                erreur=erreur,
                saisie=nom,
                noms=lister_noms(),
                longueur_max=LONGUEUR_MAX_NOM,
            ), 400

        conn = connexion()
        # Le "?" est remplacé par la valeur de nom de façon sécurisée :
        # ne jamais coller le texte de l'utilisateur directement dans le SQL.
        conn.execute("INSERT INTO noms (nom) VALUES (?)", (nom,))
        conn.commit()
        conn.close()
        # Redirection après l'envoi : recharger la page (F5) ne renverra
        # pas le formulaire une deuxième fois.
        return redirect(url_for("bonjour", nom=nom))

    return render_template(
        "bonjour.html",
        nom=request.args.get("nom"),
        noms=lister_noms(),
        longueur_max=LONGUEUR_MAX_NOM,
    )


# <int:id_nom> récupère le numéro présent dans l'adresse,
# par exemple /noms/3/modifier donne id_nom = 3.
@app.route("/noms/<int:id_nom>/modifier", methods=["GET", "POST"])
def modifier(id_nom):
    conn = connexion()
    ligne = conn.execute(
        "SELECT id, nom FROM noms WHERE id = ?", (id_nom,)
    ).fetchone()
    conn.close()
    if ligne is None:
        # Aucun nom avec ce numéro : page "introuvable".
        abort(404)

    erreur = None
    saisie = ligne["nom"]
    if request.method == "POST":
        saisie = request.form.get("nom", "").strip()
        erreur = valider_nom(saisie)
        if erreur is None:
            conn = connexion()
            conn.execute("UPDATE noms SET nom = ? WHERE id = ?", (saisie, id_nom))
            conn.commit()
            conn.close()
            return redirect(url_for("bonjour"))

    return render_template(
        "modifier.html",
        id_nom=id_nom,
        saisie=saisie,
        erreur=erreur,
        longueur_max=LONGUEUR_MAX_NOM,
    ), 400 if erreur else 200


# Supprimer modifie les données : on n'accepte que POST (un bouton de
# formulaire), jamais un simple lien GET qu'un robot pourrait suivre.
@app.post("/noms/<int:id_nom>/supprimer")
def supprimer(id_nom):
    conn = connexion()
    curseur = conn.execute("DELETE FROM noms WHERE id = ?", (id_nom,))
    conn.commit()
    conn.close()
    # rowcount = nombre de lignes supprimées : 0 si le nom n'existait pas.
    if curseur.rowcount == 0:
        abort(404)
    return redirect(url_for("bonjour"))


def main() -> None:
    # debug=True recharge le serveur à chaque modification du code.
    # host="0.0.0.0" rend le site accessible depuis le navigateur Windows.
    app.run(host="0.0.0.0", port=5000, debug=True)
