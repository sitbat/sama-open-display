"""Windows desktop UI for SAMA Open Display."""

from __future__ import annotations

from pathlib import Path
import sys
import threading
from time import monotonic, sleep
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from . import __version__
from .config import AppConfig, load_config
from .controller import DisplayController
from .device import discover_devices
from .media import iter_media
from .render import dashboard_frame, fit_image, text_frame

EXPECTED_DEVICE_ID = "chs_65inch.dev1_rom1.91"


def application_directory() -> Path:
    """Return the external-data directory for source and frozen builds."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def external_config_path() -> Path:
    return application_directory() / "config.toml"


class DisplayApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.config_data = self._load_config()
        self.title(f"SAMA Open Display  {__version__}")
        self.geometry("1180x760")
        self.minsize(980, 650)
        self.configure(background="#0b1220")

        self.frame_image = dashboard_frame()
        self.preview_photo = None
        self.animation = None
        self.animation_job = None
        self.hardware_thread = None
        self.hardware_stop = threading.Event()
        self.hardware_brightness = self.config_data.display.brightness
        self.closing = False
        self.brightness = tk.IntVar(value=self.config_data.display.brightness)
        self.fit_mode = tk.StringVar(value=self.config_data.content.fit)
        self.source_name = tk.StringVar(value="系统仪表盘")
        self.device_text = tk.StringVar(value="正在检测设备……")
        self.status_text = tk.StringVar(value="安全预览模式：尚未连接小屏")

        self._configure_style()
        self._build_layout()
        self.protocol("WM_DELETE_WINDOW", self.close_app)
        self.bind("<Configure>", lambda _event: self.after_idle(self.refresh_preview))
        self.after(50, self.refresh_devices)
        self.after(80, self.refresh_preview)

    def _load_config(self) -> AppConfig:
        path = external_config_path()
        if not path.exists():
            return load_config()
        try:
            return load_config(path)
        except Exception:
            return load_config()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("App.TFrame", background="#0b1220")
        style.configure("Panel.TFrame", background="#111c2e")
        style.configure("Title.TLabel", background="#0b1220", foreground="#f3f7ff", font=("Segoe UI Semibold", 19))
        style.configure("Sub.TLabel", background="#0b1220", foreground="#8ea2bd", font=("Segoe UI", 10))
        style.configure("PanelTitle.TLabel", background="#111c2e", foreground="#dce8f8", font=("Segoe UI Semibold", 11))
        style.configure("PanelText.TLabel", background="#111c2e", foreground="#9fb1c8", font=("Segoe UI", 9))
        style.configure("Status.TLabel", background="#0f1a2c", foreground="#75e6c3", padding=(12, 9))
        style.configure("Accent.TButton", font=("Segoe UI Semibold", 10), padding=(11, 8))
        style.configure("Side.TButton", padding=(9, 7))

    def _build_layout(self) -> None:
        root = ttk.Frame(self, style="App.TFrame", padding=18)
        root.pack(fill="both", expand=True)
        header = ttk.Frame(root, style="App.TFrame")
        header.pack(fill="x", pady=(0, 14))
        ttk.Label(header, text="SAMA Open Display", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="6.5 英寸 USB 小屏控制器", style="Sub.TLabel").pack(side="left", padx=(14, 0), pady=(8, 0))
        ttk.Label(header, text=f"v{__version__}", style="Sub.TLabel").pack(side="right", pady=(8, 0))

        body = ttk.Frame(root, style="App.TFrame")
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        left = ttk.Frame(body, style="Panel.TFrame", padding=14, width=205)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.grid_propagate(False)
        self._content_panel(left)
        center = ttk.Frame(body, style="Panel.TFrame", padding=12)
        center.grid(row=0, column=1, sticky="nsew")
        center.columnconfigure(0, weight=1)
        center.rowconfigure(1, weight=1)
        top = ttk.Frame(center, style="Panel.TFrame")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(top, textvariable=self.source_name, style="PanelTitle.TLabel").pack(side="left")
        ttk.Label(top, text="1568 × 720", style="PanelText.TLabel").pack(side="right")
        self.preview = tk.Label(center, background="#050a12", bd=0, highlightthickness=1, highlightbackground="#263955")
        self.preview.grid(row=1, column=0, sticky="nsew")
        right = ttk.Frame(body, style="Panel.TFrame", padding=14, width=245)
        right.grid(row=0, column=2, sticky="nsew", padx=(12, 0))
        right.grid_propagate(False)
        self._device_panel(right)
        ttk.Label(root, textvariable=self.status_text, style="Status.TLabel", anchor="w").pack(fill="x", pady=(12, 0))

    def _content_panel(self, panel) -> None:
        ttk.Label(panel, text="内容", style="PanelTitle.TLabel").pack(anchor="w", pady=(0, 10))
        ttk.Button(panel, text="系统仪表盘", style="Side.TButton", command=self.show_dashboard).pack(fill="x", pady=3)
        ttk.Button(panel, text="加载图片 / 媒体", style="Side.TButton", command=self.load_media).pack(fill="x", pady=3)
        ttk.Button(panel, text="文字画面", style="Side.TButton", command=self.show_text_dialog).pack(fill="x", pady=3)
        ttk.Separator(panel).pack(fill="x", pady=16)
        ttk.Label(panel, text="画面适配", style="PanelTitle.TLabel").pack(anchor="w", pady=(0, 7))
        ttk.Radiobutton(panel, text="填满并裁切", variable=self.fit_mode, value="cover").pack(anchor="w", pady=2)
        ttk.Radiobutton(panel, text="完整包含", variable=self.fit_mode, value="contain").pack(anchor="w", pady=2)
        ttk.Label(panel, text="亮度", style="PanelTitle.TLabel").pack(anchor="w", pady=(18, 5))
        row = ttk.Frame(panel, style="Panel.TFrame")
        row.pack(fill="x")
        ttk.Scale(row, from_=10, to=100, variable=self.brightness, orient="horizontal").pack(side="left", fill="x", expand=True)
        ttk.Label(row, textvariable=self.brightness, width=3, style="PanelText.TLabel").pack(side="right", padx=(6, 0))
        ttk.Separator(panel).pack(fill="x", pady=18)
        ttk.Label(panel, text="预览不会访问硬件。发送前会核对设备身份并要求确认。", style="PanelText.TLabel", wraplength=175, justify="left").pack(anchor="w")

    def _device_panel(self, panel) -> None:
        ttk.Label(panel, text="设备", style="PanelTitle.TLabel").pack(anchor="w")
        ttk.Label(panel, textvariable=self.device_text, style="PanelText.TLabel", wraplength=210, justify="left").pack(anchor="w", pady=(7, 9))
        ttk.Button(panel, text="重新检测", command=self.refresh_devices).pack(fill="x", pady=(0, 15))
        ttk.Separator(panel).pack(fill="x", pady=(0, 15))
        ttk.Label(panel, text="硬件操作", style="PanelTitle.TLabel").pack(anchor="w", pady=(0, 9))
        self.send_button = ttk.Button(panel, text="发送当前画面", style="Accent.TButton", command=self.confirm_send)
        self.send_button.pack(fill="x", pady=4)
        self.live_button = ttk.Button(panel, text="开始持续仪表盘", command=self.toggle_live_dashboard)
        self.live_button.pack(fill="x", pady=4)
        ttk.Label(panel, text="持续模式使用已验证的全帧协议，每秒最多发送一帧。", style="PanelText.TLabel", wraplength=210, justify="left").pack(anchor="w", pady=(10, 0))
        ttk.Separator(panel).pack(fill="x", pady=18)
        ttk.Label(panel, text="外部配置", style="PanelTitle.TLabel").pack(anchor="w")
        ttk.Label(panel, text=str(external_config_path()), style="PanelText.TLabel", wraplength=210, justify="left").pack(anchor="w", pady=(6, 0))

    def refresh_devices(self) -> None:
        devices = discover_devices()
        display = next((d for d in devices if d.role == "display"), None)
        helper = next((d for d in devices if d.role == "helper"), None)
        if display:
            extra = f"\n辅助端口：{helper.port}" if helper and helper.port else ""
            self.device_text.set(f"已发现目标小屏\n显示端口：{display.port or '未知'}{extra}\nVID_1D6B · PID_A065")
        else:
            self.device_text.set("未检测到目标小屏。请检查 USB 连接。")

    def refresh_preview(self) -> None:
        if self.closing:
            return
        width, height = self.preview.winfo_width() - 24, self.preview.winfo_height() - 24
        if width < 50 or height < 50:
            return
        image = self.frame_image.copy()
        image.thumbnail((width, height), Image.Resampling.LANCZOS)
        self.preview_photo = ImageTk.PhotoImage(image)
        self.preview.configure(image=self.preview_photo)

    def show_dashboard(self) -> None:
        self.stop_preview_animation()
        self.source_name.set("系统仪表盘 · 实时预览")
        self._dashboard_tick()

    def _dashboard_tick(self) -> None:
        self.animation_job = None
        self.frame_image = dashboard_frame()
        self.refresh_preview()
        self.animation_job = self.after(1000, self._dashboard_tick)

    def load_media(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("图片和媒体", "*.png *.jpg *.jpeg *.bmp *.webp *.gif *.mp4 *.avi *.mov *.mkv"), ("全部文件", "*.*")])
        if not path:
            return
        self.stop_preview_animation()
        self.source_name.set(Path(path).name)
        try:
            if Path(path).suffix.lower() in {".gif", ".mp4", ".avi", ".mov", ".mkv"}:
                self.animation = iter_media(path, fit=self.fit_mode.get(), max_fps=10)
                self._next_media_frame()
            else:
                with Image.open(path) as source:
                    self.frame_image = fit_image(source, fit=self.fit_mode.get())
                self.refresh_preview()
        except Exception as exc:
            messagebox.showerror("媒体加载失败", str(exc))

    def _next_media_frame(self) -> None:
        try:
            frame = next(self.animation)
        except StopIteration:
            self.stop_preview_animation()
            return
        except Exception as exc:
            self.stop_preview_animation()
            self.status_text.set(f"媒体解码失败：{exc}")
            return
        self.frame_image = frame.image
        self.refresh_preview()
        self.animation_job = self.after(max(16, frame.duration_ms), self._next_media_frame)

    def stop_preview_animation(self) -> None:
        if self.animation_job is not None:
            self.after_cancel(self.animation_job)
            self.animation_job = None
        if self.animation is not None:
            close = getattr(self.animation, "close", None)
            if close:
                close()
            self.animation = None

    def show_text_dialog(self) -> None:
        self.stop_preview_animation()
        dialog = tk.Toplevel(self)
        dialog.title("生成文字画面")
        dialog.geometry("520x300")
        dialog.transient(self)
        entry = tk.Text(dialog, font=("Microsoft YaHei UI", 14), wrap="word")
        entry.pack(fill="both", expand=True, padx=14, pady=14)
        entry.insert("1.0", "你好，SAMA Open Display")
        def apply():
            value = entry.get("1.0", "end").strip()
            if value:
                self.frame_image = text_frame(value)
                self.source_name.set("文字画面")
                dialog.destroy()
                self.refresh_preview()
        ttk.Button(dialog, text="生成预览", style="Accent.TButton", command=apply).pack(pady=(0, 14))
        entry.focus_set()

    def _confirm_hardware(self, continuous=False) -> bool:
        detail = "程序将保持串口连接，直到点击停止或关闭窗口。\n\n" if continuous else ""
        return messagebox.askyesno("确认硬件写入", f"将向已验证的 SAMA 小屏发送画面。\n\n{detail}请确保原厂软件已退出。本操作不会修改固件。是否继续？", icon="warning")

    def _controller(self) -> DisplayController:
        controller = DisplayController()
        controller.connect(allow_hardware=True)
        controller.hello()
        if controller.identity is None or controller.identity.raw != EXPECTED_DEVICE_ID:
            actual = controller.identity.raw if controller.identity else "unknown"
            controller.close()
            raise RuntimeError(f"设备标识不匹配：{actual}")
        return controller

    def confirm_send(self) -> None:
        if self.hardware_thread and self.hardware_thread.is_alive():
            messagebox.showinfo("设备正在使用", "请先停止持续仪表盘。")
            return
        if not self._confirm_hardware():
            return
        self.stop_preview_animation()
        self.hardware_brightness = int(self.brightness.get())
        self._controls(False)
        self.status_text.set("正在连接并验证设备……")
        self.hardware_thread = threading.Thread(target=self._send_worker, args=(self.frame_image.copy(),), daemon=True)
        self.hardware_thread.start()

    def _send_worker(self, frame) -> None:
        controller = None
        try:
            controller = self._controller()
            controller.display(frame, brightness=self.hardware_brightness, panel_rotation=90)
        except Exception as exc:
            self.after(0, self._failed, str(exc))
        else:
            self.after(0, self.status_text.set, "发送完成；COM 端口已关闭")
        finally:
            if controller:
                controller.close()
            self.after(0, self._controls, True)

    def toggle_live_dashboard(self) -> None:
        if self.hardware_thread and self.hardware_thread.is_alive():
            self.hardware_stop.set()
            self.live_button.configure(text="正在停止……", state="disabled")
            return
        if not self._confirm_hardware(True):
            return
        self.stop_preview_animation()
        self.hardware_brightness = int(self.brightness.get())
        self.hardware_stop.clear()
        self._controls(False, live=True)
        self.live_button.configure(text="停止持续仪表盘", state="normal")
        self.hardware_thread = threading.Thread(target=self._live_worker, daemon=True)
        self.hardware_thread.start()

    def _live_worker(self) -> None:
        controller, frames, started = None, 0, monotonic()
        try:
            controller = self._controller()
            while not self.hardware_stop.is_set():
                frame_started = monotonic()
                frame = dashboard_frame()
                controller.display(frame, brightness=self.hardware_brightness, panel_rotation=90, cancelled=self.hardware_stop.is_set)
                frames += 1
                self.after(0, self._live_frame, frame, frames, monotonic() - started)
                remaining = 1.0 - (monotonic() - frame_started)
                while remaining > 0 and not self.hardware_stop.is_set():
                    pause = min(0.05, remaining)
                    sleep(pause)
                    remaining -= pause
        except InterruptedError:
            pass
        except Exception as exc:
            self.after(0, self._failed, str(exc))
        finally:
            if controller:
                controller.close()
            self.after(0, self._live_finished, frames, monotonic() - started)

    def _live_frame(self, frame, frames, elapsed) -> None:
        self.frame_image = frame
        self.source_name.set("系统仪表盘 · 正在发送")
        self.refresh_preview()
        self.status_text.set(f"持续显示中：第 {frames} 帧 · 平均 {frames / elapsed:.2f} FPS")

    def _live_finished(self, frames, elapsed) -> None:
        self.hardware_stop.clear()
        self._controls(True)
        self.live_button.configure(text="开始持续仪表盘")
        if not self.status_text.get().startswith("硬件操作失败"):
            self.status_text.set(f"持续显示已停止：{frames} 帧 / {elapsed:.1f} 秒；COM 端口已关闭")

    def _failed(self, message) -> None:
        self.status_text.set(f"硬件操作失败：{message}")
        if not self.closing:
            messagebox.showerror("硬件操作失败", message)

    def _controls(self, enabled, live=False) -> None:
        state = "normal" if enabled else "disabled"
        self.send_button.configure(state=state)
        if not live:
            self.live_button.configure(state=state)

    def close_app(self) -> None:
        self.closing = True
        self.stop_preview_animation()
        self.hardware_stop.set()
        self.destroy()


def main() -> None:
    DisplayApp().mainloop()


if __name__ == "__main__":
    main()
