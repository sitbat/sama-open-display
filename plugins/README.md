# SamaRP plugins

This directory stores installed `.samarppkg` files and `plugins.json`, which
contains enable/disable state. Packages stay external to `SamaRP.exe`.

The bundled system-metrics provider exposes permission-scoped, read-only
computer data. Themes can list its plugin ID in `plugin.dependencies`.

The release also bundles `org.samarpproject.system-dashboard` as the default
selectable theme. The former SAMA Grid theme is not preinstalled.
