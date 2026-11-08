# Banc des styles du lot 2 (jeu lot2-test, 412 exemples, jamais appris) avec le lecteur en service (essai 5), a lancer depuis le depot atelya-code.
# Pourquoi : mesurer Atelya actuel sur les styles vus sur les vrais plans AVANT l'essai 8, pour juger ensuite le nouveau modele sans recul ni illusion.
# Phases : colorier (carte graphique, essai 5, 4 angles + carte des doutes), banc (echelle lue, doutes). S'arrete au premier code different de 0 (ligne PLANTE).
param([string]$Phase = 'tout', [string]$Modele = 'resultats-essai-5\atelya-essai-4.pt', [string]$Nom = 'e5')
$ErrorActionPreference = 'Continue'
Add-Type -Namespace Atelya -Name VeilleBancLot2 -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("kernel32.dll")]
public static extern uint SetThreadExecutionState(uint esFlags);
'@
[Atelya.VeilleBancLot2]::SetThreadExecutionState([uint32]2147483649) | Out-Null
$env:OMP_NUM_THREADS = '1'
$env:PYTHONIOENCODING = 'utf-8'
$A = '..\atelya'
$py = "$A\.venv\Scripts\python.exe"
$suivi = "$A\banc-lot2-$Nom.suivi"
function Note($m) { Add-Content -Path $suivi -Value "$(Get-Date -Format 'HH:mm:ss') $m" -Encoding UTF8 }
if (-not (Test-Path "$A\donnees\lot2-test\repartition.json")) { Write-Output 'PLANTE : jeu lot2-test introuvable'; exit 1 }
Set-Content -Path $suivi -Value "$(Get-Date -Format 'HH:mm:ss') DEBUT $Phase $Modele" -Encoding UTF8
$col = "coloriages-lot2-test-$Nom"
if ($Phase -in @('colorier', 'tout')) {
    Note "colorier -> $A\$col"
    Push-Location $A
    & '.\.venv\Scripts\python.exe' colorier_angles_a3.py --jeu 'donnees\lot2-test' --partie test --modele $Modele --sortie $col *> "$col.log"
    $code = $LASTEXITCODE
    Pop-Location
    if ($code -ne 0) { Note "PLANTE colorier code=$code"; Write-Output "PLANTE colorier code=$code"; exit $code }
    Note 'fini colorier code=0'
}
if ($Phase -in @('banc', 'tout')) {
    $sortie = "$A\banc-lot2-$Nom"
    New-Item -ItemType Directory -Force $sortie | Out-Null
    Note "banc -> $sortie"
    & $py -m moteur.banc_coloriage "$A\donnees\lot2-test" --partie test --coloriages "$A\$col\exemples" --echelle lue --proportions optique --processus 5 --doutes --sortie $sortie *> "$sortie\banc.log"
    $code = $LASTEXITCODE
    if ($code -ne 0) { Note "PLANTE banc code=$code"; Write-Output "PLANTE banc code=$code"; exit $code }
    Note 'fini banc code=0'
}
Note 'FINI tout'
[Atelya.VeilleBancLot2]::SetThreadExecutionState([uint32]2147483648) | Out-Null
Write-Output 'FINI tout'
