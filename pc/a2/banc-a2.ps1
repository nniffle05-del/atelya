# Etape A2-6 : banc de la lecture des PDF (PC).
# A lancer depuis le depot atelya-code :  powershell -ExecutionPolicy Bypass -File pc\a2\banc-a2.ps1 -Phase tout
# Phases : fabriquer, preparer, colorier, pdf, images-cache, images, ocr, tout. -Nombre N : seulement N plans (essai).
# Chemins RELATIFS partout (piege des accents de « Modelisation immobiliere »). Arret au premier code different de 0.
param([string]$Phase = 'tout', [int]$Nombre = 0)
$ErrorActionPreference = 'Continue'
$env:PYTHONIOENCODING = 'utf-8'
$env:OMP_NUM_THREADS = '1'
Set-Location (Join-Path $PSScriptRoot '..\..')
$A = '..\atelya'
$py = "$A\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Output "PLANTE : python introuvable ($py)"; exit 1 }
if (-not (Test-Path "$A\jeu-test-6-13\repartition.json")) { Write-Output "PLANTE : jeu-test-6-13 introuvable"; exit 1 }
$S = if ($Nombre) { "-essai$Nombre" } else { '' }
$N = if ($Nombre) { @('--nombre', "$Nombre") } else { @() }
$suivi = "$A\banc-a2$S.suivi"
function Note($t) { "$(Get-Date -Format 'HH:mm:ss') $t" | Add-Content $suivi -Encoding UTF8; Write-Output $t }
function Verifier($quoi) {
    if ($LASTEXITCODE -ne 0) { Note "PLANTE : $quoi (code=$LASTEXITCODE)"; exit 1 }
    Note "  fin $quoi code=0"
}
function Banc($jeu, $coloriages, $sortie, $options) {
    New-Item -ItemType Directory -Force $sortie | Out-Null
    Note "banc $sortie"
    & $py -m moteur.banc_coloriage $jeu @options --coloriages $coloriages --echelle lue --proportions optique --processus 5 --doutes --sortie $sortie @N *> "$sortie\banc.log"
    Verifier "banc $sortie"
}

if ($Phase -in 'fabriquer', 'tout') {
    Note "fabriquer les PDF du jeu de test -> pdf-test-a2$S"
    & $py -m moteur.generateur.plan_pdf --jeu "$A\jeu-test-6-13" --sortie "$A\pdf-test-a2$S" @N *> "$A\pdf-test-a2$S.log"
    Verifier 'fabriquer'
}
if ($Phase -in 'preparer', 'tout') {
    Note "preparer les PDF pour le banc (tri, page, image 300 dpi, textes) -> jeu-pdf-a2$S"
    & $py -m moteur.generateur.plan_pdf --jeu "$A\jeu-test-6-13" --preparer "$A\pdf-test-a2$S" --sortie "$A\jeu-pdf-a2$S" --processus 5 @N *> "$A\jeu-pdf-a2$S.log"
    Verifier 'preparer'
}
if ($Phase -in 'colorier', 'tout') {
    Note "colorier les PDF avec l'essai 5 (4 angles, carte des doutes) -> coloriages-a2-pdf$S"
    Push-Location $A
    & '.\.venv\Scripts\python.exe' colorier_angles_a3.py --jeu "jeu-pdf-a2$S" --partie test --modele 'resultats-essai-5\atelya-essai-4.pt' --sortie "coloriages-a2-pdf$S" @N *> "coloriages-a2-pdf$S.log"
    $code = $LASTEXITCODE
    Pop-Location
    if ($code -ne 0) { Note "PLANTE : colorier (code=$code)"; exit 1 }
    Note '  fin colorier code=0'
}
if ($Phase -in 'pdf', 'tout') {
    # Les PDF : textes exacts et echelle ecrite sur les pages vectorielles, OCR sur les pages piegees et scannees.
    Banc "$A\jeu-pdf-a2$S" "$A\coloriages-a2-pdf$S\exemples" "$A\banc-a2-pdf$S" @('--partie', 'test', '--textes-pdf')
}
if ($Phase -in 'images-cache', 'tout') {
    # Non-recul sur les images, rapide : memes coloriages et memes echelles lues (cache) que banc-v041-apres-e5.
    $b = "$A\banc-a2-images-cache$S"
    New-Item -ItemType Directory -Force $b | Out-Null
    if (-not (Test-Path "$b\echelles-lues")) { Copy-Item "$A\banc-v041-apres-e5\echelles-lues" "$b\echelles-lues" -Recurse }
    Banc "$A\jeu-test-6-13" "$A\coloriages-a1-apres\exemples" $b @('--partie', 'test')
}
if ($Phase -in 'images', 'tout') {
    # Non-recul sur les images, complet : echelles relues (OCR) avec le nouveau code, sans cache.
    Banc "$A\jeu-test-6-13" "$A\coloriages-a1-apres\exemples" "$A\banc-a2-images$S" @('--partie', 'test')
}
if ($Phase -in 'ocr', 'tout') {
    # Les memes images des pages vectorielles, lues par l'OCR au lieu des textes du PDF : ce que les textes exacts apportent.
    Banc "$A\jeu-pdf-a2$S" "$A\coloriages-a2-pdf$S\exemples" "$A\banc-a2-ocr$S" @('--partie', 'vecto')
}
Note "FINI $Phase"
