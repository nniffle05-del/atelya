# Essai 8 : essai 5 + oeil DINOv2 + vrais plans (PC). A lancer depuis le depot atelya-code :
#   powershell -ExecutionPolicy Bypass -File pc\essai8\petits-essais-8.ps1 -Phase jeu|eclair|T0|T1|T2|long
# Regles : petits essais de 25 min avant UN long essai (duree en minutes) ; chemins RELATIFS (piege des accents) ;
# arret au premier code different de 0 avec une ligne "PLANTE". Suivi : ..\atelya\essai8.suivi
# Le jeu refuse tout plan d'examen (verites\repartition-vrais-plans.json).
param([string]$Phase = 'eclair', [double]$PartVrais = 0.3, [string]$Depart = 'resultats-essai-5\atelya-essai-4.pt', [int]$Minutes = 180)
$ErrorActionPreference = 'Continue'
$env:PYTHONIOENCODING = 'utf-8'
$env:OMP_NUM_THREADS = '1'
Set-Location (Join-Path $PSScriptRoot '..\..')
$A = '..\atelya'
$suivi = "$A\essai8.suivi"
function Note($t) { "$(Get-Date -Format 'HH:mm:ss') $t" | Add-Content $suivi -Encoding UTF8; Write-Output $t }
if (-not (Test-Path "$A\.venv\Scripts\python.exe")) { Note 'PLANTE : python introuvable'; exit 1 }

if ($Phase -eq 'jeu') {
    & "$A\.venv\Scripts\python.exe" outils\atelya\preparer_jeu_vrais.py --verites "$A\verites-lot2" --sortie "$A\donnees\vrais-2026-11-05" --variantes 12 --controle 8 *> "$A\essai8-jeu.log"
    if ($LASTEXITCODE -ne 0) { Note "PLANTE : jeu des vrais plans (code=$LASTEXITCODE)"; exit 1 }
    Note 'fin jeu code=0'
    exit 0
}

Set-Location $A
$suivi = 'essai8.suivi'
$py = '.venv\Scripts\python.exe'
if (-not (Test-Path 'donnees\vrais-2026-11-05\repartition.json')) { Note 'PLANTE : lancer d''abord -Phase jeu'; exit 1 }
# Recette de l'essai 7b (pas prudent, maitre, BatchNorm figes), plus les vrais plans.
$base = @('entrainer_essai8.py', '--jeu', 'donnees\jeu-10000',
    '--jeu-photos', 'donnees\photos-app-cotes', 'donnees\photos-app-sans-cotes', 'donnees\photos-reel-cotes', 'donnees\photos-reel-sans-cotes',
    '--jeu-monde', 'donnees\monde-6-19',
    '--jeu-biais', 'donnees\biais-a3', 'donnees\biais-monde-a3', 'donnees\biais-photos-a3', '--part-biais', '0.15',
    '--jeu-vrais', 'donnees\vrais-2026-11-05',
    '--processus', '1', '--figer-bn', '--poids-maitre', '3.0', '--poids-escalier', '3.0',
    '--part-monde', '0.15', '--part-photos', '0.3', '--lr', '5e-5', '--lr-oeil', '1e-4', '--oeil', 'vits14')
function Essai($nom, $minutes, $vrais, $dep, $autres) {
    $sortie = "resultats-essai-8-$nom"
    New-Item -ItemType Directory -Force $sortie | Out-Null
    Note "debut $nom : $minutes min, part vrais $vrais, depart $dep"
    & $py @base --reprendre $dep --part-vrais $vrais --minutes $minutes --sortie $sortie @autres *> "$sortie\journal.log"
    if ($LASTEXITCODE -ne 0) { Note "PLANTE : $nom (code=$LASTEXITCODE)"; exit 1 }
    Get-Content "$sortie\journal.log" | Select-String 'BILAN|AUCUN|RETOUR' | ForEach-Object { "   $($_.Line)" } | Add-Content $suivi -Encoding UTF8
    Note "fin $nom code=0"
}
switch ($Phase) {
    'eclair' { Essai 'eclair' 2 0.3 'resultats-essai-5\atelya-essai-4.pt' @('--nb-val', '20') }
    'T0'     { Essai 'T0' 25 0.3 'resultats-essai-5\atelya-essai-4.pt' @() }
    'T1'     { Essai 'T1' 25 0.5 'resultats-essai-5\atelya-essai-4.pt' @() }
    'T2'     { Essai 'T2' 25 0.3 'resultats-essai-7b\atelya-essai-7.pt' @() }
    'long'   { Essai 'long' $Minutes $PartVrais $Depart @() }
    default  { Note "PLANTE : phase inconnue $Phase"; exit 1 }
}
Note "FINI $Phase"
