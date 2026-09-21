param()

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$FrontendProject = Join-Path $ProjectRoot 'frontend\SamaRP.WinUI\SamaRP.WinUI.csproj'
$FrontendBuild = Join-Path $ProjectRoot 'frontend\SamaRP.WinUI\bin\Release\net10.0-windows10.0.26100.0\win-x64'
$BackendBuild = Join-Path $ProjectRoot 'dist\SamaRP.Backend'
$ReleaseDir = Join-Path $ProjectRoot 'dist\SamaRP-WinUI'

Push-Location $ProjectRoot
try {
    if (-not (Test-Path -LiteralPath $Python)) {
        py -3 -m venv .venv
    }
    & $Python -m pip install --no-build-isolation '.[build]'
    if ($LASTEXITCODE -ne 0) { throw "Python dependencies failed with exit code $LASTEXITCODE" }
    & $Python -m unittest discover -v
    if ($LASTEXITCODE -ne 0) { throw "Python tests failed with exit code $LASTEXITCODE" }

    & $Python -m PyInstaller --noconfirm --clean --console --onedir `
        --contents-directory runtime --name SamaRP.Backend `
        --exclude-module cv2 --exclude-module tkinter run_backend.py
    if ($LASTEXITCODE -ne 0) { throw "Backend build failed with exit code $LASTEXITCODE" }

    $env:DOTNET_CLI_HOME = Join-Path $ProjectRoot 'work\dotnet-home'
    $env:DOTNET_SKIP_FIRST_TIME_EXPERIENCE = '1'
    $env:DOTNET_CLI_TELEMETRY_OPTOUT = '1'
    # The WinUI compiler places the app XBF files and MRT resource index in the
    # Release build directory. `dotnet publish -o` currently drops those files,
    # which produces an apparently complete folder that crashes at startup.
    & dotnet build $FrontendProject -c Release -r win-x64 --self-contained true -p:RestoreIgnoreFailedSources=true
    if ($LASTEXITCODE -ne 0) { throw "WinUI build failed with exit code $LASTEXITCODE" }

    if (-not (Test-Path -LiteralPath (Join-Path $FrontendBuild 'SamaRP.pri'))) {
        throw "WinUI resource index was not generated: $FrontendBuild\SamaRP.pri"
    }
    if (Test-Path -LiteralPath $ReleaseDir) {
        Remove-Item -LiteralPath $ReleaseDir -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
    Copy-Item -Path (Join-Path $FrontendBuild '*') -Destination $ReleaseDir -Recurse -Force

    $BackendDestination = Join-Path $ReleaseDir 'backend'
    New-Item -ItemType Directory -Force -Path $BackendDestination | Out-Null
    Copy-Item -Path (Join-Path $BackendBuild '*') -Destination $BackendDestination -Recurse -Force
    New-Item -ItemType Directory -Force -Path (Join-Path $ReleaseDir 'plugins') | Out-Null
    Copy-Item -Path (Join-Path $ProjectRoot 'plugins\*') -Destination (Join-Path $ReleaseDir 'plugins') -Recurse -Force
    Copy-Item -LiteralPath (Join-Path $ProjectRoot 'examples\config.toml') -Destination (Join-Path $ReleaseDir 'config.toml') -Force
    Copy-Item -LiteralPath (Join-Path $ProjectRoot 'README.md') -Destination (Join-Path $ReleaseDir 'README.md') -Force
    Copy-Item -LiteralPath (Join-Path $ProjectRoot 'LICENSE') -Destination (Join-Path $ReleaseDir 'LICENSE') -Force
    Copy-Item -LiteralPath (Join-Path $ProjectRoot 'PROTOCOL.md') -Destination (Join-Path $ReleaseDir 'PROTOCOL.md') -Force
    Copy-Item -LiteralPath (Join-Path $ProjectRoot 'PLUGIN_SPEC.md') -Destination (Join-Path $ReleaseDir 'PLUGIN_SPEC.md') -Force
    Write-Host "Built WinUI frontend: $ReleaseDir\SamaRP.exe"
    Write-Host "External backend: $BackendDestination\SamaRP.Backend.exe"
} finally {
    Pop-Location
}
