# Telecharge les meubles ABO (Amazon Berkeley Objects, CC BY 4.0) dans SA PROPRE FENETRE Windows,
# independante de toute conversation Claude Code. Reprend ou il s'etait arrete (ce qui est deja la n'est pas retelecharge).
# Double-clic (ou clic droit > Executer avec PowerShell). Journal : ..\atelya\bibliotheque\meubles-abo\journal.txt
$ErrorActionPreference = "Continue"
Set-Location (Join-Path $PSScriptRoot "..\..")
$env:PYTHONIOENCODING = "utf-8"
$Host.UI.RawUI.WindowTitle = "Atelya - telechargement des meubles (ne pas fermer)"
& "..\atelya\.venv\Scripts\python.exe" -u outils\bibliotheque\telecharger_meubles.py `
    ..\atelya\bibliotheque\meubles-essai\metadata-hf.jsonl ..\atelya\bibliotheque\meubles-abo --fils 6 2>&1 |
    Tee-Object -FilePath ..\atelya\bibliotheque\meubles-abo\journal.txt -Append
if ($LASTEXITCODE -ne 0) {
    Write-Host "PLANTE (code $LASTEXITCODE). Relancer ce script : il reprend ou il s'etait arrete." -ForegroundColor Red
} else {
    Write-Host "FINI : tous les meubles sont telecharges." -ForegroundColor Green
}
Read-Host "Appuyer sur Entree pour fermer cette fenetre"
