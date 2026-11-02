"""Résumé des bancs 6-17 -> resultats-6-17.txt et retour-6-17.zip (lancer depuis atelya)."""
import hashlib, json, os, zipfile

JEUX = ['reel-cotes', 'reel-sc', 'psc', 'apres']


def avant(j):
    if j == 'reel-cotes' and os.path.exists('banc-6-16-reel-cotes-e5c'):
        return 'banc-6-16-reel-cotes-e5c'
    return f'banc-6-16-{j}-e5'


def lire(d):
    b = json.load(open(os.path.join(d, 'bilan.json'), encoding='utf-8'))
    det = json.load(open(os.path.join(d, 'details.json'), encoding='utf-8'))
    e = b['echelle_lue']['tous']
    erreurs = []
    for x in det:
        el = x.get('echelle_lue') or {}
        if x.get('echelle_a_verifier') or not el:
            continue
        ec = [v for v in (el.get('ecart_largeur_pct'), el.get('ecart_hauteur_pct')) if v is not None]
        if ec and max(abs(v) for v in ec) > 3:
            erreurs.append(f"{x['plan']} niveau {x['niveau']} source {el.get('source')} écarts largeur "
                           f"{el.get('ecart_largeur_pct')} % / hauteur {el.get('ecart_hauteur_pct')} %")
    return {'niveaux': b['niveaux_notes'], 'lue': e['echelle_lue'], 'lue_pct': e['lue_pct'], 'a_verifier': e['a_verifier'],
            'plus3': e['plus_de_3_pct'], 'murs': b['murs']['justes_pct'], 'ouv': b['ouvertures']['justes_pct'],
            'pieces': b['pieces']['trouvees_pct'], 'type': b['pieces']['bon_type_pct'], 'parfaits': b['plans_parfaits_pct'],
            'nettoyes': sum(1 for x in det if x.get('coloriage_nettoye')), 'erreurs': erreurs}


lignes = ['RÉSULTATS 6-17 : lecture par morceaux, taches au bord, cotes dans un seul sens confirmées (avant 6-16 -> après 6-17)', '']
total_plus3 = 0
for j in JEUX:
    da, dp = avant(j), f'banc-6-17-{j}-e5'
    a, p = lire(da), lire(dp)
    total_plus3 += p['plus3']
    lignes.append(f'== {j} : {da} -> {dp} ({p["niveaux"]} niveaux)')
    lignes.append(f"  échelle lue        : {a['lue']} ({a['lue_pct']} %) -> {p['lue']} ({p['lue_pct']} %)")
    lignes.append(f"  à vérifier         : {a['a_verifier']} -> {p['a_verifier']}")
    lignes.append(f"  plus de 3 %        : {a['plus3']} -> {p['plus3']}" + ('' if p['plus3'] == 0 else '   <<< DOIT RESTER 0'))
    for k, t in (('murs', 'murs justes %'), ('ouv', 'ouvertures justes %'), ('pieces', 'pièces trouvées %'),
                 ('type', 'bon type %'), ('parfaits', 'parfaits %')):
        lignes.append(f"  {t:<19}: {a[k]} -> {p[k]} ({p[k] - a[k]:+.1f})")
    lignes.append(f"  coloriages nettoyés: {a['nettoyes']} -> {p['nettoyes']}")
    for err in p['erreurs']:
        lignes.append(f'    ERREUR > 3 % : {err}')
    lignes.append('')
lignes.append(f"ERREURS > 3 % APRÈS, tous jeux : {total_plus3} {'OK' if total_plus3 == 0 else 'PAS OK'}")
txt = '\n'.join(lignes) + '\n'
open('resultats-6-17.txt', 'w', encoding='utf-8').write(txt)
print(txt)

with zipfile.ZipFile('retour-6-17.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for j in JEUX:
        for f in ('bilan.json', 'details.json'):
            z.write(os.path.join(f'banc-6-17-{j}-e5', f), f'banc-6-17-{j}-e5/{f}')
    z.write('resultats-6-17.txt')
data = open('retour-6-17.zip', 'rb').read()
print(f'retour-6-17.zip : {len(data)} octets, SHA-256 {hashlib.sha256(data).hexdigest()}')
