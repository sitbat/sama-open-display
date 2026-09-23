# `.sodpkg` 插件规范（schema 2）

SAMA Open Display 使用 ZIP 格式的 `.sodpkg` 文件。一个包只能是 `theme`（布局主题）或 `data-provider`（数据接口）。schema 1 包继续兼容；schema 2 增加自定义布局和可执行数据接口。

发行包的 `plugins/` 目录只预装系统指标数据接口，主题默认内置于程序。用户可在“插件”页批量导入、启停和卸载包。包和状态文件 `plugins/plugins.json` 位于主 EXE 外部。

## 包结构与清单

文件必须放在 ZIP 根目录，不能只压入一个上级文件夹。以数据接口为例：

```text
sensor.sodpkg
├── manifest.toml
├── provider.toml
└── sensor.exe
```

`manifest.toml`：

```toml
[plugin]
schema = 2
id = "org.example.sensor"
name = "Example Sensor"
version = "1.0.0"
author = "Example author"
kind = "data-provider"
entry = "provider.toml"
description = "Provides sensor values"
dependencies = []
permissions = ["code.execute"]
```

`id` 使用 3–64 个小写字母、数字、点、下划线或连字符，以字母或数字开头；版本使用 `主.次.修订` 格式，可带语义化版本后缀。`entry` 必须是包根目录中的文件。`dependencies` 是插件 ID 数组；主题的前置只能是数据接口。前置缺失或未启用时，主题不会出现在可选列表中；停用或卸载正在被启用主题使用的数据接口会被阻止。

## 数据接口

内置的 schema 1 `builtin.system` 接口通过清单权限选择只读系统字段：`system.cpu`、`system.memory`、`system.uptime`、`storage.usage`、`network.counters`、`process.summary`。它的 `provider.toml` 仅需：

```toml
[provider]
adapter = "builtin.system"
```

自定义数据接口使用 schema 2 的 `external.process`，清单必须包含 `code.execute` 权限。`provider.toml` 示例：

```toml
[provider]
adapter = "external.process"
command = "sensor.exe"
timeout_ms = 1000
mode = "resident"
refresh_interval_ms = 60000

[fields]
temperature = "number"
fan_rpm = "integer"
profile = "string"
alarm = "boolean"
```

`command` 是包根目录的 Windows `.exe` 文件，建议做成无额外文件依赖的单文件程序；单次采样超时值允许 100–10000 毫秒。`refresh_interval_ms` 是采样间隔，范围 1000–300000 毫秒（最多 5 分钟）；常驻模式默认 60000 毫秒。`[fields]` 至少声明一个字段。字段类型为 `number`（有限数值）、`integer`、`string` 或 `boolean`，字段名最长 64 个字符。

`mode = "resident"` 使用常驻进程：持续显示依赖该接口的主题时，宿主启动一次 EXE，按采样间隔向它发送多条请求；切换到不依赖它的主题、停止持续发送或后端退出时，先发送关闭请求，等待 0.5 秒，未退出则终止进程。没有声明 `mode` 的旧插件仍按 `oneshot` 模式每次启动、返回一次结果并退出，默认采样间隔为 1 秒。旧的单次请求程序不能仅靠修改 `provider.toml` 变成常驻程序，必须实现下面的持续读写协议。

常驻程序应逐行读取标准输入。每收到一条 `sample` 请求，就向标准输出写入**一行** JSON 对象并刷新输出缓冲：

```json
{"protocol": 2, "plugin_id": "org.example.sensor", "action": "sample"}
```

收到 `shutdown` 请求后应自行退出；无需回复：

```json
{"protocol": 2, "plugin_id": "org.example.sensor", "action": "shutdown"}
```

标准输出只能用于逐行 JSON 响应，日志请写入标准错误。采样超时、协议错误或异常退出后，宿主会终止该进程，并在下一次重试时重新启动。一次失败不会阻止画面继续生成。

可运行的最小 C# 示例在 `examples/providers/resident-counter/`。用 `dotnet publish examples/providers/resident-counter/ResidentCounter.csproj -c Release` 生成单文件 EXE，再把 `manifest.toml`、`provider.toml` 和生成的 `ResidentCounter.exe` 一起放在 `.sodpkg` ZIP 根目录；配套布局主题在 `examples/themes/resident-counter-screen/`，需单独打包成主题插件。示例的 `count` 字段每次采样递增，可用来验证进程确实被复用。

旧版 `oneshot` 模式继续使用以下单次请求协议：

每次调用时，宿主在标准输入发送一条 JSON 请求：

```json
{"protocol": 1, "plugin_id": "org.example.sensor"}
```

程序向标准输出写一条 JSON 对象并以退出码 0 结束，例如（常驻模式也返回同样的对象，但每次响应须以换行结尾，并且不会在采样后退出）：

```json
{"temperature": 52.5, "fan_rpm": 1180, "profile": "Silent", "alarm": false}
```

返回字段只能是 `[fields]` 中声明的名称，值必须符合类型。宿主会加上插件 ID 前缀，主题可绑定 `org.example.sensor.temperature` 等字段。返回值超过 1 MB、超时、退出失败或类型不符时，该次采样会被跳过，画面继续生成。运行中的主题只调用自己声明为前置的可执行接口；命令行 `metrics` 会主动采样所有已启用的数据接口并在命令结束时关闭进程。采样间隔内复用上次成功的结果，不会每帧重复请求接口。

外部 EXE 会被提取到 `plugins/.runtime/<插件 ID>/` 下，更新或卸载插件时清理。它在独立进程中运行，但仍具有当前 Windows 用户的访问权限，并非系统级沙箱。安装界面会显示执行权限警告；只安装可信来源的可执行数据插件。

## 自定义布局主题

主题包至少包含 `manifest.toml` 与 `theme.toml`。下面的清单把上面的数据接口声明为前置：

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

`theme.toml` 使用 1568 × 720 画布。元素按文件中的先后顺序绘制；主题可以使用静态文本，也可以绑定时间或前置接口的数据：

```toml
[theme]
id = "sensor-screen"
name = "Sensor Screen"

[display]
preset = "custom"

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
type = "text"
x = 75
y = 325
text = "Sensor dashboard"
font_size = 36
```

支持的元素：

| `type` | 主要字段 | 用途 |
| --- | --- | --- |
| `rectangle` | `x`, `y`, `width`, `height`, `background`, `radius` | 色块 |
| `text` | `text` 或 `bind`, `format`, `prefix`, `suffix`, `font_size`, `bold`, `align`, `color` | 静态或动态文字 |
| `progress` | `bind`, `minimum`, `maximum`, `color`, `background`, `radius` | 数值进度条 |
| `image` | `asset`, `fit`, `x`, `y`, `width`, `height` | 包根目录的图片；`fit` 为 `cover` 或 `contain` |

矩形、进度条和图片都必须有正尺寸，元素不能超出画布。颜色可写 `#RRGGBB` 或使用上表中的调色板字段名。图片元素的 `asset` 必须位于包根目录；整张背景图片可在 `[display]` 中用 `background_image = "background.png"` 指定。

除了数据接口字段，`bind` 还可使用 `clock.time`、`clock.time_seconds`、`clock.date`、`clock.weekday` 和 `clock.timestamp`。旧主题仍可使用 `dashboard`、`minimal_clock` 或 `system_grid` 预设；`custom` 需要 schema 2。声明式主题不运行代码。

## 制作和检查包

以 PowerShell 为例，在包含 `manifest.toml` 和入口文件的目录中压缩根目录文件，再将生成的 ZIP 改为 `.sodpkg`。先检查包结构，再导入：

```powershell
Compress-Archive -Path .\manifest.toml,.\theme.toml -DestinationPath .\sensor-screen.zip
Rename-Item .\sensor-screen.zip sensor-screen.sodpkg
python -m sama_display plugin-inspect .\sensor-screen.sodpkg
python -m sama_display plugin-install .\sensor-screen.sodpkg --directory plugins
python -m sama_display plugin-list --directory plugins
```

若主题依赖数据接口，先安装并启用数据接口，再安装主题。`plugin-inspect` 验证包本身；`plugin-list` 可检查依赖问题；`theme-list --directory plugins` 可确认主题是否进入可选列表。

包压缩后上限为 20 MB，解压后总量上限为 50 MB；自定义布局最多 128 个元素，单张图片上限为 12 MB。未知 schema、类型、权限和清单选项会被拒绝。
