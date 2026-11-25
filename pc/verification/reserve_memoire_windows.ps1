# LA RÉSERVE DE MÉMOIRE SUR DISQUE DE WINDOWS (le « fichier d'échange »), agrandie pour les tournages Unreal.
# ACCORD ÉCRIT DE NT, 25/11/2026 (« Faut tout ces points-là, je t'y autorise »).
#
#     powershell -ExecutionPolicy Bypass -File pc\verification\reserve_memoire_windows.ps1            (16 Go au départ, 24 Go au plus)
#     powershell -ExecutionPolicy Bypass -File pc\verification\reserve_memoire_windows.ps1 -Annuler   (revenir au réglage automatique de Windows)
#
# Pourquoi : le PC a 16 Go de mémoire vive ; Windows y ajoutait 6,4 Go sur le disque C: (22 Go en tout). Hors Unreal le PC en
# occupe ~12 ; un import Unreal en demande jusqu'à 10,3 : le 25/11 un tournage a planté, mémoire pleine, et le suivant est
# passé avec 0,46 Go de marge. Avec 16 Go de réserve fixe : 32 Go en tout, ~9 Go de marge. Coût : 16 Go du disque C: (124 Go
# libres le 25/11). Windows demande les DROITS ADMINISTRATEUR (une fenêtre « Voulez-vous autoriser… » : répondre Oui) et le
# réglage ne prend effet qu'au PROCHAIN REDÉMARRAGE du PC. Ce script ne redémarre rien.
# Le résultat est écrit dans %TEMP%\atelya-reserve-memoire.txt (lu par la partie non administrateur).
param([int]$InitialMo = 16384, [int]$MaxMo = 24576, [switch]$Annuler, [switch]$Elevee)
$resultat = Join-Path $env:TEMP "atelya-reserve-memoire.txt"
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    if ($Elevee) { "ECHEC : droits administrateur refuses" | Out-File -LiteralPath $resultat -Encoding utf8; exit 1 }
    Remove-Item -LiteralPath $resultat -ErrorAction SilentlyContinue
    $arguments = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$PSCommandPath`"", "-InitialMo", $InitialMo, "-MaxMo", $MaxMo, "-Elevee")
    if ($Annuler) { $arguments += "-Annuler" }
    try { Start-Process powershell -Verb RunAs -ArgumentList $arguments -WindowStyle Hidden -Wait }
    catch { Write-Output "PAS FAIT : la fenetre des droits administrateur a ete refusee ou n'a pas eu de reponse ($($_.Exception.Message))"; exit 1 }
    if (Test-Path -LiteralPath $resultat) { Get-Content -LiteralPath $resultat; if ((Get-Content -LiteralPath $resultat -Raw) -match "ECHEC") { exit 1 } else { exit 0 } }
    Write-Output "PAS FAIT : aucun resultat ecrit (fenetre des droits fermee ?)"; exit 1
}
try {
    $systeme = Get-CimInstance Win32_ComputerSystem
    $avant = "automatique=$($systeme.AutomaticManagedPagefile)"
    if ($Annuler) {
        Set-CimInstance -InputObject $systeme -Property @{ AutomaticManagedPagefile = $true } -ErrorAction Stop
        "FAIT : la reserve de memoire sur disque est rendue a Windows (reglage automatique) ; avant : $avant. Prend effet au prochain redemarrage." | Out-File -LiteralPath $resultat -Encoding utf8
        exit 0
    }
    $disque = Get-PSDrive C
    if ($disque.Free / 1MB -lt $MaxMo + 20480) { "ECHEC : pas assez de place sur C: ($([math]::Round($disque.Free / 1GB)) Go libres) pour une reserve de $MaxMo Mo" | Out-File -LiteralPath $resultat -Encoding utf8; exit 1 }
    Set-CimInstance -InputObject $systeme -Property @{ AutomaticManagedPagefile = $false } -ErrorAction Stop
    $reglage = Get-CimInstance Win32_PageFileSetting | Where-Object { $_.Name -like "C:\pagefile.sys" }
    if (-not $reglage) { $reglage = New-CimInstance -ClassName Win32_PageFileSetting -Property @{ Name = "C:\pagefile.sys" } -ErrorAction Stop }
    Set-CimInstance -InputObject $reglage -Property @{ InitialSize = [uint32]$InitialMo; MaximumSize = [uint32]$MaxMo } -ErrorAction Stop
    $lu = Get-CimInstance Win32_PageFileSetting | Where-Object { $_.Name -like "C:\pagefile.sys" }
    if ($lu.InitialSize -ne $InitialMo -or $lu.MaximumSize -ne $MaxMo) { throw "le reglage relu ne correspond pas : $($lu.InitialSize) / $($lu.MaximumSize)" }
    "FAIT : reserve de memoire sur disque reglee a $InitialMo Mo au depart, $MaxMo Mo au plus (C:\pagefile.sys) ; avant : $avant. Prend effet au PROCHAIN REDEMARRAGE du PC. Pour revenir en arriere : -Annuler." | Out-File -LiteralPath $resultat -Encoding utf8
    exit 0
} catch {
    "ECHEC : $($_.Exception.Message)" | Out-File -LiteralPath $resultat -Encoding utf8
    exit 1
}
