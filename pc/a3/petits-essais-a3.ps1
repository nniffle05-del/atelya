# Étape A3-1 : petits essais DINOv2 (3 x 30 min, l'un après l'autre), à départ égal depuis l'essai 5.
# À lancer depuis D:\Modélisation immobilière\atelya :  powershell -File petits-essais-a3.ps1 -Phase prepare|essais|vrais|paquet|suite|tout   (suite = essais+vrais+paquet)
param([string]$Phase = "tout")
$ErrorActionPreference = 'Continue'
Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
$env:OMP_NUM_THREADS = "1"
$py = ".venv\Scripts\python.exe"
$suivi = "petits-essais-a3.suivi"
function Note($t) { "$(Get-Date -Format 'HH:mm:ss') $t" | Add-Content $suivi -Encoding UTF8; Write-Output $t }

# Recette de l'essai 6e (la meilleure trouvée en 6-19), identique pour les 3 essais : seul l'œil change.
$base = @("entrainer_essai7.py", "--jeu", "donnees\jeu-10000",
          "--jeu-photos", "donnees\photos-app-cotes", "donnees\photos-app-sans-cotes", "donnees\photos-reel-cotes", "donnees\photos-reel-sans-cotes",
          "--jeu-monde", "donnees\monde-6-19", "--reprendre", "resultats-essai-5\atelya-essai-4.pt",
          "--processus", "1", "--figer-bn", "--poids-maitre", "3.0", "--poids-escalier", "3.0",
          "--part-monde", "0.2", "--part-photos", "0.45", "--lr", "1.5e-4")
$essais = [ordered]@{ "T0" = "aucun"; "T1" = "vits14"; "T2" = "vitb14" }

if ($Phase -in @("prepare", "tout")) {
    Note "PREPARE"
    foreach ($f in @("oeil.py", "entrainer_essai7.py", "colorier_vrais_plans_a3.py", "colorier_a3.py", "telecharger_dinov2.py", "entrainer.py", "modeles-externes\LICENSE-DINOv2.txt", "resultats-essai-5\atelya-essai-4.pt")) {
        if (-not (Test-Path $f)) { Note "ARRET : $f manque"; exit 1 }
    }
    # Téléchargement des POIDS seulement (fichiers de nombres, pas de code) depuis le site officiel de Meta.
    New-Item -ItemType Directory -Force "modeles-externes" | Out-Null
    foreach ($n in @("vits14", "vitb14")) {
        $f = "modeles-externes\dinov2_${n}_pretrain.pth"
        if (-not (Test-Path $f)) {
            Invoke-WebRequest -UseBasicParsing -Uri "https://dl.fbaipublicfiles.com/dinov2/dinov2_${n}/dinov2_${n}_pretrain.pth" -OutFile $f
        }
        Note "poids $n : $((Get-Item $f).Length) octets"
    }
    & $py telecharger_dinov2.py *> "telecharger-dinov2.log"; Note "verification DINOv2 code $LASTEXITCODE"
    Get-Content "telecharger-dinov2.log" | Add-Content $suivi -Encoding UTF8
    # Essai éclair (2 min, l'œil le plus gros) : vérifie que tout tourne et tient dans les 8 Go.
    & $py @base --oeil vitb14 --minutes 2 --nb-val 5 --pas-par-tour 100 --sortie "resultats-a3-eclair" *> "essai-a3-eclair.log"
    Note "eclair code $LASTEXITCODE"
    Get-Content "essai-a3-eclair.log" -Tail 25 | Add-Content $suivi -Encoding UTF8
}
if ($Phase -in @("essais", "suite", "tout")) {
    foreach ($t in $essais.Keys) {
        Note "debut $t (oeil $($essais[$t]), 30 min)"
        & $py @base --oeil $essais[$t] --minutes 30 --sortie "resultats-a3-$t" *> "essai-a3-$t.log"
        Note "fin $t code $LASTEXITCODE"
        Get-Content "essai-a3-$t.log" | Select-String "BILAN|Départ|Réglages|pas " | Select-Object -Last 14 | ForEach-Object { $_.Line } | Add-Content $suivi -Encoding UTF8
    }
}
if ($Phase -in @("vrais", "suite", "tout")) {
    foreach ($t in $essais.Keys) {
        $m = "resultats-a3-$t\atelya-essai-7-dernier.pt"
        if (Test-Path $m) {
            & $py colorier_vrais_plans_a3.py --dossier vrais-plans\lot-2026-10-31 --modele $m --sortie "vrais-plans\coloriages-lot-2026-10-31-a3-$t" *> "vrais-plans\colorier-a3-$t.log"
            Note "vrais plans $t code $LASTEXITCODE"
        }
    }
}
if ($Phase -in @("paquet", "suite", "tout")) {
    $z = "pour-cloud-a3-petits.zip"
    if (Test-Path $z) { Remove-Item $z }
    $quoi = @("petits-essais-a3.suivi", "telecharger-dinov2.log", "essai-a3-*.log") + (Get-ChildItem -Directory "resultats-a3-*" | ForEach-Object { "$($_.Name)\*.json"; "$($_.Name)\*.png" }) + (Get-ChildItem -Directory "vrais-plans\coloriages-lot-2026-10-31-a3-*" | ForEach-Object { $_.FullName })
    Compress-Archive -Path $quoi -DestinationPath $z -Force
    Note "paquet $z $((Get-Item $z).Length) octets"
}
Note "FINI $Phase"
