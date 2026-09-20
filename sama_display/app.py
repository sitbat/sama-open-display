"""Small Tkinter preview application. It never writes to the USB display."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
from PIL import Image, ImageTk

from .device import discover_devices
from .controller import DisplayController
from .media import iter_media
from .render import dashboard_frame, fit_image, text_frame


class PreviewApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SAMA Open Display — 安全预览")
        self.geometry("520x860")
        self.minsize(440, 720)
        self.frame_image = dashboard_frame()
        self.preview_photo = None
        self.animation = None
        self.animation_job = None

        bar = ttk.Frame(self, padding=10)
        bar.pack(fill="x")
        ttk.Button(bar, text="实时仪表盘", command=self.show_dashboard).pack(side="left", padx=3)
        ttk.Button(bar, text="加载媒体", command=self.load_image).pack(side="left", padx=3)
        ttk.Button(bar, text="文字", command=self.show_text).pack(side="left", padx=3)
        ttk.Button(bar, text="刷新设备", command=self.refresh_devices).pack(side="left", padx=3)
        self.send_button = ttk.Button(bar, text="发送到小屏", command=self.confirm_send)
        self.send_button.pack(side="left", padx=3)
        self.status = ttk.Label(self, padding=(12, 2), foreground="#176b55")
        self.status.pack(fill="x")
        self.canvas = ttk.Label(self, anchor="center")
        self.canvas.pack(fill="both", expand=True, padx=12, pady=8)
        self.bind("<Configure>", lambda _event: self.after_idle(self.refresh_preview))
        self.protocol("WM_DELETE_WINDOW", self.close_app)
        self.refresh_devices()
        self.refresh_preview()

    def refresh_devices(self):
        devices = discover_devices()
        display = next((d for d in devices if d.role == "display"), None)
        if display:
            self.status.configure(text=f"只读检测：{display.port or '端口未知'}  VID_1D6B&PID_A065  •  未连接/未发送")
        else:
            self.status.configure(text="未检测到目标小屏  •  未连接/未发送")

    def refresh_preview(self):
        width = max(240, self.canvas.winfo_width() - 16)
        height = max(480, self.canvas.winfo_height() - 16)
        preview = self.frame_image.copy()
        preview.thumbnail((width, height), Image.Resampling.LANCZOS)
        self.preview_photo = ImageTk.PhotoImage(preview)
        self.canvas.configure(image=self.preview_photo)

    def show_dashboard(self):
        self.stop_animation()
        self.dashboard_tick()

    def dashboard_tick(self):
        self.animation_job = None
        self.frame_image = dashboard_frame()
        self.refresh_preview()
        self.animation_job = self.after(1000, self.dashboard_tick)

    def load_image(self):
        path = filedialog.askopenfilename(filetypes=[
            ("图片/视频", "*.png *.jpg *.jpeg *.bmp *.webp *.gif *.mp4 *.avi *.mov *.mkv"),
            ("全部文件", "*.*"),
        ])
        if path:
            suffix = path.lower().rsplit(".", 1)[-1]
            if suffix in {"gif", "mp4", "avi", "mov", "mkv"}:
                self.stop_animation()
                self.animation = iter_media(path, max_fps=10)
                self.next_media_frame()
            else:
                self.stop_animation()
                with Image.open(path) as source:
                    self.frame_image = fit_image(source)
                self.refresh_preview()

    def next_media_frame(self):
        if self.animation is None:
            return
        try:
            frame = next(self.animation)
        except StopIteration:
            self.stop_animation()
            return
        except Exception as exc:
            self.stop_animation()
            self.status.configure(text=f"媒体解码失败：{exc}")
            return
        self.frame_image = frame.image
        self.refresh_preview()
        self.animation_job = self.after(frame.duration_ms, self.next_media_frame)

    def stop_animation(self):
        if self.animation_job is not None:
            self.after_cancel(self.animation_job)
            self.animation_job = None
        if self.animation is not None:
            close = getattr(self.animation, "close", None)
            if close:
                close()
            self.animation = None

    def show_text(self):
        self.stop_animation()
        dialog = tk.Toplevel(self)
        dialog.title("显示文字")
        entry = tk.Text(dialog, width=42, height=8, font=("Microsoft YaHei UI", 12))
        entry.pack(padx=12, pady=12)
        entry.insert("1.0", "你好，SAMA Open Display")

        def apply():
            self.frame_image = text_frame(entry.get("1.0", "end").strip())
            dialog.destroy()
            self.refresh_preview()

        ttk.Button(dialog, text="生成预览", command=apply).pack(pady=(0, 12))

    def close_app(self):
        self.stop_animation()
        self.destroy()

    def confirm_send(self):
        confirmed = messagebox.askyesno(
            "确认硬件写入",
            "将停止当前预览动画并把这一帧写入已验证的 SAMA 小屏。\n\n"
            "请确保原厂 SAMA 软件已退出。此操作不修改固件。是否继续？",
            icon="warning",
        )
        if not confirmed:
            return
        self.stop_animation()
        frame = self.frame_image.copy()
        self.send_button.configure(state="disabled")
        self.status.configure(text="正在连接并验证设备……")
        threading.Thread(target=self._send_worker, args=(frame,), daemon=True).start()

    def _send_worker(self, frame: Image.Image):
        controller = DisplayController()
        last_percent = -1

        def progress(sent: int, total: int):
            nonlocal last_percent
            percent = sent * 100 // total
            if percent == last_percent:
                return
            last_percent = percent
            self.after(0, lambda: self.status.configure(text=f"正在发送：{percent}%"))

        try:
            controller.connect(allow_hardware=True)
            controller.hello()
            if controller.identity is None or controller.identity.raw != "chs_65inch.dev1_rom1.91":
                actual = controller.identity.raw if controller.identity else "unknown"
                raise RuntimeError(f"设备标识不匹配：{actual}")
            controller.display(frame, brightness=60, panel_rotation=90, progress=progress)
        except Exception as exc:
            message = str(exc)
            self.after(0, lambda: messagebox.showerror("发送失败", message))
            self.after(0, lambda: self.status.configure(text="发送失败；端口已关闭"))
        else:
            self.after(0, lambda: self.status.configure(text="发送完成；COM 端口已关闭"))
        finally:
            controller.close()
            self.after(0, lambda: self.send_button.configure(state="normal"))


def main() -> None:
    PreviewApp().mainloop()


if __name__ == "__main__":
    main()
