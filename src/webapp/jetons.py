"""Jetons secrets envoyés par e-mail (liens de réinitialisation et de confirmation).

Un jeton contient quelques données (l'id du compte...) et une signature
calculée avec la SECRET_KEY : impossible d'en fabriquer un ou d'en modifier
une lettre sans connaître la clé. Il contient aussi sa date de création, ce
qui permet de le refuser une fois trop ancien.

Attention : le contenu d'un jeton est signé, pas chiffré. N'y mettre que des
données qui peuvent être lues sans danger.
"""

from flask import current_app
from itsdangerous import BadSignature, URLSafeTimedSerializer

from .modeles import Utilisateur, db

# Durée de validité des liens envoyés par e-mail, en secondes.
DUREE_LIEN_REINITIALISATION = 60 * 60  # 1 heure
DUREE_LIEN_CONFIRMATION = 2 * 24 * 60 * 60  # 2 jours


def serialiseur(usage):
    """Outil qui signe et vérifie les jetons.

    "usage" (le sel) rend un jeton utilisable pour un seul usage : un jeton
    de confirmation d'e-mail ne peut pas servir à réinitialiser un mot de passe.
    """
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=usage)


# --- Réinitialisation du mot de passe ---------------------------------------------


def creer_jeton_reinitialisation(utilisateur):
    # L'empreinte du mot de passe actuel rend le lien utilisable une seule
    # fois : dès que le mot de passe change, elle ne correspond plus.
    donnees = {"id": utilisateur.id, "empreinte": utilisateur.empreinte_mot_de_passe()}
    return serialiseur("reinitialisation-mot-de-passe").dumps(donnees)


def lire_jeton_reinitialisation(jeton):
    """Renvoie l'utilisateur si le jeton est valide, sinon None."""
    try:
        donnees = serialiseur("reinitialisation-mot-de-passe").loads(
            jeton, max_age=DUREE_LIEN_REINITIALISATION
        )
    except BadSignature:
        # Jeton modifié, inventé ou expiré.
        return None
    utilisateur = db.session.get(Utilisateur, donnees["id"])
    if utilisateur is None or utilisateur.empreinte_mot_de_passe() != donnees["empreinte"]:
        # Compte supprimé, ou lien déjà utilisé (mot de passe changé depuis).
        return None
    return utilisateur


# --- Confirmation de l'adresse e-mail ----------------------------------------------


def creer_jeton_confirmation(utilisateur):
    donnees = {"id": utilisateur.id, "email": utilisateur.email}
    return serialiseur("confirmation-email").dumps(donnees)


def lire_jeton_confirmation(jeton):
    """Renvoie l'utilisateur si le jeton est valide, sinon None."""
    try:
        donnees = serialiseur("confirmation-email").loads(
            jeton, max_age=DUREE_LIEN_CONFIRMATION
        )
    except BadSignature:
        return None
    utilisateur = db.session.get(Utilisateur, donnees["id"])
    # Le lien ne confirme que l'adresse à laquelle il a été envoyé : s'il
    # a changé d'adresse depuis, l'ancien lien ne vaut plus rien.
    if utilisateur is None or utilisateur.email != donnees["email"]:
        return None
    return utilisateur
