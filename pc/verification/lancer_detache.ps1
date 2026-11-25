# LANCER UN LONG CALCUL À PART DE LA CONVERSATION, AVEC CONTRÔLE DE DÉPART ET GARDIEN (25/11/2026).
#
# Pourquoi : le 25/11 à 7 h 55 un tournage Unreal a planté à la première vue (mémoire du PC pleine) et la conversation de Claude
# est tombée avec lui ; rien n'a été relancé ni signalé pendant 6 h 30. NT : « ces erreurs-là, il faudrait que tu sois capable
# de les prédire, ou de les surveiller du moins ».
#
#     powershell -File pc\verification\lancer_detache.ps1 <script.sh du dépôt> <journal> [-BesoinGo 11] [-Relances 2] [-SansControle] [arguments du script…]
#     ex. powershell -File pc\verification\lancer_detache.ps1 pc/verification/film_sol_des_photos.sh ..\atelya\b2\lumiere-film\sol-des-photos\tournage.log
#
# 1. PRÉDIRE : avant de lancer, le contrôle de départ. Refus (code 2, une ligne « PAS LANCÉ : … » qui dit quoi faire) si
#    la mémoire libre (RAM + réserve sur disque) est sous BesoinGo (un tournage Unreal demande ~10 Go : mesuré le 25/11),
#    si l'éditeur Unreal est ouvert, si un disque a moins de 10 Go, ou si le PC peut se mettre en veille sur secteur.
#    Quand la mémoire est juste (moins de BesoinGo + 3 Go), il LIBÈRE d'abord ce que NT a permis de fermer (accord du
#    25/11/2026) : Steam, et les anciennes conversations Claude de plus de 12 heures qui ne travaillent pas (jamais celle
#    qui lance le calcul) ; -SansLiberer pour ne rien fermer.
# 2. SURVEILLER : le calcul tourne détaché (il survit à la conversation), le garde de la mémoire à côté de lui
#    (garde_memoire.ps1 → <journal>.memoire.csv, <journal>.ALERTE.txt).
# 3. REPRENDRE : si le script plante, il est relancé seul (Relances fois, après 2 minutes), tant qu'il reste de la mémoire :
#    les scripts de tournage reprennent où ils en étaient. Chaque essai est daté dans le journal ; la dernière ligne est
#    « code=0 » (fini) ou « PLANTÉ POUR DE BON … ».
# Suivre depuis la conversation : pc/verification/veille_tournage.sh <journal> <minutes> <dossiers…>.
param([Parameter(Mandatory = $true)][string]$Script, [Parameter(Mandatory = $true)][string]$Journal,
      [double]$BesoinGo = 11, [int]$Relances = 2, [switch]$SansControle, [switch]$SansLiberer,
      [Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
$depot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location -LiteralPath $depot
if (-not (Test-Path -LiteralPath $Script)) { Write-Output "PAS LANCE : script introuvable : $Script"; exit 1 }
$bash = "C:\Program Files\Git\usr\bin\bash.exe"
if (-not (Test-Path -LiteralPath $bash)) { Write-Output "PAS LANCE : bash introuvable : $bash"; exit 1 }

function Liberer-LaMemoire {
    # ACCORD DE NT (25/11/2026 : « Faut tout ces points-là, je t'y autorise ») : pendant un tournage, fermer Steam et les ANCIENNES
    # conversations Claude restées ouvertes dans VS Code (chacune garde 0,5 Go, plus ses outils). Jamais la conversation qui
    # lance ce calcul, ni une conversation ouverte depuis moins de 12 heures, ni une conversation qui travaille.
    $faits = @()
    $steam = Get-Process steam -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($steam -and $steam.Path) {
        Start-Process -FilePath $steam.Path -ArgumentList "-shutdown"   # la sortie propre de Steam, pas un arrêt forcé
        for ($i = 0; $i -lt 20 -and (Get-Process steam -ErrorAction SilentlyContinue); $i++) { Start-Sleep -Seconds 1 }
        $faits += $(if (Get-Process steam -ErrorAction SilentlyContinue) { "Steam ne s'est pas ferme" } else { "Steam ferme" })
    }
    # la conversation qui lance ce calcul : le claude.exe parmi les ancêtres de ce script
    $tous = @{}; Get-CimInstance Win32_Process | ForEach-Object { $tous[[int]$_.ProcessId] = $_ }
    $miens = @(); $p = $PID
    for ($i = 0; $i -lt 12 -and $tous.ContainsKey([int]$p); $i++) { if ($tous[[int]$p].Name -eq "claude.exe") { $miens += [int]$p }; $p = $tous[[int]$p].ParentProcessId }
    $autres = @($tous.Values | Where-Object { $_.Name -eq "claude.exe" -and ($miens -notcontains [int]$_.ProcessId) -and $_.CreationDate -lt (Get-Date).AddHours(-12) })
    if ($miens.Count -eq 0) { $autres = @() }   # lancé hors d'une conversation : on ne sait pas laquelle épargner, on n'en ferme aucune
    if ($autres.Count) {
        $avant = @{}; foreach ($a in $autres) { $avant[[int]$a.ProcessId] = (Get-Process -Id $a.ProcessId -ErrorAction SilentlyContinue).TotalProcessorTime }
        Start-Sleep -Seconds 8
        foreach ($a in $autres) {
            $q = Get-Process -Id $a.ProcessId -ErrorAction SilentlyContinue
            if ($q -and $avant[[int]$a.ProcessId] -ne $null -and (($q.TotalProcessorTime - $avant[[int]$a.ProcessId]).TotalSeconds -lt 0.2)) {
                & taskkill /PID $a.ProcessId /T /F | Out-Null   # cette conversation-là et ses propres outils, rien d'autre
                $faits += "conversation Claude du $($a.CreationDate.ToString('dd/MM HH:mm')) fermee"
            } elseif ($q) { $faits += "conversation Claude du $($a.CreationDate.ToString('dd/MM HH:mm')) laissee (elle travaille)" }
        }
    }
    return $faits
}

if (-not $SansControle) {
    $refus = @()
    $os = Get-CimInstance Win32_OperatingSystem
    $libre = [math]::Round($os.FreeVirtualMemory / 1MB, 1)
    if (($libre -lt $BesoinGo + 3) -and -not $SansLiberer) {
        $faits = Liberer-LaMemoire
        if ($faits.Count) {
            Start-Sleep -Seconds 3
            $os = Get-CimInstance Win32_OperatingSystem
            $apres = [math]::Round($os.FreeVirtualMemory / 1MB, 1)
            Write-Output ("memoire liberee ($libre -> $apres Go libres) : " + ($faits -join " ; "))
            $libre = $apres
        }
    }
    if ($libre -lt $BesoinGo) {
        $gros = Get-Process | Sort-Object PrivateMemorySize64 -Descending | Select-Object -First 6 | ForEach-Object { "{0} {1:N1} Go" -f $_.ProcessName, ($_.PrivateMemorySize64 / 1GB) }
        $refus += "memoire libre $libre Go pour $BesoinGo Go demandes ; plus gros programmes ouverts : $($gros -join ' ; ')"
    }
    if (Get-Process | Where-Object { $_.ProcessName -eq "UnrealEditor" }) { $refus += "l'editeur Unreal est ouvert (le fermer)" }
    foreach ($d in (Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Name -in @("C", "D") })) {
        if ($d.Free / 1GB -lt 10) { $refus += "disque $($d.Name) : $([math]::Round($d.Free / 1GB, 1)) Go libres (il en faut 10)" }
    }
    $veille = (powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE | Select-String "0x[0-9a-fA-F]{8}" | Select-Object -Last 2 | Select-Object -First 1)
    if ($veille -and ($veille.Line -notmatch "0x00000000")) { $refus += "le PC peut se mettre en veille sur secteur (la couper)" }
    if ($refus.Count) { Write-Output ("PAS LANCE : " + ($refus -join " | ")); exit 2 }
    Write-Output "controle de depart : memoire libre $libre Go (besoin $BesoinGo), disques et veille bons, editeur Unreal ferme"
}

$j = $Journal -replace '\\', '/'
$boucle = @"
export PATH=/usr/bin:/mingw64/bin:`$PATH; n=0; : > '$j'
while true; do
  n=`$((n+1)); echo "=== essai `$n, `$(date '+%d/%m %H:%M')" >> '$j'
  bash '$Script' $($Arguments -join ' ') > '$j.essai' 2>&1; code=`$?
  grep -v '^code=' '$j.essai' >> '$j'
  if [ `$code -eq 0 ]; then echo 'code=0' >> '$j'; break; fi
  if [ `$n -gt $Relances ]; then echo "PLANTE POUR DE BON apres `$n essais (code `$code), `$(date '+%d/%m %H:%M')" >> '$j'; echo "code=`$code" >> '$j'; break; fi
  echo "essai `$n plante (code `$code) : relance dans 2 minutes" >> '$j'; sleep 120
done
"@
$fichier = Join-Path $env:TEMP ("atelya-gardien-{0}.sh" -f (Get-Date -Format "yyyyMMdd-HHmmss"))
[System.IO.File]::WriteAllText($fichier, ($boucle -replace "`r`n", "`n"), (New-Object System.Text.UTF8Encoding($false)))
$p = Start-Process -FilePath $bash -ArgumentList @("`"$($fichier -replace '\\', '/')`"") -WorkingDirectory $depot -WindowStyle Hidden -PassThru
$g = Start-Process powershell -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$(Join-Path $PSScriptRoot 'garde_memoire.ps1')`"", "-Journal", "`"$Journal`"") -WorkingDirectory $depot -WindowStyle Hidden -PassThru
Write-Output "lance, a part de la conversation : calcul $($p.Id), garde de la memoire $($g.Id) ; journal : $Journal"
exit 0
