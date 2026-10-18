"""Les comptes utilisateurs : inscription, connexion, mot de passe oublié...

Flask-Login se charge de retenir qui est connecté (dans un cookie de
session signé par la SECRET_KEY) et fournit :
- current_user : l'utilisateur de la requête en cours ;
- login_user() / logout_user() : connecter / déconnecter ;
- @login_required : réserver une page aux personnes connectées.
"""

import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_limiter import Limiter
from flask_login import LoginManager, current_user, login_required, login_user, logout_user

from .emails import envoyer_email, lien_absolu
from .jetons import (
    creer_jeton_confirmation,
    creer_jeton_reinitialisation,
    lire_jeton_confirmation,
    lire_jeton_reinitialisation,
)
from .modeles import LONGUEUR_MAX_EMAIL, LONGUEUR_MAX_NOM_UTILISATEUR, Utilisateur, db

auth = Blueprint("auth", __name__)

login_manager = LoginManager()
# Page vers laquelle envoyer une personne non connectée.
login_manager.login_view = "auth.connexion"
login_manager.login_message = "Connectez-vous pour accéder à cette page."


def compte_vise():
    """Clé de limitation de la connexion : le nom d'utilisateur tapé.

    On limite par compte plutôt que par adresse IP : derrière l'hébergeur,
    l'adresse IP réelle du visiteur n'est pas fiable.
    """
    return "connexion:" + request.form.get("nom_utilisateur", "").strip().lower()


def email_vise():
    """Clé de limitation du mot de passe oublié : l'adresse tapée."""
    return "oubli:" + normaliser_email(request.form.get("email", ""))


def utilisateur_connecte():
    """Clé de limitation des actions de la page "Mon compte"."""
    # getattr : un visiteur non connecté n'a pas d'id (il sera de toute façon
    # renvoyé vers la connexion par @login_required).
    return f"compte:{getattr(current_user, 'id', 'anonyme')}"


def tout_le_site():
    """Clé de limitation de l'inscription : un seul compteur pour tout le site."""
    return "inscription"


# Limitation du nombre de tentatives. Les compteurs sont gardés en mémoire :
# ils repartent de zéro au redémarrage, et chaque processus Gunicorn a les
# siens (suffisant pour un petit site).
limiter = Limiter(key_func=tout_le_site, storage_uri="memory://")

LONGUEUR_MIN_MOT_DE_PASSE = 8

# Lettres minuscules, chiffres, "-" et "_", de 3 à 30 caractères.
FORMAT_NOM_UTILISATEUR = re.compile(
    rf"[a-z0-9_-]{{3,{LONGUEUR_MAX_NOM_UTILISATEUR}}}"
)

# Vérification simple : "quelque chose@quelque chose.quelque chose", sans
# espace. La seule vraie preuve qu'une adresse existe est le lien de
# confirmation envoyé dessus.
FORMAT_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


@login_manager.user_loader
def charger_utilisateur(identifiant):
    """Retrouve l'utilisateur enregistré dans le cookie de session.

    Flask-Login appelle cette fonction à chaque page pour savoir qui est
    connecté. Le cookie contient "id:empreinte" (voir Utilisateur.get_id) :
    si le mot de passe a changé depuis la connexion, l'empreinte ne
    correspond plus et la session est refusée (déconnexion).
    """
    id_texte, _, empreinte = identifiant.partition(":")
    if not id_texte.isdigit():
        return None
    utilisateur = db.session.get(Utilisateur, int(id_texte))
    if utilisateur is None or utilisateur.empreinte_mot_de_passe() != empreinte:
        return None
    return utilisateur


def trouver_utilisateur(nom_utilisateur):
    return db.session.scalar(
        db.select(Utilisateur).filter_by(nom_utilisateur=nom_utilisateur)
    )


def trouver_par_email(email):
    return db.session.scalar(db.select(Utilisateur).filter_by(email=email))


def normaliser_email(email):
    """Les adresses sont enregistrées sans espaces autour et en minuscules."""
    return email.strip().lower()


# --- Règles de validation --------------------------------------------------------


def valider_mot_de_passe(mot_de_passe, confirmation):
    """Renvoie un message d'erreur si le mot de passe est invalide, sinon None."""
    if len(mot_de_passe) < LONGUEUR_MIN_MOT_DE_PASSE:
        return (
            f"Le mot de passe doit faire au moins "
            f"{LONGUEUR_MIN_MOT_DE_PASSE} caractères."
        )
    if mot_de_passe != confirmation:
        return "Les deux mots de passe ne correspondent pas."
    return None


def valider_email(email, utilisateur_actuel=None):
    """Renvoie un message d'erreur si l'adresse est invalide ou déjà prise."""
    if len(email) > LONGUEUR_MAX_EMAIL or not FORMAT_EMAIL.fullmatch(email):
        return "Cette adresse e-mail n'est pas valide."
    deja_prise = trouver_par_email(email)
    if deja_prise and deja_prise != utilisateur_actuel:
        return "Cette adresse e-mail est déjà utilisée par un autre compte."
    return None


def valider_inscription(nom_utilisateur, email, mot_de_passe, confirmation):
    """Renvoie un message d'erreur si l'inscription est invalide, sinon None."""
    if not FORMAT_NOM_UTILISATEUR.fullmatch(nom_utilisateur):
        return (
            f"Le nom d'utilisateur doit faire de 3 à {LONGUEUR_MAX_NOM_UTILISATEUR} "
            "caractères : lettres minuscules, chiffres, - ou _."
        )
    if trouver_utilisateur(nom_utilisateur):
        return "Ce nom d'utilisateur est déjà pris."
    return valider_email(email) or valider_mot_de_passe(mot_de_passe, confirmation)


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


# --- E-mails envoyés par le site ----------------------------------------------------


def envoyer_lien_confirmation(utilisateur):
    """Envoie le lien qui prouve que l'adresse e-mail appartient à l'utilisateur."""
    lien = lien_absolu("auth.confirmer_email", jeton=creer_jeton_confirmation(utilisateur))
    return envoyer_email(
        utilisateur.email,
        "Confirmez votre adresse e-mail",
        f"Bonjour {utilisateur.nom_utilisateur},\n\n"
        f"Pour confirmer votre adresse e-mail, ouvrez ce lien (valable 2 jours) :\n"
        f"{lien}\n\n"
        "Si vous n'êtes pas à l'origine de cette demande, ignorez cet e-mail.",
    )


def envoyer_lien_reinitialisation(utilisateur):
    """Envoie le lien qui permet de choisir un nouveau mot de passe."""
    lien = lien_absolu(
        "auth.reinitialiser", jeton=creer_jeton_reinitialisation(utilisateur)
    )
    return envoyer_email(
        utilisateur.email,
        "Réinitialisation de votre mot de passe",
        f"Bonjour {utilisateur.nom_utilisateur},\n\n"
        "Pour choisir un nouveau mot de passe, ouvrez ce lien "
        "(valable 1 heure, utilisable une seule fois) :\n"
        f"{lien}\n\n"
        "Si vous n'avez rien demandé, ignorez cet e-mail : "
        "votre mot de passe reste inchangé.",
    )


# --- Inscription, connexion, déconnexion ----------------------------------------------


@auth.route("/inscription", methods=["GET", "POST"])
# 20 comptes créés par heure au maximum sur tout le site (contre les robots).
# deduct_when : seules les inscriptions réussies (redirection 302) comptent.
@limiter.limit(
    "20 per hour",
    methods=["POST"],
    deduct_when=lambda reponse: reponse.status_code == 302,
)
def inscription():
    if current_user.is_authenticated:
        return redirect(url_for("pages.bonjour"))

    erreur = None
    nom_utilisateur = ""
    email = ""
    if request.method == "POST":
        # .lower() : "Ben" et "ben" désignent le même compte.
        nom_utilisateur = request.form.get("nom_utilisateur", "").strip().lower()
        email = normaliser_email(request.form.get("email", ""))
        mot_de_passe = request.form.get("mot_de_passe", "")
        confirmation = request.form.get("confirmation", "")
        erreur = valider_inscription(nom_utilisateur, email, mot_de_passe, confirmation)
        if erreur is None:
            utilisateur = Utilisateur(nom_utilisateur=nom_utilisateur, email=email)
            utilisateur.definir_mot_de_passe(mot_de_passe)
            db.session.add(utilisateur)
            db.session.commit()
            # On connecte directement la personne qui vient de s'inscrire.
            login_user(utilisateur)
            flash(f"Bienvenue {nom_utilisateur}, votre compte est créé.")
            if envoyer_lien_confirmation(utilisateur):
                flash(f"Un e-mail de confirmation a été envoyé à {email}.")
            else:
                flash(
                    "L'e-mail de confirmation n'a pas pu être envoyé. "
                    "Réessayez depuis la page Mon compte."
                )
            return redirect(url_for("pages.bonjour"))

    return render_template(
        "inscription.html",
        erreur=erreur,
        nom_utilisateur=nom_utilisateur,
        email=email,
        longueur_min=LONGUEUR_MIN_MOT_DE_PASSE,
        longueur_max=LONGUEUR_MAX_NOM_UTILISATEUR,
    ), 400 if erreur else 200


@auth.route("/connexion", methods=["GET", "POST"])
# Contre les attaques qui essaient des milliers de mots de passe : au-delà
# de 5 échecs par minute ou 20 par heure sur un même compte, les tentatives
# suivantes sont refusées. Seuls les échecs (code 400) comptent.
@limiter.limit(
    "5 per minute;20 per hour",
    key_func=compte_vise,
    methods=["POST"],
    deduct_when=lambda reponse: reponse.status_code == 400,
)
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


# --- Mot de passe oublié -------------------------------------------------------------

MESSAGE_OUBLI = (
    "Si un compte avec une adresse e-mail confirmée correspond, un lien pour "
    "choisir un nouveau mot de passe vient d'y être envoyé. Pensez à regarder "
    "dans vos spams."
)


@auth.route("/mot-de-passe-oublie", methods=["GET", "POST"])
# Au maximum 3 demandes par heure pour une même adresse (évite d'inonder
# quelqu'un d'e-mails), et 50 par heure sur tout le site.
@limiter.limit("3 per hour", key_func=email_vise, methods=["POST"])
@limiter.limit("50 per hour", key_func=lambda: "oubli", methods=["POST"])
def mot_de_passe_oublie():
    if request.method == "POST":
        email = normaliser_email(request.form.get("email", ""))
        utilisateur = trouver_par_email(email)
        # On n'envoie le lien qu'à une adresse confirmée : sinon, une faute de
        # frappe à l'inscription donnerait le compte au propriétaire de
        # l'adresse mal tapée.
        if utilisateur and utilisateur.email_verifie:
            envoyer_lien_reinitialisation(utilisateur)
        # Toujours le même message, que l'adresse existe ou non : on ne
        # révèle pas quelles adresses ont un compte.
        flash(MESSAGE_OUBLI)
        return redirect(url_for("auth.connexion"))

    return render_template("mot_de_passe_oublie.html")


@auth.route("/reinitialiser/<jeton>", methods=["GET", "POST"])
def reinitialiser(jeton):
    utilisateur = lire_jeton_reinitialisation(jeton)
    if utilisateur is None:
        return render_template("reinitialiser.html", lien_invalide=True), 400

    erreur = None
    if request.method == "POST":
        mot_de_passe = request.form.get("mot_de_passe", "")
        confirmation = request.form.get("confirmation", "")
        erreur = valider_mot_de_passe(mot_de_passe, confirmation)
        if erreur is None:
            # Le mot de passe change, donc son empreinte aussi : ce lien et
            # toutes les sessions ouvertes sur ce compte deviennent invalides.
            utilisateur.definir_mot_de_passe(mot_de_passe)
            db.session.commit()
            logout_user()
            flash("Votre mot de passe a été modifié. Vous pouvez vous connecter.")
            return redirect(url_for("auth.connexion"))

    return render_template(
        "reinitialiser.html",
        erreur=erreur,
        longueur_min=LONGUEUR_MIN_MOT_DE_PASSE,
    ), 400 if erreur else 200


@auth.route("/confirmer-email/<jeton>")
def confirmer_email(jeton):
    utilisateur = lire_jeton_confirmation(jeton)
    if utilisateur is None:
        flash("Ce lien de confirmation est invalide ou a expiré.")
        return redirect(url_for("auth.compte"))
    utilisateur.email_verifie = True
    db.session.commit()
    flash("Votre adresse e-mail est confirmée.")
    return redirect(url_for("auth.compte"))


# --- Mon compte ---------------------------------------------------------------------


def afficher_compte(erreur_email=None, erreur_mot_de_passe=None, email_saisi=None):
    erreur = erreur_email or erreur_mot_de_passe
    return render_template(
        "compte.html",
        erreur_email=erreur_email,
        erreur_mot_de_passe=erreur_mot_de_passe,
        email_saisi=email_saisi,
        longueur_min=LONGUEUR_MIN_MOT_DE_PASSE,
    ), 400 if erreur else 200


@auth.route("/compte")
@login_required
def compte():
    return afficher_compte()


@auth.post("/compte/email")
@login_required
def changer_email():
    email = normaliser_email(request.form.get("email", ""))
    # On redemande le mot de passe : quelqu'un qui profiterait d'un
    # ordinateur resté connecté ne doit pas pouvoir détourner le compte en
    # changeant l'adresse de récupération.
    if not current_user.verifier_mot_de_passe(request.form.get("mot_de_passe", "")):
        return afficher_compte(erreur_email="Mot de passe incorrect.", email_saisi=email)
    erreur = valider_email(email, utilisateur_actuel=current_user)
    if erreur:
        return afficher_compte(erreur_email=erreur, email_saisi=email)

    current_user.email = email
    current_user.email_verifie = False
    db.session.commit()
    if envoyer_lien_confirmation(current_user):
        flash(f"Un e-mail de confirmation a été envoyé à {email}.")
    else:
        flash("L'e-mail de confirmation n'a pas pu être envoyé. Réessayez plus tard.")
    return redirect(url_for("auth.compte"))


@auth.post("/compte/renvoyer-confirmation")
@login_required
@limiter.limit("3 per hour", key_func=utilisateur_connecte)
def renvoyer_confirmation():
    if current_user.email and not current_user.email_verifie:
        if envoyer_lien_confirmation(current_user):
            flash(f"Un nouvel e-mail de confirmation a été envoyé à {current_user.email}.")
        else:
            flash("L'e-mail de confirmation n'a pas pu être envoyé. Réessayez plus tard.")
    return redirect(url_for("auth.compte"))


@auth.post("/compte/mot-de-passe")
@login_required
def changer_mot_de_passe():
    if not current_user.verifier_mot_de_passe(request.form.get("actuel", "")):
        return afficher_compte(erreur_mot_de_passe="Mot de passe actuel incorrect.")
    erreur = valider_mot_de_passe(
        request.form.get("mot_de_passe", ""), request.form.get("confirmation", "")
    )
    if erreur:
        return afficher_compte(erreur_mot_de_passe=erreur)

    utilisateur = current_user._get_current_object()
    utilisateur.definir_mot_de_passe(request.form["mot_de_passe"])
    db.session.commit()
    # Le changement d'empreinte déconnecte toutes les sessions, y compris
    # celle-ci : on reconnecte la personne sur cet appareil uniquement.
    login_user(utilisateur)
    flash("Votre mot de passe a été modifié. Vos autres sessions ont été déconnectées.")
    return redirect(url_for("auth.compte"))
