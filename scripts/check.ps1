$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $ProjectRoot
try {
    python -m compileall -q sama_display tests
    python -m unittest discover -v
    python -m sama_display detect
    python -m sama_display plan
    python -m sama_display preview --config examples\config.toml --output outputs\dashboard.png
} finally {
    Pop-Location
}

