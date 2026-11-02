$env:PYTHONIOENCODING = "utf-8"
$env:OMP_NUM_THREADS = "1"
Set-Location $PSScriptRoot
& .venv\Scripts\python.exe colorier-6-12.py --jeu jeu-test-6-13 --modele resultats-essai-4\atelya-essai-4.pt --sortie coloriages-6-15-e4seul *> colorier-6-15-e4seul.log
"FIN code=$LASTEXITCODE" | Out-File -Append -Encoding utf8 colorier-6-15-e4seul.log
Set-Location code-6-14
$bancs = @(
  @("..\donnees\photos-sans-cotes", "..\coloriages-psc-e4\exemples", "..\banc-6-15-psc-e4"),
  @("..\donnees\photos-sans-cotes", "..\coloriages-psc-e4seul\exemples", "..\banc-6-15-psc-e4seul"),
  @("..\jeu-test-6-13", "..\coloriages-6-15-e4\exemples", "..\banc-6-15-apres-e4"),
  @("..\jeu-test-6-13", "..\coloriages-6-15-e4seul\exemples", "..\banc-6-15-apres-e4seul")
)
foreach ($b in $bancs) {
  New-Item -ItemType Directory -Force $b[2] | Out-Null
  $t = Get-Date
  & ..\.venv\Scripts\python.exe -m moteur.banc_coloriage $b[0] --partie test --coloriages $b[1] --echelle lue --proportions optique --processus 5 --sortie $b[2] *> (Join-Path $b[2] "banc.log")
  "FIN code=$LASTEXITCODE duree=$((Get-Date) - $t)" | Out-File -Append -Encoding utf8 (Join-Path $b[2] "banc.log")
}
