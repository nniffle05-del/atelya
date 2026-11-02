# Essai 6e sur le PC : entraînement 180 min, puis coloriages et 4 bancs, enchaînés seuls.
# Lancer depuis D:\Modélisation immobilière\atelya (détaché).
$ErrorActionPreference = 'Continue'
$env:PYTHONIOENCODING = 'utf-8'
$env:OMP_NUM_THREADS = '1'
$A = $PSScriptRoot
Set-Location $A
$py = "$A\.venv\Scripts\python.exe"
$log = "$A\etape-6e.log"
function Note($t) { "$(Get-Date -Format 'HH:mm:ss') $t" | Out-File -Append -Encoding utf8 $log; Write-Output $t }

Note "1) essai 6e (180 min)"
& $py entrainer_essai6.py --jeu donnees\jeu-10000 --jeu-photos donnees\photos-app-cotes donnees\photos-app-sans-cotes donnees\photos-reel-cotes donnees\photos-reel-sans-cotes --jeu-monde donnees\monde-6-19 --reprendre resultats-essai-5\atelya-essai-4.pt --processus 1 --minutes 180 --figer-bn --poids-maitre 3.0 --poids-escalier 3.0 --part-monde 0.2 --part-photos 0.45 --lr 1.5e-4 --sortie resultats-essai-6e *> "$A\entrainement-essai6e.log"
Note "   fin essai 6e code $LASTEXITCODE"

$m = "$A\resultats-essai-6e\atelya-essai-6.pt"
if (Test-Path $m) { Note "2) modele utilise : atelya-essai-6.pt (garde)" }
else {
  $m = "$A\resultats-essai-6e\atelya-essai-6-dernier.pt"
  Note "2) modele utilise : atelya-essai-6-dernier.pt (aucun garde)"
}
if (-not (Test-Path $m)) { Note "   ARRET : aucun modele trouve"; exit 1 }

Note "3) vrais plans colories par e6e"
& $py colorier_vrais_plans.py --dossier vrais-plans\lot-2026-10-31 --modele $m --sortie vrais-plans\coloriages-lot-2026-10-31-e6e *> "$A\vrais-plans\colorier-lot-e6e.log"
Note "   code $LASTEXITCODE"

Note "4) coloriages des jeux de controle"
foreach ($c in @(@('donnees\photos-reel-test-sc','coloriages-reel-sc-e6e'), @('donnees\photos-reel-test-cotes','coloriages-reel-cotes-e6e'), @('donnees\photos-sans-cotes','coloriages-psc-e6e'), @('jeu-test-6-13','coloriages-6-19-e6e'))) {
  & $py colorier-6-12.py --jeu $c[0] --modele $m --sortie $c[1] *> "colorier-$($c[1]).log"; Note "   $($c[1]) code $LASTEXITCODE"
}

Set-Location "$A\code-6-19"
$bancs = @(
  @('..\jeu-test-6-13', '..\coloriages-6-19-e6e', '..\banc-6-19-apres-e6e'),
  @('..\donnees\photos-sans-cotes', '..\coloriages-psc-e6e', '..\banc-6-19-psc-e6e'),
  @('..\donnees\photos-reel-test-cotes', '..\coloriages-reel-cotes-e6e', '..\banc-6-19-reel-cotes-e6e'),
  @('..\donnees\photos-reel-test-sc', '..\coloriages-reel-sc-e6e', '..\banc-6-19-reel-sc-e6e'))
foreach ($b in $bancs) {
  Note "5) banc $($b[2])"
  New-Item -ItemType Directory -Force $b[2] | Out-Null
  & $py -m moteur.banc_coloriage $b[0] --partie test --coloriages "$($b[1])\exemples" --echelle lue --proportions optique --processus 5 --sortie $b[2] *> "$($b[2])\banc.log"
  Note "   code $LASTEXITCODE"
}
Note "FINI"
