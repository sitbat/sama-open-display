"""Classic Windows desktop UI for SAMA Open Display."""

from __future__ import annotations

from pathlib import Path
import ctypes
import sys
import threading
from time import monotonic, sleep
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from . import __version__
from .config import AppConfig, load_config
from .controller import DisplayController
from .data_provider import DataService
from .device import discover_devices
from .media import iter_media
from .render import dashboard_frame, fit_image, text_frame
from .plugin import PluginManager
from .theme import discover_themes

EXPECTED_DEVICE_ID = "chs_65inch.dev1_rom1.91"


def application_directory() -> Path:
    """Return the external-data directory for source and frozen builds."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def external_config_path() -> Path:
    return application_directory() / "config.toml"


def plugins_directory() -> Path:
    return application_directory() / "plugins"


def application_icon_path() -> Path:
    return application_directory() / "assets" / "app-icon.ico"


class DisplayApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.config_data = self._load_config()
        self.title(f"SAMA Open Display  {__version__}")
        self.geometry("1240x790")
        self.minsize(1060, 680)

        icon = application_icon_path()
        if icon.exists():
            try:
                self.iconbitmap(default=str(icon))
            except tk.TclError:
                pass

        self.plugin_manager = PluginManager(plugins_directory())
        self.plugins = self.plugin_manager.scan()
        self.data_service = DataService(self.plugins)
        self.themes = discover_themes(plugins_directory(), self.plugin_manager.enabled_ids())
        self.current_theme = self.themes[0]
        self.appearance = tk.StringVar(value="light")
        self.theme_name = tk.StringVar(value=self.current_theme.name)
        self.frame_image = dashboard_frame(theme=self.current_theme, data=self.data_service.snapshot())
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
        self.after(0, self._apply_windows_style)

    def _load_config(self) -> AppConfig:
        path = external_config_path()
        if not path.exists():
            return load_config()
        try:
            return load_config(path)
        except Exception:
            return load_config()

    def _configure_style(self) -> None:
        dark = self.appearance.get() == "dark"
        self.ui = {
            "root": "#0f1115" if dark else "#f5f7fa",
            "panel": "#191c22" if dark else "#ffffff",
            "surface": "#22262e" if dark else "#edf1f6",
            "text": "#f4f6f9" if dark else "#172033",
            "muted": "#a3adba" if dark else "#68778b",
            "border": "#343a45" if dark else "#d8dee8",
            "accent": "#4cc7e8" if dark else "#0067c0",
        }
        self.configure(background=self.ui["root"])
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("App.TFrame", background=self.ui["root"])
        style.configure("Panel.TFrame", background=self.ui["panel"])
        style.configure("Title.TLabel", background=self.ui["root"], foreground=self.ui["text"], font=("Segoe UI Variable Display Semibold", 20))
        style.configure("Sub.TLabel", background=self.ui["root"], foreground=self.ui["muted"], font=("Segoe UI Variable Text", 10))
        style.configure("PanelTitle.TLabel", background=self.ui["panel"], foreground=self.ui["text"], font=("Segoe UI Variable Text Semibold", 11))
        style.configure("PanelText.TLabel", background=self.ui["panel"], foreground=self.ui["muted"], font=("Segoe UI Variable Text", 9))
        style.configure("Status.TLabel", background=self.ui["surface"], foreground=self.ui["accent"], padding=(12, 9))
        style.configure("Accent.TButton", font=("Segoe UI Semibold", 10), padding=(11, 8))
        style.configure("Side.TButton", padding=(9, 7))
        style.configure("Panel.TRadiobutton", background=self.ui["panel"], foreground=self.ui["text"])
        style.configure("Panel.TCheckbutton", background=self.ui["panel"], foreground=self.ui["text"])
        style.configure("Treeview", rowheight=32, font=("Segoe UI Variable Text", 10))
        style.configure("Treeview.Heading", font=("Segoe UI Variable Text Semibold", 10))

    def _apply_windows_style(self) -> None:
        """Use DWM dark title bars and rounded corners without a UI runtime."""
        if sys.platform != "win32":
            return
        try:
            hwnd = self.winfo_id()
            dark = ctypes.c_int(1 if self.appearance.get() == "dark" else 0)
            corner = ctypes.c_int(2)  # DWMWCP_ROUND
            backdrop = ctypes.c_int(2)  # DWMSBT_MAINWINDOW (Mica where supported)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), 4)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(corner), 4)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 38, ctypes.byref(backdrop), 4)
        except (AttributeError, OSError):
            pass

    def _build_layout(self) -> None:
        root = ttk.Frame(self, style="App.TFrame", padding=18)
        root.pack(fill="both", expand=True)
        header = ttk.Frame(root, style="App.TFrame")
        header.pack(fill="x", pady=(0, 14))
        ttk.Label(header, text="SAMA Open Display", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="用于给 SAMA 屏幕设备显示自定义内容的开源工具", style="Sub.TLabel").pack(side="left", padx=(14, 0), pady=(8, 0))
        ttk.Label(header, text=f"v{__version__}", style="Sub.TLabel").pack(side="right", pady=(8, 0))
        self.appearance_button = ttk.Button(header, text="☀  亮色", command=self.toggle_appearance)
        self.appearance_button.pack(side="right", padx=(0, 12))

        self.pages = ttk.Notebook(root)
        self.pages.pack(fill="both", expand=True)
        display_page = ttk.Frame(self.pages, style="App.TFrame", padding=(0, 12, 0, 0))
        plugins_page = ttk.Frame(self.pages, style="App.TFrame", padding=14)
        self.pages.add(display_page, text="  显示与设备  ")
        self.pages.add(plugins_page, text="  插件中心  ")

        body = ttk.Frame(display_page, style="App.TFrame")
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
        self.preview = tk.Label(center, background=self.ui["surface"], bd=0, highlightthickness=1, highlightbackground=self.ui["border"])
        self.preview.grid(row=1, column=0, sticky="nsew")
        right = ttk.Frame(body, style="Panel.TFrame", padding=14, width=245)
        right.grid(row=0, column=2, sticky="nsew", padx=(12, 0))
        right.grid_propagate(False)
        self._device_panel(right)
        self._plugin_panel(plugins_page)
        ttk.Label(root, textvariable=self.status_text, style="Status.TLabel", anchor="w").pack(fill="x", pady=(12, 0))

    def _content_panel(self, panel) -> None:
        ttk.Label(panel, text="内容", style="PanelTitle.TLabel").pack(anchor="w", pady=(0, 10))
        ttk.Button(panel, text="系统仪表盘", style="Side.TButton", command=self.show_dashboard).pack(fill="x", pady=3)
        ttk.Button(panel, text="加载图片 / 媒体", style="Side.TButton", command=self.load_media).pack(fill="x", pady=3)
        ttk.Button(panel, text="文字画面", style="Side.TButton", command=self.show_text_dialog).pack(fill="x", pady=3)
        ttk.Separator(panel).pack(fill="x", pady=16)
        ttk.Label(panel, text="显示主题", style="PanelTitle.TLabel").pack(anchor="w", pady=(0, 7))
        self.theme_picker = ttk.Combobox(panel, state="readonly", textvariable=self.theme_name,
                                         values=[theme.name for theme in self.themes])
        self.theme_picker.pack(fill="x", pady=(0, 6))
        self.theme_picker.bind("<<ComboboxSelected>>", self.change_theme)
        ttk.Button(panel, text="打开插件中心", command=lambda: self.pages.select(1)).pack(fill="x")
        self.theme_description = ttk.Label(panel, text=self.current_theme.description,
                                           style="PanelText.TLabel", wraplength=175, justify="left")
        self.theme_description.pack(anchor="w", pady=(7, 0))
        ttk.Separator(panel).pack(fill="x", pady=16)
        ttk.Label(panel, text="画面适配", style="PanelTitle.TLabel").pack(anchor="w", pady=(0, 7))
        ttk.Radiobutton(panel, text="填满并裁切", variable=self.fit_mode, value="cover", style="Panel.TRadiobutton").pack(anchor="w", pady=2)
        ttk.Radiobutton(panel, text="完整包含", variable=self.fit_mode, value="contain", style="Panel.TRadiobutton").pack(anchor="w", pady=2)
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

    def _plugin_panel(self, panel) -> None:
        heading = ttk.Frame(panel, style="App.TFrame")
        heading.pack(fill="x", pady=(0, 12))
        ttk.Label(heading, text="插件中心", style="Title.TLabel").pack(side="left")
        ttk.Label(heading, text="批量安装、启停和管理主题及数据前置插件", style="Sub.TLabel").pack(side="left", padx=14, pady=(8, 0))
        ttk.Button(heading, text="批量安装…", style="Accent.TButton", command=self.install_plugins).pack(side="right")

        table_frame = ttk.Frame(panel, style="Panel.TFrame", padding=10)
        table_frame.pack(fill="both", expand=True)
        columns = ("name", "kind", "version", "status", "dependencies", "permissions")
        self.plugin_table = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended")
        labels = {
            "name": "插件", "kind": "类型", "version": "版本", "status": "状态",
            "dependencies": "前置插件", "permissions": "数据权限",
        }
        widths = {"name": 190, "kind": 110, "version": 75, "status": 150, "dependencies": 250, "permissions": 290}
        for column in columns:
            self.plugin_table.heading(column, text=labels[column])
            self.plugin_table.column(column, width=widths[column], minwidth=70, anchor="w")
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.plugin_table.yview)
        self.plugin_table.configure(yscrollcommand=scrollbar.set)
        self.plugin_table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        actions = ttk.Frame(panel, style="App.TFrame")
        actions.pack(fill="x", pady=(12, 0))
        ttk.Button(actions, text="启用所选", command=lambda: self.set_plugins_enabled(True)).pack(side="left")
        ttk.Button(actions, text="停用所选", command=lambda: self.set_plugins_enabled(False)).pack(side="left", padx=8)
        ttk.Button(actions, text="卸载所选", command=self.uninstall_plugins).pack(side="left")
        ttk.Button(actions, text="刷新", command=self.refresh_plugins).pack(side="right")
        self.plugin_summary = ttk.Label(actions, style="Sub.TLabel")
        self.plugin_summary.pack(side="right", padx=14)
        self.refresh_plugins()

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
        self.frame_image = dashboard_frame(theme=self.current_theme, data=self.data_service.snapshot())
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
                frame = dashboard_frame(theme=self.current_theme, data=self.data_service.snapshot())
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

    def change_theme(self, _event=None) -> None:
        selected = next((theme for theme in self.themes if theme.name == self.theme_name.get()), None)
        if selected is None:
            return
        self.current_theme = selected
        self.theme_description.configure(text=selected.description or f"作者：{selected.author}")
        self.stop_preview_animation()
        self.source_name.set(f"主题预览 · {selected.name}")
        self.frame_image = dashboard_frame(theme=selected, data=self.data_service.snapshot())
        self.refresh_preview()

    def _selected_plugin_ids(self) -> list[str]:
        return list(self.plugin_table.selection())

    def install_plugins(self) -> None:
        paths = filedialog.askopenfilenames(filetypes=[("SAMA Open Display 插件", "*.sodpkg")])
        if not paths:
            return
        try:
            installed = self.plugin_manager.install_many(list(paths))
        except Exception as exc:
            messagebox.showerror("插件安装失败", str(exc))
            return
        self.refresh_plugins()
        self.status_text.set(f"已安装 {len(installed)} 个插件")

    def refresh_plugins(self) -> None:
        self.plugins = self.plugin_manager.scan()
        self.data_service = DataService(self.plugins)
        if hasattr(self, "plugin_table"):
            for item in self.plugin_table.get_children():
                self.plugin_table.delete(item)
            kind_names = {"theme": "显示主题", "data-provider": "数据前置"}
            for item in self.plugins:
                manifest = item.manifest
                status = item.problem or ("已启用" if item.enabled else "已停用")
                self.plugin_table.insert("", "end", iid=manifest.plugin_id, values=(
                    manifest.name, kind_names.get(manifest.kind, manifest.kind), manifest.version,
                    status, ", ".join(manifest.dependencies) or "—",
                    ", ".join(manifest.permissions) or "—",
                ))
            enabled = sum(item.enabled and not item.problem for item in self.plugins)
            self.plugin_summary.configure(text=f"{len(self.plugins)} 个插件 · {enabled} 个可用")
        previous = self.current_theme.theme_id if hasattr(self, "current_theme") else ""
        self.themes = discover_themes(plugins_directory(), self.plugin_manager.enabled_ids())
        if hasattr(self, "theme_picker"):
            self.theme_picker.configure(values=[theme.name for theme in self.themes])
            selected = next((theme for theme in self.themes if theme.theme_id == previous), self.themes[0])
            self.current_theme = selected
            self.theme_name.set(selected.name)

    def set_plugins_enabled(self, enabled: bool) -> None:
        selected = self._selected_plugin_ids()
        if not selected:
            return
        try:
            self.plugin_manager.set_enabled(selected, enabled)
            self.refresh_plugins()
        except Exception as exc:
            messagebox.showerror("插件状态未更改", str(exc))

    def uninstall_plugins(self) -> None:
        selected = self._selected_plugin_ids()
        if not selected:
            return
        if not messagebox.askyesno("卸载插件", f"确定卸载所选 {len(selected)} 个插件？\n插件文件将从外部 plugins 目录删除。"):
            return
        try:
            self.plugin_manager.uninstall(selected)
            self.refresh_plugins()
        except Exception as exc:
            messagebox.showerror("插件卸载失败", str(exc))

    def toggle_appearance(self) -> None:
        self.appearance.set("dark" if self.appearance.get() == "light" else "light")
        self._configure_style()
        dark = self.appearance.get() == "dark"
        self.appearance_button.configure(text="☾  深色" if dark else "☀  亮色")
        self.preview.configure(background=self.ui["surface"], highlightbackground=self.ui["border"])
        self._apply_windows_style()

    def close_app(self) -> None:
        self.closing = True
        self.stop_preview_animation()
        self.hardware_stop.set()
        self.destroy()


def main() -> None:
    if sys.platform == "win32":
        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except (AttributeError, OSError):
            pass
    DisplayApp().mainloop()


if __name__ == "__main__":
    main()
