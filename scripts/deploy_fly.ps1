# Deployment des FMM Live Moderators auf Fly.io (Frankfurt).
# Voraussetzung: flyctl installiert und `fly auth login` erledigt.
param(
    [Parameter(Mandatory = $true)][string]$AppName,
    [string]$Region = "fra",
    [string]$Model = ""
)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$fly = (Get-Command fly -ErrorAction SilentlyContinue)
if (-not $fly) { $fly = (Get-Command flyctl -ErrorAction SilentlyContinue) }
if (-not $fly) { throw "flyctl nicht gefunden. Installation: iwr https://fly.io/install.ps1 -useb | iex" }
$fly = $fly.Source

# 1) App anlegen (falls noch nicht vorhanden)
$apps = & $fly apps list --json | ConvertFrom-Json
if (-not ($apps | Where-Object { $_.Name -eq $AppName })) {
    Write-Host "Lege App $AppName an ..."
    & $fly apps create $AppName
}
$toml = (Get-Content fly.toml -Raw) -replace '(?m)^app = ".*"', "app = `"$AppName`""
[IO.File]::WriteAllText((Join-Path (Get-Location) "fly.toml"), $toml, (New-Object Text.UTF8Encoding($false)))

# 2) Volume anlegen (falls noch nicht vorhanden)
$vols = & $fly volumes list -a $AppName --json | ConvertFrom-Json
if (-not ($vols | Where-Object { $_.name -eq "moderator_data" })) {
    Write-Host "Lege Speicher-Volume an ..."
    & $fly volumes create moderator_data --size 1 --region $Region -a $AppName --yes
}

# 3) Secrets setzen
$publicUrl = "https://$AppName.fly.dev"
$tokenFile = Join-Path ([Environment]::GetFolderPath("Desktop")) "ADMIN_TOKEN_Live_Moderator.txt"
$secretList = & $fly secrets list -a $AppName --json | ConvertFrom-Json
$hasAdmin = [bool]($secretList | Where-Object { $_.Name -eq "ADMIN_TOKEN" })
$secretArgs = @("PUBLIC_URL=$publicUrl")
if (-not $hasAdmin) {
    $bytes = New-Object byte[] 24; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $adminToken = [Convert]::ToBase64String($bytes).Replace("+", "-").Replace("/", "_").TrimEnd("=")
    Set-Content -Path $tokenFile -Value $adminToken -Encoding ascii
    Write-Host "ADMIN_TOKEN erzeugt und gespeichert: $tokenFile"
    $secretArgs += "ADMIN_TOKEN=$adminToken"
}
if (-not ($secretList | Where-Object { $_.Name -eq "ANTHROPIC_API_KEY" })) {
    $sec = Read-Host "Anthropic-API-Schluessel (Eingabe verdeckt)" -AsSecureString
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
    if ($plain) { $secretArgs += "ANTHROPIC_API_KEY=$plain" }
}
if ($Model) { $secretArgs += "LM_MODEL=$Model" }
& $fly secrets set @secretArgs -a $AppName --stage

# 4) Deploy
& $fly deploy -a $AppName --ha=false
Start-Sleep -Seconds 5
$health = Invoke-RestMethod "$publicUrl/healthz"
Write-Host "Online: $publicUrl  (Version $($health.version))"
Write-Host "Agentur-Dashboard: $publicUrl/admin"
