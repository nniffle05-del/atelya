# Étape A3 — banc de contrôle : qui fait reculer les murs, le modèle 7b ou le nouveau traducteur (murs en biais) ?
# 1) coloriages de l'essai 5 (A1) notés avec le NOUVEAU code (code-a3)  2) coloriages 7b notés avec l'ANCIEN code (code-a1)
# À lancer depuis D:\Modélisation immobilière\atelya :  powershell -File controle-a3b.ps1
$ErrorActionPreference = 'Continue'
$env:PYTHONIOENCODING = 'utf-8'
$env:OMP_NUM_THREADS = '1'
Set-Location $PSScriptRoot
$A = $PSScriptRoot
$suivi = "$A\controle-a3b.suivi"
function Note($t) { "$(Get-Date -Format 'HH:mm:ss') $t" | Add-Content $suivi -Encoding UTF8; Write-Output $t }
$jeux = @(@('jeu-test-6-13', 'apres'), @('donnees\photos-sans-cotes', 'psc'), @('donnees\photos-reel-test-cotes', 'reel-cotes'), @('donnees\photos-reel-test-sc', 'reel-sc'))
$taches = @()
# Les 2 bancs biais de l'essai 7b qui avaient planté (mur arrondi en morceaux, corrigé dans code-a3)
$taches += , @('code-a3', 'donnees\biais-test-a3', 'coloriages-a3-biais-e7', 'banc-a3-biais-e7', 'x')
$taches += , @('code-a3', 'donnees\biais-photos-test-a3', 'coloriages-a3-biais-photos-e7', 'banc-a3-biais-photos-e7', 'x')
foreach ($j in $jeux) {
    $taches += , @('code-a3', $j[0], "coloriages-a1-$($j[1])", "banc-ctl-$($j[1])-e5-codea3", "banc-6-17-$($j[1])-e5")
    $taches += , @('code-a1', $j[0], "coloriages-a3-$($j[1])-e7", "banc-ctl-$($j[1])-e7-codea1", "banc-6-17-$($j[1])-e5")
}
foreach ($t in $taches) {
    $banc = "$A\$($t[3])"
    New-Item -ItemType Directory -Force $banc | Out-Null
    if ((Test-Path "$A\$($t[4])\echelles-lues") -and -not (Test-Path "$banc\echelles-lues")) { Copy-Item "$A\$($t[4])\echelles-lues" "$banc\echelles-lues" -Recurse }
    Note "banc $($t[3]) ($($t[0]), $($t[2]))"
    Push-Location "$A\$($t[0])"
    & "$A\.venv\Scripts\python.exe" -m moteur.banc_coloriage "..\$($t[1])" --partie test --coloriages "..\$($t[2])\exemples" --echelle lue --proportions optique --processus 5 --doutes --sortie "..\$($t[3])" *> "$banc\banc.log"
    Note "  fin code=$LASTEXITCODE"
    Pop-Location
}
Note "FINI controle"
