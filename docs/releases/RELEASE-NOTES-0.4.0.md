# SAMA Open Display 0.4.0

> 历史版本记录；功能和待办均以 0.4.0 发布时为准。现行状态见 [项目状态](../PROJECT.md)。

本版本将 Windows EXE 和桌面 GUI 作为主要使用入口。

- 新增横向三栏 GUI：内容选择、1568×720 预览、设备与发送控制；
- 支持仪表盘、图片/GIF/可选视频、文字画面和适配模式；
- 支持单帧发送和可停止的持续仪表盘；
- 每次硬件操作继续要求确认并核对 `chs_65inch.dev1_rom1.91`；
- 改用 PyInstaller `onedir`，主 EXE 不内嵌配置和全部 DLL；
- `config.toml` 位于 EXE 同目录，依赖统一位于 `runtime`；
- 默认轻量版排除 OpenCV；
- 修复便携 Python 虚拟环境下 Tcl/Tk 未被打包的问题；
- 40 项本地自动测试通过，EXE 已完成窗口启动与响应验证。

目录结构：

```text
SAMA-OpenDisplay.exe
config.toml
README.md
LICENSE
PROTOCOL.md
runtime\
```

Windows x64 发行包：`SAMA-OpenDisplay-0.4.0-Windows-x64.zip`

SHA-256：`1BA409C589AA91E164458ED269F27CC60F4A2785A95763ABADB6ECD0A9D5DBF6`
