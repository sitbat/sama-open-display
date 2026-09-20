# SamaRP 0.6.0

## Highlights

- Dedicated plugin-center page with multi-select and batch installation.
- Enable, disable, refresh, and uninstall operations with dependency protection.
- Theme plugins can declare data-provider plugins as prerequisites.
- Permission-scoped, read-only host data API for CPU, memory, uptime, storage,
  network counters, and process summary.
- Bundled `system-metrics` provider and dependent `SAMA 网格` theme.
- External plugin state in `plugins/plugins.json`; packages and state remain
  outside the executable.
- Windows 11 polish: high-DPI awareness, rounded window corners, dark title bar,
  Mica backdrop hint, native controls, and light/dark appearance.

## Security

Plugin schema v1 stays declarative. Packages cannot execute Python, DLLs,
scripts, commands, or hardware writes. Data providers use allow-listed host
adapters and explicit permissions.

## Validation

- 48 unit tests pass; one optional OpenCV test is skipped in the lightweight build.
- Source GUI startup verified on Windows 11.

Windows archive: `SamaRP-0.6.0-Windows-x64.zip`

SHA-256: `056E9D29CBFE10A4221171069A0BFE54B9A62D7F3C13B6AD58496E80A8D813E1`
