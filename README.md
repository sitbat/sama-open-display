# SAMA Open Display

用于给 SAMA USB 小屏显示自定义内容的开源工具。当前适配并经过真机验证的是 6.5 英寸设备：应用按 1568 × 720 横屏排版，再转换成设备使用的 720 × 1568 扫描缓冲区。

这是非官方社区项目，与 SAMA 品牌方没有隶属、授权或背书关系。当前支持主题仪表盘、图片和文本；主题与数据接口可通过 `.sodpkg` 插件扩展。

## 使用 Windows 程序

目录式发行包的入口是 `SAMAOpenDisplay.exe`。请保留它旁边的 DLL、`backend/` 和 `plugins/`，不要只复制 EXE。启动后：

1. 在“显示与设备”选择“使用主题”“加载图片”或“显示文本”。预览只在电脑上生成画面。
2. 确认右侧检测到目标 USB 小屏，再点击“发送当前画面”或“开始持续发送画面”。原厂程序占用显示串口时，请先退出原厂程序。
3. 在“插件”页批量导入、启停或卸载 `.sodpkg` 文件；在“设置”页配置外观、开机自启、启动后发送和系统托盘行为。

程序会在写入前握手，并核对设备返回的标识 `chs_65inch.dev1_rom1.91`。WinUI 发送按钮不再弹出二次确认；开启“启动软件即开始持续发送画面”后，检测到目标设备即可自动发送。持续发送默认目标为 1 FPS，实际速度取决于画面变化量和 USB 链路；帧传输较慢时不会累积待发送帧。切换到其他页面不停止持续发送，彻底退出程序或点击停止按钮才会停止。

内容模式、主题、图片路径、文本、适配方式和应用设置保存在 `%LOCALAPPDATA%\SAMA Open Display\settings.json`，下次启动会恢复。图片文件被移走时，显示内容会回退到主题。窗口默认收起左侧导航栏；是否在最小化或关闭时留在系统托盘可分别设置。

## 主题和数据插件

内置主题可直接使用，发行包默认只附带“系统指标接口”数据插件，不预装主题插件。外部插件有两类：

- 布局主题：用文本、矩形、进度条和图片组合 1568 × 720 画面，可绑定时间和数据字段。
- 数据接口：声明可供主题读取的字段；自定义接口可运行随插件提供的独立 Windows EXE。布局主题在清单中声明所需数据插件作为前置依赖。

启用数据接口并不会让它一直后台执行；当前主题使用其前置字段时才会在画面刷新中调用。`metrics` 命令会主动采样已启用的数据接口。可执行数据插件以当前 Windows 用户身份运行，安装前请确认来源；独立进程并不提供系统级沙箱。

插件安装和依赖规则、完整示例、输入输出协议见 [PLUGIN_SPEC.md](PLUGIN_SPEC.md)。

## 命令行与开发

源代码运行需要 Python 3.10+。WinUI 前端的构建目标是 Windows 11，需 .NET 10 SDK；`scripts/build-winui.ps1` 会安装 Python 构建依赖、运行测试，再生成后端与前端。源码命令行和经典 Python GUI 可独立运行。

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\python.exe -m sama_display detect
.\.venv\Scripts\python.exe -m sama_display preview --output outputs\dashboard.png
.\.venv\Scripts\python.exe -m unittest discover -v
```

离线预览图片、文本或已安装的主题：

```powershell
.\.venv\Scripts\python.exe -m sama_display preview --image D:\Pictures\example.png --output outputs\picture.png
.\.venv\Scripts\python.exe -m sama_display preview --text "Hello" --output outputs\text.png
.\.venv\Scripts\python.exe -m sama_display theme-list --directory plugins
.\.venv\Scripts\python.exe -m sama_display preview --theme-id midnight --plugins-directory plugins --output outputs\theme.png
```

`detect`、`preview`、`theme-list`、`plugin-list` 和 `plugin-inspect` 不向屏幕发送画面。命令行写入要求 `--write-hardware` 和与握手结果完全相同的 `--device-id`：

```powershell
.\.venv\Scripts\python.exe -m sama_display send --image D:\Pictures\example.png --device-id chs_65inch.dev1_rom1.91 --write-hardware
.\.venv\Scripts\python.exe -m sama_display dashboard-live --seconds 60 --interval 1.0 --device-id chs_65inch.dev1_rom1.91 --write-hardware
```

构建 WinUI 目录版：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build-winui.ps1
```

输出位于 `dist\SAMA-Open-Display-WinUI\`。WinUI 主程序、.NET/Windows App SDK 组件、`backend\SAMAOpenDisplay.Backend.exe`、插件与文档分别存放。旧版经典 Python GUI 可运行 `.\.venv\Scripts\python.exe -m sama_display.app`，对应的目录式构建脚本是 `scripts\build-windows.ps1`；它不是当前推荐的 Windows 前端。

## 兼容范围与项目资料

当前设备按 USB ID 自动发现：显示链路 `VID_1D6B&PID_A065`，辅助链路 `VID_1A86&PID_CA65`。COM 编号只是测试记录，不写死在程序里。已在设备标识 `chs_65inch.dev1_rom1.91` 上验证握手、横屏全帧和差分更新；其他型号与协议版本尚需验证。长期连续运行也仍需更充分的测试。

- [项目状态与后续工作](docs/PROJECT.md)
- [文档目录与历史记录](docs/README.md)
- [显示协议与验证依据](PROTOCOL.md)
- [插件格式与开发说明](PLUGIN_SPEC.md)

许可证：GPL-3.0-or-later，见 [LICENSE](LICENSE)。
