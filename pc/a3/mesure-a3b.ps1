# Étape A3 — mesure complète de l’essai 7b (petit œil + murs en biais), à comparer à l'essai 5 (A1).
# À lancer depuis D:\Modélisation immobilière\atelya :  powershell -File mesure-a3b.ps1 -Phase colorier|bancs|vrais|paquet|tout
# Chemins RELATIFS partout (cv2 n'écrit pas dans un chemin avec « é »).
param([string]$Phase = 'tout')
$ErrorActionPreference = 'Continue'
$env:PYTHONIOENCODING = 'utf-8'
$env:OMP_NUM_THREADS = '1'
Set-Location $PSScriptRoot
$py = '.\.venv\Scripts\python.exe'
$suivi = 'mesure-a3b.suivi'
function Note($t) { "$(Get-Date -Format 'HH:mm:ss') $t" | Add-Content $suivi -Encoding UTF8; Write-Output $t }

# Modèles notés : l'essai 7 gardé (s'il existe) et son dernier état ; l'essai 5 seulement sur les jeux biais (nouveaux).
$modeles = [ordered]@{}
if (Test-Path 'resultats-essai-7b\atelya-essai-7.pt') { $modeles['e7'] = 'resultats-essai-7b\atelya-essai-7.pt' }
if (Test-Path 'resultats-essai-7b\atelya-essai-7-dernier.pt') { $modeles['e7d'] = 'resultats-essai-7b\atelya-essai-7-dernier.pt' }
$e5 = 'resultats-essai-5\atelya-essai-4.pt'
# jeu, nom court ; les 4 premiers ont déjà leur banc essai 5 (banc-a1-*-e5)
$jeux = @(
    @('jeu-test-6-13', 'apres'),
    @('donnees\photos-sans-cotes', 'psc'),
    @('donnees\photos-reel-test-cotes', 'reel-cotes'),
    @('donnees\photos-reel-test-sc', 'reel-sc'),
    @('donnees\biais-test-a3', 'biais'),
    @('donnees\biais-photos-test-a3', 'biais-photos'))

function Taches {
    $t = @()
    foreach ($k in $modeles.Keys) { foreach ($j in $jeux) { $t += , @($j[0], $j[1], $k, $modeles[$k]) } }
    foreach ($j in $jeux[4..5]) { $t += , @($j[0], $j[1], 'e5', $e5) }
    return $t
}

if ($Phase -in 'colorier', 'tout') {
    Note "modeles : $($modeles.Keys -join ', ')"
    # Les deux jeux biais de test ne servent qu'à noter : tous leurs plans passent dans la partie « test ».
    Push-Location code-a3
    foreach ($j in @('biais-test-a3', 'biais-photos-test-a3')) {
        & "..\.venv\Scripts\python.exe" -m moteur.generateur repartir "..\donnees\$j" --parts 0,0,1 *> "..\repartir-$j.log"
        Note "repartir $j code=$LASTEXITCODE"
    }
    Pop-Location
    foreach ($t in (Taches)) {
        $sortie = "coloriages-a3-$($t[1])-$($t[2])"
        Note "colorier $($t[0]) avec $($t[2]) -> $sortie"
        & $py colorier_angles_a3.py --jeu $t[0] --partie test --modele $t[3] --sortie $sortie *> "$sortie.log"
        Note "  fin code=$LASTEXITCODE"
    }
}
if ($Phase -in 'bancs', 'tout') {
    Push-Location code-a3
    foreach ($t in (Taches)) {
        $banc = "..\banc-a3-$($t[1])-$($t[2])"
        $ancien = "..\banc-6-17-$($t[1])-e5"
        New-Item -ItemType Directory -Force $banc | Out-Null
        if ((Test-Path "$ancien\echelles-lues") -and -not (Test-Path "$banc\echelles-lues")) { Copy-Item "$ancien\echelles-lues" "$banc\echelles-lues" -Recurse }
        Note "banc $banc"
        & "..\.venv\Scripts\python.exe" -m moteur.banc_coloriage "..\$($t[0])" --partie test --coloriages "..\coloriages-a3-$($t[1])-$($t[2])\exemples" --echelle lue --proportions optique --processus 5 --doutes --sortie $banc *> "$banc\banc.log"
        Note "  fin code=$LASTEXITCODE"
    }
    Pop-Location
}
if ($Phase -in 'vrais', 'tout') {
    foreach ($k in $modeles.Keys) {
        Note "vrais plans (doutes) $k"
        & $py colorier_angles_a3.py --images 'vrais-plans\lot-2026-10-31' --modele $modeles[$k] --sortie "vrais-plans\doutes-a3-$k" *> "vrais-plans\doutes-a3-$k.log"
        Note "  fin code=$LASTEXITCODE"
    }
}
if ($Phase -in 'paquet', 'tout') {
    $tmp = "retour-a3b-$(Get-Date -Format 'MMdd-HHmm')"
    New-Item -ItemType Directory $tmp | Out-Null
    Get-ChildItem -Directory 'banc-a3-*', 'banc-a1-*-e5' | ForEach-Object {
        $d = "$tmp\$($_.Name)"; New-Item -ItemType Directory $d | Out-Null
        Copy-Item "$($_.FullName)\bilan.json", "$($_.FullName)\details.json" $d -ErrorAction SilentlyContinue
        if ($_.Name -like 'banc-a3-biais*') { Copy-Item "$($_.FullName)\logements" "$d\logements" -Recurse -ErrorAction SilentlyContinue }
    }
    Copy-Item 'resultats-essai-7b\bilan.json', 'resultats-essai-7b\historique.json', 'essai-7b.log', 'essai-7b.suivi', 'jeux-a3.suivi', $suivi $tmp -ErrorAction SilentlyContinue
    foreach ($d in (Get-ChildItem -Directory 'vrais-plans\coloriages-lot-2026-10-31-atelya-essai-7*', 'vrais-plans\doutes-a3-*' -ErrorAction SilentlyContinue)) {
        Copy-Item $d.FullName "$tmp\vrais-$($d.Name)" -Recurse
    }
    Compress-Archive -Path "$tmp\*" -DestinationPath "$tmp.zip" -Force
    Note "paquet $tmp.zip $((Get-Item "$tmp.zip").Length) octets"
}
Note "FINI $Phase"
