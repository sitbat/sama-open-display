# SAMA Open Display

面向 SAMA 6.5 英寸 USB 小屏（720×1568）的开源替代控制器。目前已完成：

- 自动识别 `VID_1D6B&PID_A065` 主显示串口及 `VID_1A86&PID_CA65` 辅助设备；
- 真机 HELLO 已验证，设备标识为 `chs_65inch.dev1_rom1.91`；
- 1568×720 物理横屏画布；编码时转换为设备要求的 720×1568 协议缓冲区；
- GUI 实时预览与命令行预览导出；
- Rev-C `EF 69` 协议命令、BGRA 帧和 249/250 字节分块编码；
- 不依赖 pyserial 的 Windows 原生串口传输层；
- 单元测试和协议研究记录。

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

生成动态仪表盘 GIF、检查 GIF/视频解码、检查完整发送计划：

```powershell
python -m sama_display animate-dashboard --seconds 5 --fps 2
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

低帧率播放 GIF/视频或运行实时仪表盘：

```powershell
python -m sama_display play D:\Videos\demo.mp4 --max-fps 0.8 `
  --device-id chs_65inch.dev1_rom1.91 --write-hardware

python -m sama_display dashboard-live --seconds 60 --interval 2 `
  --device-id chs_65inch.dev1_rom1.91 --write-hardware
```

当前使用已经真机验证的全帧路径，实测一帧约 1.1 秒，因此命令把最大帧率限制在 1 FPS。
局部更新验证完成后会提高动画帧率。

使用配置文件：

```powershell
python -m sama_display preview --config examples\config.toml
```

## Windows 独立程序

构建不带视频解码器的轻量版本：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build-windows.ps1
```

构建包含 OpenCV 视频支持的版本：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build-windows.ps1 -WithVideo
```

输出为 `dist\SAMA-OpenDisplay.exe`。构建脚本会创建隔离虚拟环境、安装依赖并先执行测试。

项目使用 Python 3.10+、Pillow 和 psutil。Windows 传输层仅使用 Python 标准库 `ctypes`，视频支持使用可选 OpenCV。

## 动态内容策略

- GIF 保留每一帧自己的时长；
- 视频按 `max_fps` 节流，不会因为源视频是 60 FPS 就无限堆积；
- GUI 的系统仪表盘每秒重新采样；
- 连续帧可以生成原厂 ROM >= 1.89 风格的压缩差分流，但真机入口仍保持禁用；
- CLI、GUI 和低帧率播放入口均有显式确认与设备身份校验；未经确认不会打开端口。

## 已识别硬件

| 角色 | USB ID | 当前端口 | 说明 |
|---|---|---:|---|
| 显示数据 | `VID_1D6B&PID_A065` | COM5 | Gadget Serial v2.4 / usbser |
| 辅助控制 | `VID_1A86&PID_CA65` | COM4 | UsbMonitor / CH552 类设备 |

端口号会变化，应用按 VID/PID 从注册表重新发现，不写死 COM5。

## 固件结论

当前没有必要重刷固件。原厂程序已经通过 USB 串口发送普通画面数据，说明“显示任意内容”可完全在电脑端完成。
刷固件只适合后续追求脱机播放、设备端解码或摆脱现有协议限制的研究，而且必须先取得固件备份、芯片型号、
引脚和可恢复刷写路径；否则收益小、变砖风险高。

## 路线图

1. HELLO、全屏参数、横屏转换和颜色通道均已真机验证。
2. 单帧任意图片/仪表盘已接入正式 CLI 和 GUI。
3. 已从原厂程序集还原 `CC` 差分记录；下一步仅在单独授权后做可恢复的真机验证。
4. 执行 Windows 独立程序构建及长时间稳定性测试，补充硬件兼容矩阵。

## 当前限制

- 6.5 英寸全帧参数、BGRA、横屏转换均已真机验证；
- `CC` 压缩差分流已离线核对原厂编码器，但尚未在 ROM 1.91 真机验证；
- 独立 EXE 构建脚本已提供，但当前机器没有安装 PyInstaller，因此尚未生成并验证 EXE；
- 原厂软件占用 COM5 时，替代应用不能同时打开该端口。

协议细节和证据等级见 `PROTOCOL.md`。
