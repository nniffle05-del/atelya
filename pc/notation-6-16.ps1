$ErrorActionPreference = 'Continue'
$env:PYTHONIOENCODING = 'utf-8'
$env:OMP_NUM_THREADS = '1'
Set-Location 'D:\Modélisation immobilière\atelya'
$m = 'resultats-essai-5\atelya-essai-4.pt'
"debut $(Get-Date)" > notation-6-16.log
foreach ($c in @(@('donnees\photos-reel-test-sc','coloriages-reel-sc-e5'), @('donnees\photos-reel-test-cotes','coloriages-reel-cotes-e5'), @('donnees\photos-sans-cotes','coloriages-psc-e5'), @('jeu-test-6-13','coloriages-6-16-e5'))) {
    "colorier $($c[1]) $(Get-Date)" >> notation-6-16.log
    & .venv\Scripts\python.exe colorier-6-12.py --jeu $c[0] --modele $m --sortie $c[1] *> "colorier-$($c[1]).log"
    "  code $LASTEXITCODE" >> notation-6-16.log
}
Set-Location code-6-16
$bancs = @(
    @('..\donnees\photos-reel-test-sc', '..\coloriages-reel-sc-e5', '..\banc-6-16-reel-sc-e5'),
    @('..\donnees\photos-reel-test-cotes', '..\coloriages-reel-cotes-e5', '..\banc-6-16-reel-cotes-e5'),
    @('..\donnees\photos-sans-cotes', '..\coloriages-psc-e5', '..\banc-6-16-psc-e5'),
    @('..\jeu-test-6-13', '..\coloriages-6-16-e5', '..\banc-6-16-apres-e5'),
    @('..\donnees\photos-reel-test-sc', '..\coloriages-reel-sc-e4', '..\banc-6-16-reel-sc-e4g'),
    @('..\donnees\photos-reel-test-cotes', '..\coloriages-reel-cotes-e4', '..\banc-6-16-reel-cotes-e4g'),
    @('..\donnees\photos-sans-cotes', '..\coloriages-psc-e4seul', '..\banc-6-16-psc-e4g'),
    @('..\jeu-test-6-13', '..\coloriages-6-15-e4seul', '..\banc-6-16-apres-e4g'))
foreach ($b in $bancs) {
    "banc $($b[2]) $(Get-Date)" >> ..\notation-6-16.log
    New-Item -ItemType Directory -Force $b[2] | Out-Null
    & ..\.venv\Scripts\python.exe -m moteur.banc_coloriage $b[0] --partie test --coloriages "$($b[1])\exemples" --echelle lue --proportions optique --processus 5 --sortie $b[2] *> "$($b[2])\banc.log"
    "  code $LASTEXITCODE" >> ..\notation-6-16.log
}
"FINI $(Get-Date)" >> ..\notation-6-16.log
