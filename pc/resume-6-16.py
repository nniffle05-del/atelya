"""Résumé des bancs 6-16 -> resultats-6-16.txt (lancer depuis atelya)."""
import json, os

BANCS = [
    ('reel-sc', 'banc-6-16-reel-sc-e4g', 'banc-6-16-reel-sc-e5'),
    ('reel-cotes', 'banc-6-16-reel-cotes-e4g', 'banc-6-16-reel-cotes-e5'),
    ('psc', 'banc-6-16-psc-e4g', 'banc-6-16-psc-e5'),
    ('1066 anciens', 'banc-6-16-apres-e4g', 'banc-6-16-apres-e5'),
]


def lire(d):
    p = os.path.join(d, 'bilan.json')
    if not os.path.exists(p):
        return None
    b = json.load(open(p, encoding='utf-8'))
    det = json.load(open(os.path.join(d, 'details.json'), encoding='utf-8'))
    e = b['echelle_lue']['tous']
    erreurs = []
    douteux = 0
    for x in det:
        if x.get('coloriage_douteux') or (x.get('echelle_lue') or {}).get('coloriage_douteux'):
            douteux += 1
        el = x.get('echelle_lue') or {}
        if x.get('echelle_a_verifier') or not el:
            continue
        ec = [abs(v) for v in (el.get('ecart_largeur_pct'), el.get('ecart_hauteur_pct')) if v is not None]
        if ec and max(ec) > 3:
            pire = max((v for v in (el.get('ecart_largeur_pct'), el.get('ecart_hauteur_pct')) if v is not None), key=abs)
            erreurs.append(f"{x['plan']}-n{x['niveau']} {pire:+.1f}% {el.get('source')}")
    return {
        'niveaux': b['niveaux_notes'], 'rates': b['niveaux_rates'],
        'murs': b['murs']['justes_pct'], 'ouv': b['ouvertures']['justes_pct'],
        'pieces': b['pieces']['trouvees_pct'], 'type': b['pieces']['bon_type_pct'],
        'parfaits': b['plans_parfaits_pct'], 'lue': e['echelle_lue'], 'lue_pct': e['lue_pct'],
        'plus3': e['plus_de_3_pct'], 'a_verifier': e['a_verifier'], 'douteux': douteux,
        'erreurs': erreurs,
    }


lignes = ['RÉSULTATS 6-16 : essai 4 (avec garde-fous) contre essai 5', '']
tete = f"{'jeu':<14}{'essai':<7}{'murs':>7}{'ouv.':>7}{'pièces':>8}{'type':>7}{'parf.':>7}{'éch. lue':>14}{'>3%':>5}{'à vér.':>8}{'douteux':>9}"
lignes.append(tete)
res = {}
for nom, d4, d5 in BANCS:
    for essai, d in (('e4', d4), ('e5', d5)):
        r = lire(d)
        res[(nom, essai)] = r
        if r is None:
            lignes.append(f"{nom:<14}{essai:<7}  (pas de résultat : {d})")
            continue
        lignes.append(f"{nom:<14}{essai:<7}{r['murs']:>7.1f}{r['ouv']:>7.1f}{r['pieces']:>8.1f}{r['type']:>7.1f}{r['parfaits']:>7.1f}"
                      f"{r['lue']:>6} ({r['lue_pct']:>4.1f}%){r['plus3']:>5}{r['a_verifier']:>8}{r['douteux']:>9}")
lignes.append('')
lignes.append('ERREURS D\'ÉCHELLE > 3 %')
for (nom, essai), r in res.items():
    if r and r['erreurs']:
        lignes.append(f"{nom} {essai} ({len(r['erreurs'])}) : " + ' ; '.join(r['erreurs']))
lignes.append('')
a4, a5 = res[('1066 anciens', 'e4')], res[('1066 anciens', 'e5')]
if a4 and a5:
    lignes.append('GARDE-FOUS DE DÉCISION (1 066 anciens, essai 5 vs essai 4, recul max 0,5 point)')
    for k, t in (('murs', 'murs justes'), ('ouv', 'ouvertures justes'), ('lue_pct', 'échelle lue %')):
        diff = a5[k] - a4[k]
        lignes.append(f"  {t} : {a4[k]:.1f} -> {a5[k]:.1f} ({diff:+.1f}) {'OK' if diff >= -0.5 else 'RECUL'}")
    tot = sum(r['plus3'] for (n, e), r in res.items() if r and e == 'e5')
    lignes.append(f"  erreurs > 3 % essai 5, tous jeux : {tot} {'OK' if tot == 0 else 'PAS OK'}")
txt = '\n'.join(lignes)
open('resultats-6-16.txt', 'w', encoding='utf-8').write(txt + '\n')
print(txt)
