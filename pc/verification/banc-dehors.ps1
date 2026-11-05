# Bancs de non-recul du correctif « dehors » (traducteur 0.4.4 : le vide ne passe que par le fond), sans cache.
# A lancer depuis le depot atelya-code. S'arrete au premier code different de 0, avec une ligne PLANTE.
$ErrorActionPreference = 'Stop'
Add-Type -Namespace Atelya -Name VeilleEchelle -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("kernel32.dll")]
public static extern uint SetThreadExecutionState(uint esFlags);
'@
[Atelya.VeilleEchelle]::SetThreadExecutionState([uint32]2147483649) | Out-Null
$env:OMP_NUM_THREADS = '1'
$env:PYTHONIOENCODING = 'utf-8'
$A = '..\atelya'
$py = "$A\.venv\Scripts\python.exe"
$suivi = "$A\banc-dehors.suivi"
function Note($m) { Add-Content -Path $suivi -Value "$(Get-Date -Format 'HH:mm:ss') $m" -Encoding UTF8 }
Set-Content -Path $suivi -Value "$(Get-Date -Format 'HH:mm:ss') DEBUT" -Encoding UTF8
$taches = @(
    @('apres', "$A\jeu-test-6-13", "$A\coloriages-a1-apres\exemples", @()),
    @('pdf', "$A\jeu-pdf-a2", "$A\coloriages-a2-pdf\exemples", @('--textes-pdf')),
    @('reel-cotes', "$A\donnees\photos-reel-test-cotes", "$A\coloriages-a1-reel-cotes\exemples", @()),
    @('biais-e7', "$A\donnees\biais-test-a3", "$A\coloriages-a3-biais-e7\exemples", @())
)
foreach ($t in $taches) {
    $sortie = "$A\banc-dehors-$($t[0])"
    if (-not (Test-Path $t[1]) -or -not (Test-Path $t[2])) { Note "PLANTE $($t[0]) : dossier introuvable"; exit 2 }
    New-Item -ItemType Directory -Force $sortie | Out-Null
    Note "lance $($t[0])"
    $ErrorActionPreference = 'Continue'
    & $py -m moteur.banc_coloriage $t[1] --partie test @($t[3]) --coloriages $t[2] --echelle lue --proportions optique --processus 5 --doutes --sortie $sortie *> "$sortie\banc.log"
    $code = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    if ($code -ne 0) { Note "PLANTE $($t[0]) code=$code"; exit $code }
    Note "fini $($t[0]) code=0"
}
Note 'FINI tout'
[Atelya.VeilleEchelle]::SetThreadExecutionState([uint32]2147483648) | Out-Null
