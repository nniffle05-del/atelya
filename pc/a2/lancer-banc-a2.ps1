# Lance banc-a2.ps1 en empechant la mise en veille de Windows pendant le calcul (sans changer les reglages :
# l'interdiction tombe d'elle-meme quand cette fenetre se ferme).
param([string]$Phase = 'tout', [int]$Nombre = 0, [string]$Depuis = '', [string]$Sans = '')
Add-Type -Namespace Atelya -Name Veille -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("kernel32.dll")]
public static extern uint SetThreadExecutionState(uint esFlags);
'@
# ES_CONTINUOUS (0x80000000) | ES_SYSTEM_REQUIRED (0x00000001) : le PC reste eveille, l'ecran peut s'eteindre
[Atelya.Veille]::SetThreadExecutionState([uint32]2147483649) | Out-Null
Write-Output "Veille bloquee pendant le calcul. NE FERMEZ PAS CETTE FENETRE (cela arreterait le calcul)."
& (Join-Path $PSScriptRoot 'banc-a2.ps1') -Phase $Phase -Nombre $Nombre -Depuis $Depuis -Sans $Sans
$code = $LASTEXITCODE
[Atelya.Veille]::SetThreadExecutionState([uint32]2147483648) | Out-Null
Write-Output "Termine (code $code). La veille normale de Windows est retablie."
