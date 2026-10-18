"""Les pages de l'application.

Un Blueprint ("plan") regroupe des pages. Il est branché sur l'application
dans __init__.py. Dans les templates, on désigne une page par
"pages.<nom de la fonction>", par exemple url_for("pages.bonjour").
"""

from flask import Blueprint, abort, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import selectinload

from .auth import login_manager
from .modeles import LONGUEUR_MAX_NOM, Nom, db

pages = Blueprint("pages", __name__)


def valider_nom(nom):
    """Renvoie un message d'erreur si le nom est invalide, sinon None."""
    if not nom:
        return "Le nom ne peut pas être vide."
    if len(nom) > LONGUEUR_MAX_NOM:
        return f"Le nom ne doit pas dépasser {LONGUEUR_MAX_NOM} caractères."
    return None


def lister_noms():
    """Renvoie tous les noms, du plus récent au plus ancien, avec leur auteur."""
    # selectinload : charge les auteurs en une seule requête supplémentaire,
    # au lieu d'une requête par nom affiché (problème dit "N+1").
    return db.session.scalars(
        db.select(Nom).options(selectinload(Nom.auteur)).order_by(Nom.id.desc())
    ).all()


def verifier_auteur(ligne):
    """Interdit l'accès (erreur 403) si l'utilisateur connecté n'est pas l'auteur.

    Cacher les boutons dans la page ne suffit pas : n'importe qui peut taper
    l'adresse /noms/3/supprimer lui-même. La vérification doit donc toujours
    être faite ici, côté serveur.
    """
    if ligne.auteur_id != current_user.id:
        abort(403)


# Chaque fonction décorée par @pages.route répond à une adresse (URL).
@pages.route("/")
def accueil():
    return render_template("accueil.html")


# Page de santé : l'hébergeur l'appelle régulièrement pour vérifier que
# l'application et sa base de données fonctionnent. En cas d'erreur, la
# page renvoie un code 500 et l'hébergeur redémarre l'application.
@pages.route("/sante")
def sante():
    db.session.execute(db.text("SELECT 1"))
    return {"etat": "ok"}


# Cette page accepte GET (afficher le formulaire) et POST (formulaire envoyé).
@pages.route("/bonjour", methods=["GET", "POST"])
def bonjour():
    if request.method == "POST":
        # Tout le monde peut voir la liste, mais seules les personnes
        # connectées peuvent ajouter un nom : les autres sont envoyées
        # vers la page de connexion.
        if not current_user.is_authenticated:
            return login_manager.unauthorized()

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

        # On crée un objet Nom dont l'auteur est la personne connectée,
        # on l'ajoute à la session, puis commit() l'enregistre dans la base.
        db.session.add(Nom(nom=nom, auteur_id=current_user.id))
        db.session.commit()
        # Redirection après l'envoi : recharger la page (F5) ne renverra
        # pas le formulaire une deuxième fois.
        return redirect(url_for("pages.bonjour", nom=nom))

    return render_template(
        "bonjour.html",
        nom=request.args.get("nom"),
        noms=lister_noms(),
        longueur_max=LONGUEUR_MAX_NOM,
    )


# <int:id_nom> récupère le numéro présent dans l'adresse,
# par exemple /noms/3/modifier donne id_nom = 3.
@pages.route("/noms/<int:id_nom>/modifier", methods=["GET", "POST"])
@login_required
def modifier(id_nom):
    # Cherche le nom par son id ; s'il n'existe pas, page "introuvable" (404).
    ligne = db.get_or_404(Nom, id_nom)
    verifier_auteur(ligne)

    erreur = None
    saisie = ligne.nom
    if request.method == "POST":
        saisie = request.form.get("nom", "").strip()
        erreur = valider_nom(saisie)
        if erreur is None:
            # Il suffit de changer l'attribut : SQLAlchemy fait l'UPDATE.
            ligne.nom = saisie
            db.session.commit()
            return redirect(url_for("pages.bonjour"))

    return render_template(
        "modifier.html",
        id_nom=id_nom,
        saisie=saisie,
        erreur=erreur,
        longueur_max=LONGUEUR_MAX_NOM,
    ), 400 if erreur else 200


# Supprimer modifie les données : on n'accepte que POST (un bouton de
# formulaire), jamais un simple lien GET qu'un robot pourrait suivre.
@pages.post("/noms/<int:id_nom>/supprimer")
@login_required
def supprimer(id_nom):
    ligne = db.get_or_404(Nom, id_nom)
    verifier_auteur(ligne)
    db.session.delete(ligne)
    db.session.commit()
    return redirect(url_for("pages.bonjour"))
