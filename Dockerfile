# Image de départ : Linux léger avec Python 3.12 et uv déjà installés.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# 1) Installer d'abord les dépendances seules. Docker garde cette étape en
#    cache : tant que pyproject.toml et uv.lock ne changent pas, une
#    reconstruction après une modification du code est quasi instantanée.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

# 2) Copier le code de l'application et l'installer.
COPY . .
RUN uv sync --locked --no-dev

# Lancer l'application avec un utilisateur sans droits administrateur.
RUN useradd --create-home appli && mkdir -p /app/data && chown appli /app/data
USER appli

ENV PATH="/app/.venv/bin:$PATH" \
    CHEMIN_BASE_DE_DONNEES=/app/data/noms.db

EXPOSE 5000

# Gunicorn : un serveur web fait pour tourner en continu
# (contrairement au serveur de développement de "uv run webapp").
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "webapp:app"]
