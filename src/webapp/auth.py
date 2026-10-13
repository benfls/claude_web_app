"""Les comptes utilisateurs : inscription, connexion et déconnexion.

Flask-Login se charge de retenir qui est connecté (dans un cookie de
session signé par la SECRET_KEY) et fournit :
- current_user : l'utilisateur de la requête en cours ;
- login_user() / logout_user() : connecter / déconnecter ;
- @login_required : réserver une page aux personnes connectées.
"""

import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user

from .modeles import LONGUEUR_MAX_NOM_UTILISATEUR, Utilisateur, db

auth = Blueprint("auth", __name__)

login_manager = LoginManager()
# Page vers laquelle envoyer une personne non connectée.
login_manager.login_view = "auth.connexion"
login_manager.login_message = "Connectez-vous pour accéder à cette page."

LONGUEUR_MIN_MOT_DE_PASSE = 8

# Lettres minuscules, chiffres, "-" et "_", de 3 à 30 caractères.
FORMAT_NOM_UTILISATEUR = re.compile(
    rf"[a-z0-9_-]{{3,{LONGUEUR_MAX_NOM_UTILISATEUR}}}"
)


@login_manager.user_loader
def charger_utilisateur(id_utilisateur):
    """Retrouve l'utilisateur dont l'id est enregistré dans la session.

    Flask-Login appelle cette fonction à chaque page pour savoir qui
    est connecté.
    """
    return db.session.get(Utilisateur, int(id_utilisateur))


def trouver_utilisateur(nom_utilisateur):
    return db.session.scalar(
        db.select(Utilisateur).filter_by(nom_utilisateur=nom_utilisateur)
    )


def valider_inscription(nom_utilisateur, mot_de_passe, confirmation):
    """Renvoie un message d'erreur si l'inscription est invalide, sinon None."""
    if not FORMAT_NOM_UTILISATEUR.fullmatch(nom_utilisateur):
        return (
            f"Le nom d'utilisateur doit faire de 3 à {LONGUEUR_MAX_NOM_UTILISATEUR} "
            "caractères : lettres minuscules, chiffres, - ou _."
        )
    if len(mot_de_passe) < LONGUEUR_MIN_MOT_DE_PASSE:
        return (
            f"Le mot de passe doit faire au moins "
            f"{LONGUEUR_MIN_MOT_DE_PASSE} caractères."
        )
    if mot_de_passe != confirmation:
        return "Les deux mots de passe ne correspondent pas."
    if trouver_utilisateur(nom_utilisateur):
        return "Ce nom d'utilisateur est déjà pris."
    return None


def adresse_de_retour():
    """Page où aller après la connexion.

    Quand on essaie d'ouvrir une page réservée, Flask-Login renvoie vers
    /connexion?next=/la/page. Sécurité : on n'accepte qu'une adresse de
    notre propre site ("/bonjour"), jamais "https://site-pirate.com" ou
    "//site-pirate.com", sinon un lien piégé pourrait vous envoyer sur un
    faux site juste après votre connexion.
    """
    suivante = request.args.get("next", "")
    if suivante.startswith("/") and not suivante.startswith("//") and "\\" not in suivante:
        return suivante
    return url_for("pages.bonjour")


@auth.route("/inscription", methods=["GET", "POST"])
def inscription():
    if current_user.is_authenticated:
        return redirect(url_for("pages.bonjour"))

    erreur = None
    nom_utilisateur = ""
    if request.method == "POST":
        # .lower() : "Ben" et "ben" désignent le même compte.
        nom_utilisateur = request.form.get("nom_utilisateur", "").strip().lower()
        mot_de_passe = request.form.get("mot_de_passe", "")
        confirmation = request.form.get("confirmation", "")
        erreur = valider_inscription(nom_utilisateur, mot_de_passe, confirmation)
        if erreur is None:
            utilisateur = Utilisateur(nom_utilisateur=nom_utilisateur)
            utilisateur.definir_mot_de_passe(mot_de_passe)
            db.session.add(utilisateur)
            db.session.commit()
            # On connecte directement la personne qui vient de s'inscrire.
            login_user(utilisateur)
            flash(f"Bienvenue {nom_utilisateur}, votre compte est créé.")
            return redirect(url_for("pages.bonjour"))

    return render_template(
        "inscription.html",
        erreur=erreur,
        nom_utilisateur=nom_utilisateur,
        longueur_min=LONGUEUR_MIN_MOT_DE_PASSE,
        longueur_max=LONGUEUR_MAX_NOM_UTILISATEUR,
    ), 400 if erreur else 200


@auth.route("/connexion", methods=["GET", "POST"])
def connexion():
    if current_user.is_authenticated:
        return redirect(url_for("pages.bonjour"))

    erreur = None
    nom_utilisateur = ""
    if request.method == "POST":
        nom_utilisateur = request.form.get("nom_utilisateur", "").strip().lower()
        mot_de_passe = request.form.get("mot_de_passe", "")
        utilisateur = trouver_utilisateur(nom_utilisateur)
        if utilisateur and utilisateur.verifier_mot_de_passe(mot_de_passe):
            login_user(utilisateur)
            return redirect(adresse_de_retour())
        # Même message que le compte existe ou non : on ne révèle pas
        # quels noms d'utilisateur sont inscrits.
        erreur = "Nom d'utilisateur ou mot de passe incorrect."

    return render_template(
        "connexion.html", erreur=erreur, nom_utilisateur=nom_utilisateur
    ), 400 if erreur else 200


# POST uniquement : un simple lien (ou une image piégée sur un autre site)
# ne doit pas pouvoir vous déconnecter.
@auth.post("/deconnexion")
@login_required
def deconnexion():
    logout_user()
    flash("Vous êtes déconnecté.")
    return redirect(url_for("pages.accueil"))
