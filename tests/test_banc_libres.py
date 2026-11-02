

def test_zones_des_erreurs_mur_arrondi_en_morceaux():
    from moteur.banc_coloriage import zones_des_erreurs
    vrai = {"murs": [{"id": "M_arrondi1-0", "debut": [0, 0], "fin": [1, 0], "epaisseur": 0.2},
                     {"id": "M_arrondi1-1", "debut": [1, 0], "fin": [1.5, 0.5], "epaisseur": 0.2}],
            "ouvertures": [], "pieces": []}
    r = {"murs": [{"vrai": "M_arrondi1", "trouve": True, "juste": False, "bouts": 0.5, "axe": 0.05}],
         "ouvertures": [], "pieces": []}
    z = zones_des_erreurs(vrai, r)
    assert z[0]["zone"] == [-0.1, -0.1, 1.6, 0.6]
