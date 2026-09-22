# SAMA Open Display

用于给 SAMA 屏幕设备显示自定义内容的开源工具。目前主要适配 SAMA 6.5 英寸 USB 小屏
（720×1568）。本项目是非官方社区工具，与 SAMA 品牌方不存在隶属、授权或背书关系。目前已完成：

- 自动识别 `VID_1D6B&PID_A065` 主显示串口及 `VID_1A86&PID_CA65` 辅助设备；
- 真机 HELLO 已验证，设备标识为 `chs_65inch.dev1_rom1.91`；
- 1568×720 物理横屏画布；编码时转换为设备要求的 720×1568 协议缓冲区；
- GUI 实时预览与命令行预览导出；
- 深色/亮色界面、可切换显示主题和 `.sodpkg` 插件导入；
- 开机自启、启动后隐藏、最小化/关闭到系统托盘和持久化外观设置；
- 独立插件中心，支持批量安装、启停、卸载、前置依赖和权限查看；
- 只读系统数据接口，主题可通过数据前置插件获取 CPU、内存、磁盘、网络等指标；
- Rev-C `EF 69` 协议命令、BGRA 帧和 249/250 字节分块编码；
- 不依赖 pyserial 的 Windows 原生串口传输层；
- 单元测试和协议研究记录。

项目文档入口见 [`docs/README.md`](docs/README.md)，包括项目目标、历次真机验证记录和历史发布说明。

## 安全状态

默认功能全部是只读检测或本地预览。程序目前不会自动连接、复位或向屏幕写入数据。
硬件发送要求显式确认：CLI 同时要求 `--write-hardware` 和完整设备 ID，GUI 每次弹出确认框。
程序握手后还会再次核对 `chs_65inch.dev1_rom1.91`，不匹配即拒绝传输。

## 安装与快速开始

需要 Windows 10/11 和 Python 3.10 或更高版本。全新环境：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install .
```

若要播放 MP4、AVI、MOV 或 MKV，安装视频扩展：

```powershell
python -m pip install ".[video]"
```

运行：

```powershell
python -m sama_display detect
python -m sama_display preview --output outputs\dashboard.png
python -m sama_display.app
python -m unittest discover -v
```

加载任意图片并按比例铺满画布：

```powershell
python -m sama_display preview --image D:\Pictures\example.png --output outputs\picture.png
```

检查视频解码和完整发送计划：

```powershell
python -m sama_display media-info D:\Videos\demo.mp4 --max-frames 20 --max-fps 10
python -m sama_display plan --brightness 70
```

最后一条命令只生成字节计划并打印长度与哈希，不连接设备。

发送任意图片或系统仪表盘（会写入硬件，必须先退出原厂 SAMA 软件）：

```powershell
python -m sama_display send --image D:\Pictures\example.png `
  --device-id chs_65inch.dev1_rom1.91 --write-hardware

python -m sama_display send `
  --device-id chs_65inch.dev1_rom1.91 --write-hardware
```

GUI 中的“发送到小屏”按钮也会在每次写入前要求确认。

播放视频或运行使用 `CC` 差分刷新的实时仪表盘：

```powershell
python -m sama_display play D:\Videos\demo.mp4 --max-fps 0.8 `
  --device-id chs_65inch.dev1_rom1.91 --write-hardware

python -m sama_display dashboard-live --seconds 60 --interval 1.0 `
  --device-id chs_65inch.dev1_rom1.91 --write-hardware
```

当前使用已经真机验证的全帧路径，实测一帧约 1.1 秒，因此命令把最大帧率限制在 1 FPS。
首帧使用完整 BGRA，后续帧只发送变化像素；差异越小，实际刷新越快。

使用配置文件：

```powershell
python -m sama_display preview --config examples\config.toml
```

## Windows 独立程序

构建新的 WinUI 3 目录式版本：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build-winui.ps1
```

输出目录为 `dist\SAMA-Open-Display-WinUI\`。`SAMAOpenDisplay.exe` 是 WinUI 3 主入口；.NET 和 Windows App SDK
组件保持为外部 DLL，Python 协议核心位于 `backend`，插件位于 `plugins`。当前 WinUI 迁移阶段开放设备
检测、仪表盘预览、插件批量管理、依赖和权限，以及带双重安全门的一次性画面发送。

WinUI 现在包含一次性“发送当前画面”入口。按钮仅在检测到目标 USB 小屏且已有有效预览时启用；每次发送都
会显示端口、USB 标识、亮度和预期协议身份，并要求用户明确确认。后端仍会执行 `--write-hardware` 门禁、
HELLO 握手以及 `chs_65inch.dev1_rom1.91` 精确身份比对。持续发送画面沿用相同安全门，并在每次启动前再次确认。

持续发送画面使用当前所选主题和只读数据前置，默认帧率为 1 FPS；如果一帧传输耗时更长，不会排队积压。
“停止持续发送画面”通过停止信号让传输管线在当前数据块边界退出并关闭串口。
切换到插件、关于或设置页面不会中断持续发送；任务会保留在缓存的首页会话中，只有用户主动停止或真正退出程序时才会结束。

首页“内容”区域中的“使用主题”会列出内置主题以及用户安装并启用的主题插件。发行包只预装
“系统指标接口”数据前置；不再预装系统仪表盘或 SAMA 网格主题插件。切换主题后会立即重新生成安全预览。

设置页可启用当前用户的 Windows 开机自启，并选择自启后直接隐藏到后台。程序提供原生系统托盘图标；左键
单击可恢复主窗口，右键菜单可打开程序或彻底退出。最小化按钮和关闭按钮是否隐藏到托盘可分别设置，设置保存
在 `%LOCALAPPDATA%\SAMA Open Display\settings.json`，不会写入程序目录。

构建不带视频解码器的轻量版本：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build-windows.ps1
```

构建包含 OpenCV 视频支持的版本：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build-windows.ps1 -WithVideo
```

输出目录为 `dist\SAMA-Open-Display\`：

```text
SAMAOpenDisplay.exe    主程序入口
config.toml            可编辑的外部配置
assets\                应用图标
plugins\               外部主题与数据前置插件
README.md              使用说明
LICENSE
PROTOCOL.md
PLUGIN_SPEC.md          插件规范
runtime\               Python 运行库、Pillow、psutil 和 DLL
```

构建使用 PyInstaller `onedir` 模式，不会把配置、DLL 和全部运行库硬塞进主 EXE。默认轻量构建明确排除
OpenCV；只有使用 `-WithVideo` 时才把视频解码依赖放进 `runtime`。构建脚本会创建隔离环境、安装依赖并先执行测试。

## 主题与插件

SAMA Open Display 只使用统一的 `.sodpkg` 插件文件。“插件中心”支持批量安装、启用、停用和卸载；插件保存在
主程序旁边的 `plugins` 目录，不会写入 EXE。v1 支持纯数据主题和权限受控的系统数据前置插件，不执行第三方
脚本、DLL 或 Python 代码。完整清单、依赖、数据权限、配色和背景图片约束见 `PLUGIN_SPEC.md`。

当前 GUI 使用 WinUI 3 原生控件，并接入高 DPI、深浅色外观、系统托盘和 Windows 11 窗口样式。协议、渲染和
插件核心与界面保持分层。

项目使用 Python 3.10+、Pillow 和 psutil。Windows 传输层仅使用 Python 标准库 `ctypes`，视频支持使用可选 OpenCV。

## 仓库结构

```text
frontend/SAMAOpenDisplay.WinUI/   WinUI 3 主界面
sama_display/                     协议、渲染、插件和硬件后端
tests/                            自动测试
examples/                         配置、主题和数据插件示例
plugins/                          随目录版发布的内置数据插件
scripts/                          检查与 Windows 构建脚本
docs/                             项目目标、真机验证和历史发布记录
outputs/                          本地生成内容（不提交）
dist/                             本地构建结果（不提交）
```

## 动态内容策略

- 视频按 `max_fps` 节流，不会因为源视频是 60 FPS 就无限堆积；
- GUI 的系统仪表盘每秒重新采样；
- 连续帧使用已在 ROM 1.91 真机验证的原厂 `CC` 压缩差分流；
- CLI、GUI 和低帧率播放入口均有显式确认与设备身份校验；未经确认不会打开端口。

## 已识别硬件

| 角色 | USB ID | 当前端口 | 说明 |
|---|---|---:|---|
| 显示数据 | `VID_1D6B&PID_A065` | COM5 | Gadget Serial v2.4 / usbser |
| 辅助控制 | `VID_1A86&PID_CA65` | COM4 | UsbMonitor / CH552 类设备 |

端口号会变化，应用按 VID/PID 从注册表重新发现，不写死 COM5。

## 路线图

1. HELLO、全屏参数、横屏转换和颜色通道均已真机验证。
2. 单帧任意图片/仪表盘已接入正式 CLI 和 GUI。
3. 已从原厂程序集还原 `CC` 差分记录、扫描映射和基准帧序号，并完成可恢复的真机验证。
4. 执行 Windows 独立程序构建及长时间稳定性测试，补充硬件兼容矩阵。

## 当前限制

- 6.5 英寸全帧参数、BGRA、横屏转换均已真机验证；
- `CC` 压缩差分流已离线核对原厂编码器，并在 ROM 1.91 真机验证；
- Windows 目录式 EXE 已构建并完成启动验证；配置和运行库保持为外部文件；
- 原厂软件占用 COM5 时，替代应用不能同时打开该端口。

协议细节和证据等级见 `PROTOCOL.md`。
