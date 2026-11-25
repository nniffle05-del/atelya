# LE GARDE DE LA MÉMOIRE d'un long calcul (25/11/2026, demande de NT : « ces erreurs-là, il faudrait que tu sois capable de les
# prédire, ou de les surveiller du moins » ; le matin, un tournage Unreal avait planté à la première vue, mémoire du PC pleine,
# et la conversation de Claude était tombée avec lui : personne n'a rien vu pendant 6 h 30).
#
#     powershell -File pc\verification\garde_memoire.ps1 <journal du calcul> [-Heures 12] [-AlerteGo 2]
#
# Tourne À PART de la conversation. Toutes les 30 secondes il écrit une ligne dans <journal>.memoire.csv (heure, mémoire libre
# en Go — RAM + réserve sur disque —, RAM libre, ce qu'Unreal, Blender et Python occupent) ; sous AlerteGo de mémoire libre il
# écrit <journal>.ALERTE.txt (avec les plus gros programmes ouverts). Il s'arrête quand le journal dit « code= » (fini), ou
# après le nombre d'heures donné. Rien n'est tué, rien n'est fermé : il regarde et il écrit.
param([Parameter(Mandatory = $true)][string]$Journal, [double]$Heures = 12, [double]$AlerteGo = 2)
$csv = "$Journal.memoire.csv"
$alerte = "$Journal.ALERTE.txt"
if (-not (Test-Path -LiteralPath $csv)) { "heure;libre_go;ram_libre_go;unreal_go;blender_go;python_go" | Out-File -LiteralPath $csv -Encoding utf8 }
$fin = (Get-Date).AddHours($Heures)
$prive = { param($motif) [math]::Round((Get-Process | Where-Object { $_.ProcessName -match $motif } | Measure-Object PrivateMemorySize64 -Sum).Sum / 1GB, 2) }
while ((Get-Date) -lt $fin) {
    $os = Get-CimInstance Win32_OperatingSystem
    $libre = [math]::Round($os.FreeVirtualMemory / 1MB, 2)
    $ligne = "{0:dd/MM HH:mm:ss};{1};{2};{3};{4};{5}" -f (Get-Date), $libre, [math]::Round($os.FreePhysicalMemory / 1MB, 2), (& $prive "Unreal"), (& $prive "^blender"), (& $prive "^python")
    $ligne | Out-File -LiteralPath $csv -Encoding utf8 -Append
    if ($libre -lt $AlerteGo) {
        $gros = Get-Process | Sort-Object PrivateMemorySize64 -Descending | Select-Object -First 6 | ForEach-Object { "{0} {1:N1} Go" -f $_.ProcessName, ($_.PrivateMemorySize64 / 1GB) }
        ("{0:dd/MM HH:mm:ss} MEMOIRE PRESQUE PLEINE : {1} Go libres. Plus gros programmes : {2}" -f (Get-Date), $libre, ($gros -join " ; ")) | Out-File -LiteralPath $alerte -Encoding utf8 -Append
    }
    if ((Test-Path -LiteralPath $Journal) -and (Select-String -LiteralPath $Journal -Pattern "code=" -Quiet)) { break }
    Start-Sleep -Seconds 30
}
