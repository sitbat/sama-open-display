param(
    [string]$Wix = 'wix',
    [switch]$BuildApp
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Payload = Join-Path $ProjectRoot 'dist\SAMA-Open-Display-WinUI'
$Installer = Join-Path $ProjectRoot 'installer\SAMAOpenDisplay.wxs'
$Output = Join-Path $ProjectRoot 'dist\SAMA-Open-Display-1.0.0-win-x64.msi'

if ($BuildApp) {
    & (Join-Path $PSScriptRoot 'build-winui.ps1')
    if ($LASTEXITCODE -ne 0) { throw "Application build failed with exit code $LASTEXITCODE" }
}
if (-not (Test-Path -LiteralPath (Join-Path $Payload 'SAMAOpenDisplay.exe'))) {
    throw "Build the application first: .\scripts\build-winui.ps1"
}

& $Wix build $Installer -arch x64 -culture zh-CN -ext WixToolset.UI.wixext/6.0.0 `
    -d "PayloadRoot=$Payload" -out $Output -pdbtype none
if ($LASTEXITCODE -ne 0) { throw "MSI build failed with exit code $LASTEXITCODE" }
Write-Host "Built MSI: $Output"
