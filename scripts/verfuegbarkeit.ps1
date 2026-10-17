# Verfuegbarkeitstest des oeffentlichen Einrichtungslinks (laeuft per Windows-Aufgabe alle 30 Minuten).
# Meldet sich nur bei Statuswechsel (Ausfall / wieder erreichbar) per Windows-Benachrichtigung. Kostenlos.
param(
    [string[]]$Urls = @("https://nikolajfischer-svg.github.io/fmm-live-moderator/", "https://nikolajfischer-svg.github.io/"),
    # Pruefmerkmal je Adresse (gleiche Reihenfolge): Einrichtungsseite bzw. Weiterleitung dorthin
    [string[]]$Markers = @("Dein eigener KI-Moderator", "url=/fmm-live-moderator/"),
    [switch]$Test
)
$ErrorActionPreference = "SilentlyContinue"
$dir = Join-Path $env:LOCALAPPDATA "FMM_Live_Moderator"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$log = Join-Path $dir "verfuegbarkeit.log"
$stateFile = Join-Path $dir "verfuegbarkeit_status.txt"

function Notify([string]$title, [string]$text) {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    $n = New-Object System.Windows.Forms.NotifyIcon
    $n.Icon = [System.Drawing.SystemIcons]::Warning
    $n.BalloonTipTitle = $title
    $n.BalloonTipText = $text
    $n.Visible = $true
    $n.ShowBalloonTip(15000)
    Start-Sleep -Seconds 16
    $n.Dispose()
}

$fails = @()
for ($i = 0; $i -lt $Urls.Count; $i++) {
    $u = $Urls[$i]
    $Marker = if ($i -lt $Markers.Count) { $Markers[$i] } else { $Markers[0] }
    $ok = $false
    for ($try = 1; $try -le 3 -and -not $ok; $try++) {
        try {
            $r = Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 20
            if ($r.StatusCode -eq 200 -and $r.Content -like "*$Marker*") { $ok = $true }
        } catch {}
        if (-not $ok) { Start-Sleep -Seconds 20 }
    }
    if (-not $ok) { $fails += $u }
}
$now = Get-Date -Format "yyyy-MM-dd HH:mm"
$status = if ($fails.Count -eq 0) { "OK" } else { "AUSFALL" }
Add-Content -Path $log -Value "$now $status $($fails -join ' ')" -Encoding utf8
$previous = if (Test-Path $stateFile) { (Get-Content $stateFile -Raw).Trim() } else { "OK" }
Set-Content -Path $stateFile -Value $status -Encoding ascii

if ($Test) { Notify "FMM Live Moderator - Test" "Der Verfügbarkeitstest ist eingerichtet. Aktueller Status: $status"; exit 0 }
if ($status -eq "AUSFALL" -and $previous -ne "AUSFALL") {
    Notify "FMM Live Moderator NICHT erreichbar" "Einrichtungsseite antwortet nicht: $($fails -join ', '). Bitte Claude Bescheid geben."
} elseif ($status -eq "OK" -and $previous -eq "AUSFALL") {
    Notify "FMM Live Moderator wieder erreichbar" "Die Einrichtungsseite funktioniert wieder."
}
