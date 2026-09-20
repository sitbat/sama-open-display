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

    $PyInstallerArgs = @(
        '--noconfirm', '--clean', '--windowed', '--onefile',
        '--name', 'SAMA-OpenDisplay',
        '--collect-all', 'PIL',
        '--collect-all', 'psutil'
    )
    if ($WithVideo) {
        $PyInstallerArgs += @('--collect-all', 'cv2')
    }
    $PyInstallerArgs += 'run_gui.py'
    & $Python -m PyInstaller @PyInstallerArgs
    Write-Host "Built: $ProjectRoot\dist\SAMA-OpenDisplay.exe"
} finally {
    Pop-Location
}

