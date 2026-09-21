# SAMA Open Display 0.5.0

SAMA Open Display is an open-source tool for displaying custom content on
compatible SAMA screen devices. It is an unofficial community project.

## Highlights

- New light-first, Fluent-inspired Windows interface with a dark-mode switch.
- New SAMA horse-head application icon with an open-source badge.
- Importable display themes with live 1568×720 preview.
- Three built-in layouts: dashboard, minimal clock, and system grid.
- `.sodpkg` plugin specification v1 with manifest, semantic version, plugin
  identity, validation, and data-only security boundary.
- Example `SAMA 网格` theme plugin included outside the executable.
- Directory-based Windows package: configuration, plugins, assets, docs, DLLs,
  and runtime remain external to the 4.5 MB main executable.

## Validation

- 46 unit tests pass (one optional OpenCV test skipped in the lightweight build).
- Windows GUI launch verified under Windows 11.
- Hardware writes remain confirmation-gated and device-identity checked.

Windows archive: `SAMA-Open-Display-0.5.0-Windows-x64.zip`
SHA-256: `6A9BE623490D44132190401A664E656CBBEFC9768C5F211C96C3A3B705B01079`
