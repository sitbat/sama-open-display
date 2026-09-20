param(
    [switch]$WithVideo
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
Push-Location $ProjectRoot
try {
    if (-not (Test-Path $Python)) {
        py -3 -m venv .venv
    }
    & $Python -m pip install --upgrade pip
    if ($WithVideo) {
        & $Python -m pip install '.[build,video]'
    } else {
        & $Python -m pip install '.[build]'
    }
    & $Python -m unittest discover -v
    if ($LASTEXITCODE -ne 0) { throw "Unit tests failed with exit code $LASTEXITCODE" }

    # A venv created from the portable Windows Python distribution does not
    # automatically expose its sibling Tcl/Tk data directories. Point
    # PyInstaller at the base installation so the onedir runtime contains a
    # working GUI rather than silently excluding tkinter.
    $BasePrefix = & $Python -c 'import sys; print(sys.base_prefix)'
    $TclLibrary = Join-Path $BasePrefix 'tcl\tcl8.6'
    $TkLibrary = Join-Path $BasePrefix 'tcl\tk8.6'
    if (-not (Test-Path -LiteralPath $TclLibrary) -or -not (Test-Path -LiteralPath $TkLibrary)) {
        throw "Tcl/Tk runtime was not found below $BasePrefix"
    }
    $env:TCL_LIBRARY = $TclLibrary
    $env:TK_LIBRARY = $TkLibrary

    $PyInstallerArgs = @(
        '--noconfirm', '--clean', '--windowed', '--onedir',
        '--contents-directory', 'runtime',
        '--name', 'SamaRP',
        '--icon', 'assets\app-icon.ico',
        '--exclude-module', 'pytest'
    )
    if ($WithVideo) {
        $PyInstallerArgs += @('--collect-all', 'cv2')
    } else {
        $PyInstallerArgs += @('--exclude-module', 'cv2')
    }
    $PyInstallerArgs += 'run_gui.py'
    & $Python -m PyInstaller @PyInstallerArgs
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }
    $ReleaseDir = Join-Path $ProjectRoot 'dist\SamaRP'
    New-Item -ItemType Directory -Force -Path (Join-Path $ReleaseDir 'assets') | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $ReleaseDir 'plugins') | Out-Null
    Copy-Item -LiteralPath (Join-Path $ProjectRoot 'assets\app-icon.ico') -Destination (Join-Path $ReleaseDir 'assets\app-icon.ico') -Force
    Copy-Item -Path (Join-Path $ProjectRoot 'plugins\*.samarppkg') -Destination (Join-Path $ReleaseDir 'plugins') -Force
    Copy-Item -LiteralPath (Join-Path $ProjectRoot 'plugins\README.md') -Destination (Join-Path $ReleaseDir 'plugins\README.md') -Force
    Copy-Item -LiteralPath (Join-Path $ProjectRoot 'examples\config.toml') -Destination (Join-Path $ReleaseDir 'config.toml') -Force
    Copy-Item -LiteralPath (Join-Path $ProjectRoot 'README.md') -Destination (Join-Path $ReleaseDir 'README.md') -Force
    Copy-Item -LiteralPath (Join-Path $ProjectRoot 'LICENSE') -Destination (Join-Path $ReleaseDir 'LICENSE') -Force
    Copy-Item -LiteralPath (Join-Path $ProjectRoot 'PROTOCOL.md') -Destination (Join-Path $ReleaseDir 'PROTOCOL.md') -Force
    Copy-Item -LiteralPath (Join-Path $ProjectRoot 'PLUGIN_SPEC.md') -Destination (Join-Path $ReleaseDir 'PLUGIN_SPEC.md') -Force
    Write-Host "Built: $ReleaseDir\SamaRP.exe"
    Write-Host "Dependencies: $ReleaseDir\runtime"
} finally {
    Pop-Location
}
