"""Les modèles : la description des tables de la base, sous forme de classes.

Avec SQLAlchemy, une classe = une table, un attribut = une colonne,
et un objet de cette classe = une ligne de la table.
"""

from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Nombre maximum de caractères autorisés pour un nom.
LONGUEUR_MAX_NOM = 50


class Base(DeclarativeBase):
    pass


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
