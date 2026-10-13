"""Les pages de l'application.

Un Blueprint ("plan") regroupe des pages. Il est branché sur l'application
dans __init__.py. Dans les templates, on désigne une page par
"pages.<nom de la fonction>", par exemple url_for("pages.bonjour").
"""

from flask import Blueprint, redirect, render_template, request, url_for

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
    """Renvoie tous les noms, du plus récent au plus ancien."""
    return db.session.scalars(db.select(Nom).order_by(Nom.id.desc())).all()


# Chaque fonction décorée par @pages.route répond à une adresse (URL).
@pages.route("/")
def accueil():
    return render_template("accueil.html")


# Cette page accepte GET (afficher le formulaire) et POST (formulaire envoyé).
@pages.route("/bonjour", methods=["GET", "POST"])
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

        # On crée un objet Nom, on l'ajoute à la session, puis commit()
        # l'enregistre réellement dans la base.
        db.session.add(Nom(nom=nom))
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
def modifier(id_nom):
    # Cherche le nom par son id ; s'il n'existe pas, page "introuvable" (404).
    ligne = db.get_or_404(Nom, id_nom)

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
def supprimer(id_nom):
    db.session.delete(db.get_or_404(Nom, id_nom))
    db.session.commit()
    return redirect(url_for("pages.bonjour"))
