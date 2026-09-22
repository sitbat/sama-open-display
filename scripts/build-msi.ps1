param(
    [string]$Wix = 'wix',
    [switch]$BuildApp
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Payload = Join-Path $ProjectRoot 'dist\SAMA-Open-Display-WinUI'
$Installer = Join-Path $ProjectRoot 'installer\SAMAOpenDisplay.wxs'
$Output = Join-Path $ProjectRoot 'dist\SAMA-Open-Display-1.0.0-win-x64.msi'
$InstallerAssets = Join-Path $ProjectRoot 'work\installer-assets'

if ($BuildApp) {
    & (Join-Path $PSScriptRoot 'build-winui.ps1')
    if ($LASTEXITCODE -ne 0) { throw "Application build failed with exit code $LASTEXITCODE" }
}
if (-not (Test-Path -LiteralPath (Join-Path $Payload 'SAMAOpenDisplay.exe'))) {
    throw "Build the application first: .\scripts\build-winui.ps1"
}

& (Join-Path $PSScriptRoot 'generate-msi-assets.ps1') -OutputDirectory $InstallerAssets
& $Wix build $Installer -arch x64 -culture zh-CN -ext WixToolset.UI.wixext/6.0.0 -ext WixToolset.Util.wixext/6.0.0 `
    -d "PayloadRoot=$Payload" -d "InstallerAssets=$InstallerAssets" -out $Output -pdbtype none
if ($LASTEXITCODE -ne 0) { throw "MSI build failed with exit code $LASTEXITCODE" }

# Guard against accidentally publishing WiX's sample agreement again.
$windowsInstaller = New-Object -ComObject WindowsInstaller.Installer
$database = $windowsInstaller.OpenDatabase($Output, 0)
$view = $database.OpenView("SELECT ``Text`` FROM ``Control`` WHERE ``Dialog_`` = 'LicenseAgreementDlg' AND ``Control`` = 'LicenseText'")
$view.Execute()
$record = $view.Fetch()
$agreement = if ($null -ne $record) { $record.StringData(1) } else { '' }
$view.Close()
if (-not $agreement.Contains('SAMA Open Display is free software') -or
    $agreement.Contains('Lorem ipsum dolor sit amet')) {
    throw 'The MSI does not contain the project license notice.'
}
Write-Host "Built MSI: $Output"
