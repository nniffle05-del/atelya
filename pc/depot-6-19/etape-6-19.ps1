# Etape 6-19 sur le PC : code, jeu styles du monde, essai court, essai 6, coloriages et bancs.
$ErrorActionPreference = 'Continue'
$env:PYTHONIOENCODING = 'utf-8'
$env:OMP_NUM_THREADS = '1'
$A = Split-Path $PSScriptRoot -Parent
Set-Location $A
$py = "$A\.venv\Scripts\python.exe"
$log = "$A\etape-6-19.log"
function Note($t) { "$(Get-Date -Format 'HH:mm:ss') $t" | Out-File -Append -Encoding utf8 $log; Write-Output $t }
$phase = $args[0]
if ($phase -eq 'prepare') {
  Note "1) code-6-19"
  robocopy "$A\code-6-17" "$A\code-6-19" /E /NFL /NDL /NJH /NJS /XD __pycache__ | Out-Null
  robocopy "$A\depot-6-19\moteur" "$A\code-6-19\moteur" /E /NFL /NDL /NJH /NJS | Out-Null
  robocopy "$A\depot-6-19\tests" "$A\code-6-19\tests" /E /NFL /NDL /NJH /NJS | Out-Null
  Copy-Item "$A\depot-6-19\lancer_tests.py" "$A\code-6-19\" -Force
  Copy-Item "$A\depot-6-19\entrainer_essai6.py" "$A\" -Force
  Set-Location "$A\code-6-19"
  & $py lancer_tests.py *> "$A\tests-6-19.log"; Note "   tests code $LASTEXITCODE (voir tests-6-19.log)"
  Note "2) jeu monde-6-19 (graines 60001-63300)"
  & $py -m moteur.generateur tout --nombre 3300 --depart 60001 --styles-monde --dossier "$A\donnees\monde-6-19" --processus 5 *> "$A\gen-monde-6-19.log"
  Note "   fin generation code $LASTEXITCODE"
  Set-Location $A
  Note "3) essai court (4 min)"
  & $py entrainer_essai6.py --jeu donnees\jeu-10000 --jeu-photos donnees\photos-app-cotes donnees\photos-app-sans-cotes donnees\photos-reel-cotes donnees\photos-reel-sans-cotes --jeu-monde donnees\monde-6-19 --reprendre resultats-essai-5\atelya-essai-4.pt --sortie resultats-essai-6-court --minutes 4 --pas-par-tour 100 --nb-val 20 --processus 1 *> "$A\essai6-court.log"
  Note "   fin essai court code $LASTEXITCODE"
}
if ($phase -eq 'essai6') {
  Note "4) essai 6 (120 min)"
  & $py entrainer_essai6.py --jeu donnees\jeu-10000 --jeu-photos donnees\photos-app-cotes donnees\photos-app-sans-cotes donnees\photos-reel-cotes donnees\photos-reel-sans-cotes --jeu-monde donnees\monde-6-19 --reprendre resultats-essai-5\atelya-essai-4.pt --sortie resultats-essai-6 --minutes 120 --processus 1 *> "$A\entrainement-essai6.log"
  Note "   fin essai 6 code $LASTEXITCODE"
  $m = "$A\resultats-essai-6\atelya-essai-6.pt"
  if (-not (Test-Path $m)) { Note "   pas de modele garde : on s'arrete"; exit 0 }
  Note "5) vrais plans colories par essai 6"
  & $py colorier_vrais_plans.py --dossier vrais-plans\lot-2026-10-31 --modele $m --sortie vrais-plans\coloriages-lot-2026-10-31-e6 *> "$A\vrais-plans\colorier-lot-e6.log"
  Note "6) coloriages des jeux de controle"
  foreach ($c in @(@('donnees\photos-reel-test-sc','coloriages-reel-sc-e6'), @('donnees\photos-reel-test-cotes','coloriages-reel-cotes-e6'), @('donnees\photos-sans-cotes','coloriages-psc-e6'), @('jeu-test-6-13','coloriages-6-19-e6'))) {
    & $py colorier-6-12.py --jeu $c[0] --modele $m --sortie $c[1] *> "colorier-$($c[1]).log"; Note "   $($c[1]) code $LASTEXITCODE"
  }
  Set-Location "$A\code-6-19"
  $bancs = @(
    @('..\jeu-test-6-13', '..\coloriages-6-19-e6', '..\banc-6-19-apres-e6'),
    @('..\donnees\photos-sans-cotes', '..\coloriages-psc-e6', '..\banc-6-19-psc-e6'),
    @('..\donnees\photos-reel-test-cotes', '..\coloriages-reel-cotes-e6', '..\banc-6-19-reel-cotes-e6'),
    @('..\donnees\photos-reel-test-sc', '..\coloriages-reel-sc-e6', '..\banc-6-19-reel-sc-e6'))
  foreach ($b in $bancs) {
    Note "7) banc $($b[2])"
    New-Item -ItemType Directory -Force $b[2] | Out-Null
    & $py -m moteur.banc_coloriage $b[0] --partie test --coloriages "$($b[1])\exemples" --echelle lue --proportions optique --processus 5 --sortie $b[2] *> "$($b[2])\banc.log"
    Note "   code $LASTEXITCODE"
  }
  Note "FINI"
}
