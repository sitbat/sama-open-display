# SAMA Open Display plugins

This directory stores installed `.sodpkg` files and `plugins.json`, which
contains enable/disable state. Packages stay external to `SAMAOpenDisplay.exe`.

The bundled system-metrics provider exposes permission-scoped, read-only
computer data. Themes can list its plugin ID in `plugin.dependencies`.

Display themes are built into the application or installed by the user. The
release does not preinstall a theme plugin.
