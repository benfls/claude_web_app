"""Les modèles : la description des tables de la base, sous forme de classes.

Avec SQLAlchemy, une classe = une table, un attribut = une colonne,
et un objet de cette classe = une ligne de la table.
"""

from datetime import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from werkzeug.security import check_password_hash, generate_password_hash

# Nombre maximum de caractères autorisés pour un nom.
LONGUEUR_MAX_NOM = 50

# Longueur maximum d'un nom d'utilisateur.
LONGUEUR_MAX_NOM_UTILISATEUR = 30


class Base(DeclarativeBase):
    # Donne un nom prévisible aux contraintes (ex. "uq_utilisateurs_nom_utilisateur").
    # Les migrations en ont besoin pour pouvoir les modifier plus tard avec SQLite.
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


# "db" donne accès à la base : db.session pour lire et écrire.
db = SQLAlchemy(model_class=Base)


class Nom(db.Model):
    __tablename__ = "noms"

    # Mapped[int] : la colonne contient un entier.
    # primary_key=True : c'est l'identifiant unique de chaque ligne,
    # attribué automatiquement (1, 2, 3...).
    id: Mapped[int] = mapped_column(primary_key=True)

    # Le texte du nom, limité à LONGUEUR_MAX_NOM caractères.
    nom: Mapped[str] = mapped_column(String(LONGUEUR_MAX_NOM))

    # La date d'ajout, remplie automatiquement avec l'heure actuelle.
    date_ajout: Mapped[datetime] = mapped_column(default=datetime.now)

    def __repr__(self):
        # Affichage lisible quand on fait print(un_nom).
        return f"<Nom {self.id} {self.nom!r}>"


# UserMixin ajoute ce dont Flask-Login a besoin (is_authenticated, get_id...).
class Utilisateur(UserMixin, db.Model):
    __tablename__ = "utilisateurs"

    id: Mapped[int] = mapped_column(primary_key=True)

    # unique=True : deux comptes ne peuvent pas avoir le même nom.
    nom_utilisateur: Mapped[str] = mapped_column(
        String(LONGUEUR_MAX_NOM_UTILISATEUR), unique=True
    )

    # Jamais le mot de passe lui-même : seulement son empreinte (hash).
    mot_de_passe_hash: Mapped[str] = mapped_column(String(256))

    date_creation: Mapped[datetime] = mapped_column(default=datetime.now)

    def definir_mot_de_passe(self, mot_de_passe):
        """Calcule et enregistre l'empreinte du mot de passe."""
        self.mot_de_passe_hash = generate_password_hash(mot_de_passe)

    def verifier_mot_de_passe(self, mot_de_passe):
        """Renvoie True si le mot de passe correspond à l'empreinte."""
        return check_password_hash(self.mot_de_passe_hash, mot_de_passe)

    def __repr__(self):
        return f"<Utilisateur {self.id} {self.nom_utilisateur!r}>"
