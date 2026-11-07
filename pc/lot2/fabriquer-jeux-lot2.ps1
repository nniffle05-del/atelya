# Fabrique les jeux du lot 2 du generateur (0.1.6, --lot2), a lancer depuis le depot atelya-code.
# Pourquoi : l'essai 8 apprendra les styles vus sur les vrais plans aussi sur des plans fabriques, dont la verite est exacte.
# Pourquoi ces graines : 120001 et au-dela ne recoupent aucun jeu deja fait. Les jeux « test » ne servent JAMAIS a apprendre.
# Chemins RELATIFS (cv2 n'ecrit rien dans un chemin absolu accentue). S'arrete au premier code different de 0, avec une ligne PLANTE.
param([int]$Processus = 3)
$ErrorActionPreference = 'Continue'
Add-Type -Namespace Atelya -Name VeilleJeux -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("kernel32.dll")]
public static extern uint SetThreadExecutionState(uint esFlags);
'@
[Atelya.VeilleJeux]::SetThreadExecutionState([uint32]2147483649) | Out-Null
$env:OMP_NUM_THREADS = '1'
$env:PYTHONIOENCODING = 'utf-8'
$A = '..\atelya'
$py = "$A\.venv\Scripts\python.exe"
$suivi = "$A\lot2-jeux.suivi"
function Note($m) { Add-Content -Path $suivi -Value "$(Get-Date -Format 'HH:mm:ss') $m" -Encoding UTF8 }
if (-not (Test-Path $py)) { Write-Output 'PLANTE : python introuvable'; exit 1 }
Set-Content -Path $suivi -Value "$(Get-Date -Format 'HH:mm:ss') DEBUT" -Encoding UTF8
$jeux = @(
    @('lot2-test', '--nombre', '400', '--depart', '129001', '--lot2'),
    @('lot2-a', '--nombre', '3300', '--depart', '120001', '--lot2'),
    @('lot2-monde', '--nombre', '800', '--depart', '124001', '--lot2', '--styles-monde'),
    @('lot2-biais', '--nombre', '1100', '--depart', '125001', '--lot2', '--biais'),
    @('lot2-photos', '--nombre', '1100', '--depart', '127001', '--lot2', '--familles', 'photo', '--photo-realiste')
)
foreach ($j in $jeux) {
    $nom = $j[0]; $opts = $j[1..($j.Count - 1)]
    Note "lance $nom : $($opts -join ' ')"
    & $py -m moteur.generateur tout @opts --dossier "$A\donnees\$nom" --processus $Processus *> "$A\gen-$nom.log"
    $code = $LASTEXITCODE
    if ($code -ne 0) { Note "PLANTE $nom code=$code"; Write-Output "PLANTE $nom code=$code"; exit $code }
    Note "fini $nom code=0"
}
Note 'FINI tout'
[Atelya.VeilleJeux]::SetThreadExecutionState([uint32]2147483648) | Out-Null
Write-Output 'FINI tout'
