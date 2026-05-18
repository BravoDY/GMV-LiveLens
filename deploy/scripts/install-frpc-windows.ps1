param(
  [Parameter(Mandatory = $true)]
  [string]$Token,

  [string]$FrpVersion = "0.68.0",
  [string]$InstallDir = ""
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path "$PSScriptRoot\..\.."
$deployDir = Join-Path $root "deploy"
$frpDir = Join-Path $deployDir "frp"
if (-not $InstallDir) {
  $InstallDir = Join-Path $deployDir "frp-runtime"
}
$installDirResolved = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($InstallDir)
$zipPath = Join-Path $env:TEMP "frp_$FrpVersion`_windows_amd64.zip"
$downloadUrl = "https://github.com/fatedier/frp/releases/download/v$FrpVersion/frp_$FrpVersion`_windows_amd64.zip"

New-Item -ItemType Directory -Force -Path $installDirResolved | Out-Null
New-Item -ItemType Directory -Force -Path $frpDir | Out-Null

Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath
Expand-Archive -Path $zipPath -DestinationPath $env:TEMP -Force

$expanded = Join-Path $env:TEMP "frp_$FrpVersion`_windows_amd64"
Copy-Item -Path (Join-Path $expanded "frpc.exe") -Destination (Join-Path $installDirResolved "frpc.exe") -Force

$template = Get-Content -Raw -Path (Join-Path $frpDir "frpc.gmv-livelens.toml.example")
$config = $template.Replace("replace-with-the-same-strong-random-frp-token", $Token)
[System.IO.File]::WriteAllText((Join-Path $frpDir "frpc.toml"), $config, [System.Text.UTF8Encoding]::new($false))

Write-Host "FRP client installed:"
Write-Host "  exe:    $(Join-Path $installDirResolved "frpc.exe")"
Write-Host "  config: $(Join-Path $frpDir "frpc.toml")"
Write-Host "Start it with: 第2步_启动公网隧道.bat"
