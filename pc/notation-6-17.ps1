$ErrorActionPreference = 'Continue'
$env:PYTHONIOENCODING = 'utf-8'
$env:OMP_NUM_THREADS = '1'
Set-Location (Join-Path $PSScriptRoot 'code-6-17') -ErrorAction Stop
$bancs = @(
    @('..\donnees\photos-reel-test-cotes', '..\coloriages-reel-cotes-e5', '..\banc-6-17-reel-cotes-e5'),
    @('..\donnees\photos-reel-test-sc', '..\coloriages-reel-sc-e5', '..\banc-6-17-reel-sc-e5'),
    @('..\donnees\photos-sans-cotes', '..\coloriages-psc-e5', '..\banc-6-17-psc-e5'),
    @('..\jeu-test-6-13', '..\coloriages-6-16-e5', '..\banc-6-17-apres-e5'))
foreach ($b in $bancs) {
    "3) banc $($b[2]) debut $(Get-Date)" | Out-File -Append -Encoding utf8 ..\etape-6-17.log
    & ..\.venv\Scripts\python.exe -m moteur.banc_coloriage $b[0] --partie test --coloriages "$($b[1])\exemples" --echelle lue --proportions optique --processus 5 --sortie $b[2] *> "$($b[2])\banc.log"
    "   fin $(Get-Date) code $LASTEXITCODE" | Out-File -Append -Encoding utf8 ..\etape-6-17.log
}
"3) BANCS FINIS $(Get-Date)" | Out-File -Append -Encoding utf8 ..\etape-6-17.log
