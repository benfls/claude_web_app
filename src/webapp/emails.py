"""Envoi des e-mails.

Trois modes, choisis par la configuration EMAIL_MODE :
- "brevo"   : vrai envoi, par l'API web de Brevo (en production) ;
- "console" : pas d'envoi, l'e-mail s'affiche dans le terminal (en local) ;
- "test"    : pas d'envoi, l'e-mail est rangé dans boite_de_test (tests).

Pourquoi une API web et pas SMTP (l'envoi "classique") ? L'offre gratuite
de Render bloque les ports SMTP.
"""

import requests
from flask import current_app, url_for

URL_API_BREVO = "https://api.brevo.com/v3/smtp/email"

# En mode "test", les e-mails "envoyés" sont rangés ici pour que les tests
# puissent les lire.
boite_de_test = []


def lien_absolu(page, **valeurs):
    """Adresse complète d'une page, à mettre dans un e-mail.

    Sécurité : on construit l'adresse à partir de ADRESSE_DU_SITE (fixée dans
    la configuration), et non à partir de l'adresse demandée par le visiteur.
    Sinon, un pirate pourrait faire croire au site qu'il s'appelle
    "site-pirate.com" : le lien de réinitialisation envoyé à sa victime
    pointerait vers son site, et il récupérerait le jeton secret.
    """
    return current_app.config["ADRESSE_DU_SITE"].rstrip("/") + url_for(page, **valeurs)


def envoyer_email(destinataire, sujet, texte):
    """Envoie un e-mail. Renvoie True si l'envoi a réussi, False sinon."""
    mode = current_app.config["EMAIL_MODE"]

    if mode == "test":
        boite_de_test.append({"destinataire": destinataire, "sujet": sujet, "texte": texte})
        return True

    if mode == "console":
        print(
            f"\n===== E-MAIL (simulé, non envoyé) pour {destinataire} =====\n"
            f"Sujet : {sujet}\n\n{texte}\n"
            "=============================================\n",
            flush=True,
        )
        return True

    try:
        reponse = requests.post(
            URL_API_BREVO,
            headers={
                "api-key": current_app.config["BREVO_API_KEY"],
                "accept": "application/json",
            },
            json={
                "sender": {
                    "name": current_app.config["NOM_EXPEDITEUR"],
                    "email": current_app.config["EMAIL_EXPEDITEUR"],
                },
                "to": [{"email": destinataire}],
                "subject": sujet,
                "textContent": texte,
            },
            # Ne pas bloquer la page plus de 10 secondes si Brevo ne répond pas.
            timeout=10,
        )
        # Déclenche une erreur si Brevo a refusé l'envoi (clé invalide...).
        reponse.raise_for_status()
        return True
    except requests.RequestException as erreur:
        # On note l'erreur dans les logs (sans l'adresse, donnée personnelle).
        current_app.logger.error("Échec de l'envoi d'un e-mail : %s", erreur)
        return False
