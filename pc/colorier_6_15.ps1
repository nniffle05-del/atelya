$env:PYTHONIOENCODING = "utf-8"
Set-Location $PSScriptRoot
$py = ".venv\Scripts\python.exe"
$t = Get-Date
& $py colorier-6-12.py --jeu donnees\photos-sans-cotes --modele resultats-essai-4\atelya-essai-4.pt --modele-pieces resultats-essai-3\atelya-essai-3.pt --sortie coloriages-psc-e4 *> colorier-psc-e4.log
"FIN code=$LASTEXITCODE duree=$((Get-Date) - $t)" | Out-File -Append -Encoding utf8 colorier-psc-e4.log
$t = Get-Date
& $py colorier-6-12.py --jeu donnees\photos-sans-cotes --modele resultats-essai-4\atelya-essai-4.pt --sortie coloriages-psc-e4seul *> colorier-psc-e4seul.log
"FIN code=$LASTEXITCODE duree=$((Get-Date) - $t)" | Out-File -Append -Encoding utf8 colorier-psc-e4seul.log
$t = Get-Date
& $py colorier-6-12.py --jeu jeu-test-6-13 --modele resultats-essai-4\atelya-essai-4.pt --modele-pieces resultats-essai-3\atelya-essai-3.pt --sortie coloriages-6-15-e4 *> colorier-6-15-e4.log
"FIN code=$LASTEXITCODE duree=$((Get-Date) - $t)" | Out-File -Append -Encoding utf8 colorier-6-15-e4.log
