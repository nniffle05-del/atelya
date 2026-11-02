$env:OMP_NUM_THREADS = "1"
$racine = $PSScriptRoot
$py = Join-Path $racine ".venv\Scripts\python.exe"
Set-Location (Join-Path $racine "code-6-14")
$log1 = Join-Path $racine "gen-photos-app-cotes.log"
$log2 = Join-Path $racine "gen-photos-app-sans-cotes.log"
# chemins relatifs (comme a l'etape 6-14) : les ecritures d'images echouent sur les chemins accentues
$t0 = Get-Date
& $py -m moteur.generateur tout --dossier "..\donnees\photos-app-cotes" --nombre 1400 --depart 30001 --familles photo --vraie-camera --processus 5 *> $log1
"FIN cotes code=$LASTEXITCODE duree=$((Get-Date) - $t0)" | Out-File -Append -Encoding utf8 $log1
$t1 = Get-Date
& $py -m moteur.generateur tout --dossier "..\donnees\photos-app-sans-cotes" --nombre 1400 --depart 31401 --familles photo --vraie-camera --sans-cotes --processus 5 *> $log2
"FIN sans-cotes code=$LASTEXITCODE duree=$((Get-Date) - $t1)" | Out-File -Append -Encoding utf8 $log2
