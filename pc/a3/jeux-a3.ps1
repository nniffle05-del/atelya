# Étape A3-2 sur le PC : code A3 (générateur 0.1.5 --biais, traducteur 0.4.0, 3D en onglet), tests, jeux murs en biais.
# À lancer depuis D:\Modélisation immobilière\atelya :  powershell -File jeux-a3.ps1 -Phase code|jeux|essai7|tout   (tout = code+jeux+essai7)
# Chemins RELATIFS pour --dossier (cv2.imwrite échoue sans rien dire sur un chemin absolu avec « é »).
param([string]$Phase = "tout")
$ErrorActionPreference = 'Continue'
Set-Location $PSScriptRoot
$A = $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
$env:OMP_NUM_THREADS = "1"
$py = "$A\.venv\Scripts\python.exe"
$suivi = "$A\jeux-a3.suivi"
function Note($t) { "$(Get-Date -Format 'HH:mm:ss') $t" | Add-Content $suivi -Encoding UTF8; Write-Output $t }

if ($Phase -in @("code", "tout")) {
    Note "CODE : code-a3 = code-6-19 + depot-a3 (moteur et tests complets de la branche A3)"
    if (-not (Test-Path "$A\code-6-19")) { Note "ARRET : code-6-19 manque"; exit 1 }
    if (Test-Path "$A\depot-a3.zip") { Expand-Archive -Path "$A\depot-a3.zip" -DestinationPath "$A\depot-a3" -Force }
    robocopy "$A\code-6-19" "$A\code-a3" /E /NFL /NDL /NJH /NJS /XD __pycache__ | Out-Null
    robocopy "$A\depot-a3\moteur" "$A\code-a3\moteur" /E /NFL /NDL /NJH /NJS | Out-Null
    robocopy "$A\depot-a3\tests" "$A\code-a3\tests" /E /NFL /NDL /NJH /NJS | Out-Null
    Copy-Item "$A\depot-a3\lancer_tests.py" "$A\code-a3\" -Force
    Set-Location "$A\code-a3"
    & $py lancer_tests.py *> "$A\tests-a3.log"; Note "tests code $LASTEXITCODE"
    Get-Content "$A\tests-a3.log" -Tail 3 | Add-Content $suivi -Encoding UTF8
    Set-Location $A
}
if ($Phase -in @("jeux", "tout")) {
    Set-Location "$A\code-a3"
    # Graines 80001+ : aucune ne recoupe les jeux déjà faits. Les jeux « test » ne servent JAMAIS à apprendre.
    $jeux = @(
        @("biais-a3", "--nombre", "3300", "--depart", "80001", "--biais"),
        @("biais-monde-a3", "--nombre", "1100", "--depart", "84001", "--biais", "--styles-monde"),
        @("biais-photos-a3", "--nombre", "1500", "--depart", "86001", "--biais", "--familles", "photo", "--photo-realiste"),
        @("biais-test-a3", "--nombre", "400", "--depart", "89001", "--biais"),
        @("biais-photos-test-a3", "--nombre", "200", "--depart", "89501", "--biais", "--familles", "photo", "--photo-realiste"))
    foreach ($j in $jeux) {
        $nom = $j[0]; $opts = $j[1..($j.Count - 1)]
        Note "jeu $nom : $($opts -join ' ')"
        & $py -m moteur.generateur tout @opts --dossier "..\donnees\$nom" --processus 5 *> "$A\gen-$nom.log"
        Note "   code $LASTEXITCODE"
        Get-Content "$A\gen-$nom.log" | Select-String "acceptes_dans_le_manifeste|répartition" | Select-Object -Last 2 | ForEach-Object { "   $($_.Line.Trim())" } | Add-Content $suivi -Encoding UTF8
    }
    Set-Location $A
}
if ($Phase -in @("essai7", "tout")) {
    Set-Location $A
    # Grand entraînement A3 : petit œil DINOv2 (choix NT 2026-11-02, T1 = +9 pts monde vs sans œil) + murs en biais.
    # Recette des petits essais (6e + échauffement) ; 20 % de morceaux tirés dans les jeux biais (jamais les jeux test).
    Note "essai 7 (180 min, oeil vits14, jeux biais)"
    & $py entrainer_essai7.py --jeu donnees\jeu-10000 `
        --jeu-photos donnees\photos-app-cotes donnees\photos-app-sans-cotes donnees\photos-reel-cotes donnees\photos-reel-sans-cotes `
        --jeu-monde donnees\monde-6-19 --jeu-biais donnees\biais-a3 donnees\biais-monde-a3 donnees\biais-photos-a3 --part-biais 0.2 `
        --reprendre resultats-essai-5\atelya-essai-4.pt --processus 1 --figer-bn --poids-maitre 3.0 --poids-escalier 3.0 `
        --part-monde 0.2 --part-photos 0.45 --lr 1.5e-4 --oeil vits14 --minutes 180 --sortie resultats-essai-7 *> "$A\essai-7.log"
    Note "   fin essai 7 code $LASTEXITCODE"
    Get-Content "$A\essai-7.log" | Select-String "BILAN|AUCUN|Départ" | ForEach-Object { "   $($_.Line)" } | Add-Content $suivi -Encoding UTF8
    foreach ($m in @("atelya-essai-7.pt", "atelya-essai-7-dernier.pt")) {
        $f = "resultats-essai-7\$m"
        if (Test-Path $f) {
            $n = $m.Replace(".pt", "")
            & $py colorier_vrais_plans_a3.py --dossier vrais-plans\lot-2026-10-31 --modele $f --sortie "vrais-plans\coloriages-lot-2026-10-31-$n" *> "vrais-plans\colorier-$n.log"
            Note "   vrais plans $n code $LASTEXITCODE"
        }
    }
}
Note "FINI $Phase"
