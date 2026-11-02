# Étape 6d : 4 petits essais de 30 min, l'un après l'autre (pas en parallèle).
# À lancer depuis D:\Modélisation immobilière\atelya.
Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
$env:OMP_NUM_THREADS = "1"
$base = @("entrainer_essai6.py", "--jeu", "donnees\jeu-10000",
          "--jeu-photos", "donnees\photos-app-cotes", "donnees\photos-app-sans-cotes", "donnees\photos-reel-cotes", "donnees\photos-reel-sans-cotes",
          "--jeu-monde", "donnees\monde-6-19", "--reprendre", "resultats-essai-5\atelya-essai-4.pt",
          "--processus", "1", "--minutes", "30", "--figer-bn", "--lr", "1.5e-4")
$essais = [ordered]@{
    "T0" = @("--poids-maitre", "1.0", "--part-monde", "0.25", "--part-photos", "0.35")
    "T1" = @("--poids-maitre", "1.0", "--part-monde", "0.25", "--part-photos", "0.35", "--part-coherence", "0")
    "T2" = @("--poids-maitre", "3.0", "--part-monde", "0.2", "--part-photos", "0.45")
    "T3" = @("--poids-maitre", "1.0", "--part-monde", "0.25", "--part-photos", "0.35", "--poids-escalier", "3.0")
}
foreach ($t in $essais.Keys) {
    "$(Get-Date -Format 'HH:mm:ss') debut $t" | Add-Content petits-essais-6d.suivi -Encoding UTF8
    & .venv\Scripts\python.exe @base @($essais[$t]) --sortie "resultats-6d-$t" *> "essai-6d-$t.log"
    "$(Get-Date -Format 'HH:mm:ss') fin $t code $LASTEXITCODE" | Add-Content petits-essais-6d.suivi -Encoding UTF8
}
"$(Get-Date -Format 'HH:mm:ss') TOUT FINI" | Add-Content petits-essais-6d.suivi -Encoding UTF8
