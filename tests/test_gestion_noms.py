"""Tests de la validation, de la modification et de la suppression des noms."""

NOM_TROP_LONG = "a" * 51


# --- Validation lors de l'ajout ---------------------------------------------


def test_ajout_nom_vide_affiche_une_erreur(client, lire_noms):
    reponse = client.post("/bonjour", data={"nom": "   "})
    assert reponse.status_code == 400
    assert "Le nom ne peut pas être vide." in reponse.text
    assert lire_noms() == []


def test_ajout_nom_trop_long_est_refuse(client, lire_noms):
    reponse = client.post("/bonjour", data={"nom": NOM_TROP_LONG})
    assert reponse.status_code == 400
    assert "ne doit pas dépasser 50 caractères" in reponse.text
    assert lire_noms() == []


def test_ajout_nom_de_50_caracteres_est_accepte(client, lire_noms):
    nom = "a" * 50
    client.post("/bonjour", data={"nom": nom})
    assert lire_noms() == [nom]


def test_saisie_conservee_apres_une_erreur(client):
    # L'utilisateur ne doit pas avoir à tout retaper.
    reponse = client.post("/bonjour", data={"nom": NOM_TROP_LONG})
    assert f'value="{NOM_TROP_LONG}"' in reponse.text


def test_liste_affiche_les_boutons_modifier_et_supprimer(client, id_ben):
    page = client.get("/bonjour").text
    assert f"/noms/{id_ben}/modifier" in page
    assert f"/noms/{id_ben}/supprimer" in page


# --- Modification -------------------------------------------------------------


def test_page_modifier_affiche_le_nom_actuel(client, id_ben):
    reponse = client.get(f"/noms/{id_ben}/modifier")
    assert reponse.status_code == 200
    assert 'value="Ben"' in reponse.text


def test_modifier_change_le_nom(client, id_ben, lire_noms):
    reponse = client.post(f"/noms/{id_ben}/modifier", data={"nom": "Benjamin"})
    assert reponse.status_code == 302
    assert reponse.headers["Location"] == "/bonjour"
    assert lire_noms() == ["Benjamin"]


def test_modifier_avec_nom_vide_est_refuse(client, id_ben, lire_noms):
    reponse = client.post(f"/noms/{id_ben}/modifier", data={"nom": ""})
    assert reponse.status_code == 400
    assert "Le nom ne peut pas être vide." in reponse.text
    assert lire_noms() == ["Ben"]


def test_modifier_avec_nom_trop_long_est_refuse(client, id_ben, lire_noms):
    reponse = client.post(f"/noms/{id_ben}/modifier", data={"nom": NOM_TROP_LONG})
    assert reponse.status_code == 400
    assert lire_noms() == ["Ben"]


def test_modifier_un_nom_inexistant_renvoie_404(client):
    assert client.get("/noms/999/modifier").status_code == 404
    assert client.post("/noms/999/modifier", data={"nom": "X"}).status_code == 404


# --- Suppression ----------------------------------------------------------------


def test_supprimer_retire_le_nom(client, id_ben, lire_noms):
    reponse = client.post(f"/noms/{id_ben}/supprimer")
    assert reponse.status_code == 302
    assert lire_noms() == []


def test_supprimer_ne_touche_pas_aux_autres_noms(client, id_ben, lire_noms):
    client.post("/bonjour", data={"nom": "Alice"})
    client.post(f"/noms/{id_ben}/supprimer")
    assert lire_noms() == ["Alice"]


def test_supprimer_un_nom_inexistant_renvoie_404(client):
    assert client.post("/noms/999/supprimer").status_code == 404


def test_supprimer_par_un_simple_lien_est_refuse(client, id_ben, lire_noms):
    # 405 = méthode non autorisée : seul le bouton (POST) peut supprimer.
    assert client.get(f"/noms/{id_ben}/supprimer").status_code == 405
    assert lire_noms() == ["Ben"]
