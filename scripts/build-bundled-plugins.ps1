param()

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Source = Join-Path $ProjectRoot 'plugin_sources\system-dashboard'
$PluginDirectory = Join-Path $ProjectRoot 'plugins'
$TemporaryZip = Join-Path $PluginDirectory 'org.samarpproject.system-dashboard.zip'
$Destination = Join-Path $PluginDirectory 'org.samarpproject.system-dashboard.samarppkg'

New-Item -ItemType Directory -Force -Path $PluginDirectory | Out-Null
if (Test-Path -LiteralPath $TemporaryZip) {
    Remove-Item -LiteralPath $TemporaryZip -Force
}
if (Test-Path -LiteralPath $Destination) {
    Remove-Item -LiteralPath $Destination -Force
}
Compress-Archive -Path (Join-Path $Source '*') -DestinationPath $TemporaryZip -CompressionLevel Optimal
Move-Item -LiteralPath $TemporaryZip -Destination $Destination
Write-Host "Built bundled theme: $Destination"
