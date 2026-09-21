# SAMA display themes

The application imports portable `.sodpkg` plugins. A theme plugin is a ZIP
archive whose root contains `manifest.toml`, `theme.toml`, and optionally one
background image.

Supported display presets are `dashboard`, `minimal_clock`, and `system_grid`.
Colors use `#RRGGBB`. See `examples/themes/sama-grid/theme.toml` for a complete
example. Theme packages stay outside the executable in the `themes` directory.
