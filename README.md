# webapp

[![CI](https://github.com/benfls/claude_web_app/actions/workflows/ci.yml/badge.svg)](https://github.com/benfls/claude_web_app/actions/workflows/ci.yml)

Application web simple en Python avec [Flask](https://flask.palletsprojects.com/) :
une liste de noms que les utilisateurs connectés peuvent ajouter, modifier et
supprimer.

- Base de données SQLite, via Flask-SQLAlchemy et Flask-Migrate
- Comptes utilisateurs avec Flask-Login, protection CSRF avec Flask-WTF
- Dépendances gérées avec [uv](https://docs.astral.sh/uv/)

## Configuration

Copiez le modèle de configuration, puis remplissez `SECRET_KEY` :

```bash
cp .env.example .env
python3 -c "import secrets; print(secrets.token_hex(32))"   # génère une clé
```

## Lancer l'application

**Avec Docker** (recommandé) :

```bash
docker compose up -d --build
```

**Sans Docker**, pour le développement :

```bash
uv run webapp
```

Dans les deux cas, le site est accessible sur <http://localhost:5000>.
Les migrations de la base de données s'appliquent automatiquement au démarrage.

## Tests

```bash
uv run pytest
```

Pour les lancer sur PostgreSQL (la base est vidée par les tests) :

```bash
TEST_DATABASE_URL=postgresql+psycopg://utilisateur:motdepasse@localhost:5432/tests uv run pytest
```

Les tests sont aussi lancés automatiquement par GitHub Actions à chaque push,
sur SQLite et sur PostgreSQL (voir [.github/workflows/ci.yml](.github/workflows/ci.yml)),
ainsi que la construction et le démarrage de l'image Docker.

## Déploiement

L'application est hébergée sur [Render](https://render.com), configuré par
[render.yaml](render.yaml) : un service web (image Docker) et une base
PostgreSQL, dans la région de Francfort.

- Chaque push sur `main` est déployé automatiquement, une fois la CI au vert.
- Les migrations s'appliquent au démarrage du conteneur.
- Render vérifie que le site fonctionne grâce à la page `/sante`.

Offre gratuite : le site se met en veille après 15 minutes sans visite (environ
une minute pour se réveiller), et la base PostgreSQL gratuite expire 30 jours
après sa création.

## Modifier la structure de la base

1. Modifier les modèles dans `src/webapp/modeles.py`
2. Générer la migration :
   `uv run flask --app webapp db migrate -m "Description du changement"`
3. Relire le script créé dans `src/webapp/migrations/versions/`
4. Lancer les tests, puis commiter le script avec le code
