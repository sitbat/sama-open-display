param(
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LicensePath = Join-Path $ProjectRoot 'LICENSE'
$IconPath = Join-Path $ProjectRoot 'assets\app-icon.png'
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

# WiX's stock license is placeholder text. Generate a simple RTF from the
# project's actual license notice so the MSI never embeds that placeholder.
$license = [System.IO.File]::ReadAllText($LicensePath, [System.Text.Encoding]::UTF8)
$escaped = $license.Replace('\', '\\').Replace('{', '\{').Replace('}', '\}')
$escaped = $escaped.Replace("`r`n", "`n").Replace("`r", "`n").Replace("`n", "\par`n")
$rtf = '{\rtf1\ansi\deff0{\fonttbl{\f0 Segoe UI;}}\f0\fs18 ' + $escaped + '}'
[System.IO.File]::WriteAllText(
    (Join-Path $OutputDirectory 'License.rtf'), $rtf, [System.Text.Encoding]::ASCII)

Add-Type -AssemblyName System.Drawing
$logo = [System.Drawing.Image]::FromFile($IconPath)
try {
    $banner = New-Object System.Drawing.Bitmap(493, 58)
    $graphics = [System.Drawing.Graphics]::FromImage($banner)
    try {
        $graphics.Clear([System.Drawing.Color]::White)
        $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $graphics.DrawImage($logo, 440, 5, 48, 48)
        $accent = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(0, 120, 215))
        try { $graphics.FillRectangle($accent, 0, 56, 493, 2) }
        finally { $accent.Dispose() }
        $banner.Save((Join-Path $OutputDirectory 'Banner.png'), [System.Drawing.Imaging.ImageFormat]::Png)
    }
    finally { $graphics.Dispose(); $banner.Dispose() }

    $dialog = New-Object System.Drawing.Bitmap(493, 312)
    $graphics = [System.Drawing.Graphics]::FromImage($dialog)
    try {
        $graphics.Clear([System.Drawing.Color]::White)
        $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $panel = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(232, 242, 252))
        try { $graphics.FillRectangle($panel, 0, 0, 150, 312) }
        finally { $panel.Dispose() }
        $graphics.DrawImage($logo, 19, 96, 112, 112)
        $dialog.Save((Join-Path $OutputDirectory 'Dialog.png'), [System.Drawing.Imaging.ImageFormat]::Png)
    }
    finally { $graphics.Dispose(); $dialog.Dispose() }
}
finally { $logo.Dispose() }
