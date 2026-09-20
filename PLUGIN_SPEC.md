# SamaRP Plugin Specification v1

SamaRP plugins are declarative ZIP packages using the `.samarppkg` extension.
They are external files and are never embedded in the main executable.

## Package layout

```text
example.samarppkg
├── manifest.toml
├── theme.toml
└── background.png       # optional
```

`manifest.toml`:

```toml
[plugin]
schema = 1
id = "org.example.clean-grid"
name = "Clean Grid"
version = "1.0.0"
author = "Example author"
kind = "theme"
entry = "theme.toml"
description = "A bright four-card system monitor"
```

Plugin IDs are stable lowercase identifiers. Versions follow semantic
versioning. Version 1 supports the `theme` kind. Theme plugins are data-only:
SamaRP does not execute Python, DLLs, scripts, or commands from a package.

## Theme entry

The entry file has `[theme]`, `[display]`, and `[palette]` sections. Supported
presets are `dashboard`, `minimal_clock`, and `system_grid`. Colors use
`#RRGGBB`. An optional `background_image` must point to a file in the package
root and may not exceed 12 MB. The whole package may not exceed 20 MB.

## Security and compatibility

- Packages are inspected before installation and are not extracted.
- Paths outside the ZIP root are rejected.
- Unknown schema versions, plugin kinds, and manifest keys are rejected.
- Installed packages remain in the external `themes` directory.
- Future executable plugin kinds will require an explicit permission model and
  will not be accepted by a v1 host.
