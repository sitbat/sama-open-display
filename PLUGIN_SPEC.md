# SAMA Open Display Plugin Specification v2

SAMA Open Display uses external ZIP packages with the `.sodpkg` extension. A
package is one of exactly two kinds:

- `data-provider`: exposes named data fields.
- `theme`: defines a display layout and may depend on data providers.

Schema 1 packages remain supported. Schema 2 adds external provider processes
and free-form declarative layouts.

## Common manifest

Every package contains `manifest.toml` at its root:

```toml
[plugin]
schema = 2
id = "org.example.sensor"
name = "Example Sensor"
version = "1.0.0"
author = "Example author"
kind = "data-provider"
entry = "provider.toml"
description = "Provides custom sensor values"
dependencies = []
permissions = ["code.execute"]
```

IDs are stable lowercase identifiers and versions use semantic versioning.
Theme dependencies must point to installed, enabled `data-provider` plugins.
The host refuses to enable, disable or uninstall packages when doing so would
break this dependency graph. Executable providers are invoked only while the
active theme declares them as prerequisites; merely enabling one does not run
it in the background.

## Data-provider plugins

### Built-in adapter

The bundled schema-1 provider uses `builtin.system`. It exposes only the
permissions present in its manifest:

- `system.cpu`, `system.memory`, `system.uptime`
- `storage.usage`, `network.counters`, `process.summary`

```toml
[provider]
adapter = "builtin.system"
```

### External process adapter

Schema 2 providers can ship a Windows executable at the package root:

```text
sensor.sodpkg
├── manifest.toml
├── provider.toml
└── sensor.exe
```

`provider.toml` declares the executable, timeout and public interface:

```toml
[provider]
adapter = "external.process"
command = "sensor.exe"
timeout_ms = 1000

[fields]
temperature = "number"
fan_rpm = "integer"
profile = "string"
alarm = "boolean"
```

The manifest must use schema 2 and request `code.execute`. The host sends one
JSON request on standard input:

```json
{"protocol": 1, "plugin_id": "org.example.sensor"}
```

The process writes one JSON object to standard output and exits with code 0:

```json
{"temperature": 52.5, "fan_rpm": 1180, "profile": "Silent", "alarm": false}
```

Returned keys must be declared in `[fields]` and values must match their types.
The host namespaces them before exposing them to themes:

```text
org.example.sensor.temperature
org.example.sensor.fan_rpm
org.example.sensor.profile
org.example.sensor.alarm
```

The executable runs in a separate process with redirected standard streams and
a 100-10000 ms timeout. This protects the main process from crashes, but it is
not an OS sandbox: the executable still has the current Windows user's access.
The plugin center therefore shows an explicit executable-code warning before
installation. Distribute providers as self-contained single-file executables.

## Free-layout theme plugins

A schema-2 theme declares its provider prerequisites and uses `preset="custom"`:

```toml
[plugin]
schema = 2
id = "org.example.sensor-screen"
name = "Sensor Screen"
version = "1.0.0"
author = "Example author"
kind = "theme"
entry = "theme.toml"
dependencies = ["org.example.sensor"]
permissions = []
```

The layout canvas is 1568 x 720. Elements are painted in declaration order:

```toml
[theme]
id = "sensor-screen"
name = "Sensor Screen"

[display]
preset = "custom"
background_image = "background.png" # optional

[palette]
background = "#07111f"
surface = "#10243b"
surface_alt = "#1c3850"
text = "#eef7ff"
muted = "#8ba7bd"
accent = "#32d3a2"
accent_2 = "#4fb6ff"
accent_3 = "#b084ff"

[[element]]
type = "rectangle"
x = 40
y = 40
width = 600
height = 260
background = "surface"
radius = 28

[[element]]
type = "text"
x = 75
y = 75
width = 520
bind = "org.example.sensor.temperature"
format = ".1f"
suffix = " °C"
font_size = 84
bold = true
color = "accent"

[[element]]
type = "progress"
x = 75
y = 210
width = 500
height = 34
bind = "org.example.sensor.temperature"
minimum = 0
maximum = 100
color = "accent"
background = "surface_alt"
radius = 17

[[element]]
type = "image"
x = 700
y = 40
width = 800
height = 640
asset = "illustration.png"
fit = "contain"
```

Supported elements:

- `rectangle`: position, size, background and corner radius.
- `text`: static text or a `bind`, number format, prefix/suffix, font size,
  weight, color and left/center/right alignment.
- `progress`: numeric binding, min/max, colors and corner radius.
- `image`: package-root image asset with `cover` or `contain` fitting.

Colors may be `#RRGGBB` or a palette name. In addition to provider fields,
themes may bind `clock.time`, `clock.time_seconds`, `clock.date`,
`clock.weekday` and `clock.timestamp`.

Legacy presets `dashboard`, `minimal_clock` and `system_grid` remain available.

## Validation and storage

- Package size is limited to 20 MB and expanded content to 50 MB.
- Layouts are limited to 128 elements and validated against the 1568x720 canvas.
- Image assets must be package-root files and may not exceed 12 MB each.
- Unknown schemas, plugin kinds, permissions and manifest options are rejected.
- Provider output is type checked and undeclared fields are rejected.
- Packages remain outside the main EXE in the `plugins` directory.
- Provider executables are materialized under `plugins/.runtime` and removed on
  update or uninstall.
- Declarative theme packages never execute code.
