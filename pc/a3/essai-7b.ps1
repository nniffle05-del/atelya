# Essai 7b (A3) : même recette que l'essai 7, mais pas d'apprentissage 3 fois plus doux + garde-fou « retour en arrière ».
# À lancer depuis D:\Modélisation immobilière\atelya :  powershell -File essai-7b.ps1
$ErrorActionPreference = 'Continue'
Set-Location $PSScriptRoot
$A = $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
$env:OMP_NUM_THREADS = "1"
$py = "$A\.venv\Scripts\python.exe"
$suivi = "$A\essai-7b.suivi"
function Note($t) { "$(Get-Date -Format 'HH:mm:ss') $t" | Add-Content $suivi -Encoding UTF8; Write-Output $t }
Note "essai 7b (150 min, oeil vits14, jeux biais, lr 5e-5, lr-oeil 1e-4)"
& $py entrainer_essai7b.py --jeu donnees\jeu-10000 `
    --jeu-photos donnees\photos-app-cotes donnees\photos-app-sans-cotes donnees\photos-reel-cotes donnees\photos-reel-sans-cotes `
    --jeu-monde donnees\monde-6-19 --jeu-biais donnees\biais-a3 donnees\biais-monde-a3 donnees\biais-photos-a3 --part-biais 0.2 `
    --reprendre resultats-essai-5\atelya-essai-4.pt --processus 1 --figer-bn --poids-maitre 3.0 --poids-escalier 3.0 `
    --part-monde 0.2 --part-photos 0.45 --lr 5e-5 --lr-oeil 1e-4 --oeil vits14 --minutes 150 --sortie resultats-essai-7b *> "$A\essai-7b.log"
Note "   fin essai 7b code $LASTEXITCODE"
Get-Content "$A\essai-7b.log" | Select-String "BILAN|AUCUN|RETOUR|gard" | ForEach-Object { "   $($_.Line)" } | Add-Content $suivi -Encoding UTF8
Note "FINI"
