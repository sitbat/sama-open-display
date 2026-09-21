using System.Runtime.InteropServices;

namespace SAMAOpenDisplay_WinUI.Services;

public sealed class TrayIconService : IDisposable
{
    private const uint CallbackMessage = 0x8001;
    private const uint IconId = 1;
    private const int GwlWndProc = -4;
    private const uint NifMessage = 0x00000001;
    private const uint NifIcon = 0x00000002;
    private const uint NifTip = 0x00000004;
    private const uint NimAdd = 0x00000000;
    private const uint NimDelete = 0x00000002;
    private const uint WmLButtonUp = 0x0202;
    private const uint WmLButtonDoubleClick = 0x0203;
    private const uint WmRButtonUp = 0x0205;
    private const uint WmSysCommand = 0x0112;
    private const nuint ScMinimize = 0xF020;
    private const uint MfString = 0x00000000;
    private const uint MfSeparator = 0x00000800;
    private const uint TpmReturnCommand = 0x0100;
    private const uint TpmNonotify = 0x0080;
    private const uint ImageIcon = 1;
    private const uint LrLoadFromFile = 0x0010;
    private const uint LrDefaultSize = 0x0040;
    private const uint MenuShow = 1001;
    private const uint MenuExit = 1002;

    private readonly nint _windowHandle;
    private readonly Action _showWindow;
    private readonly Action _hideWindow;
    private readonly Action _exitApplication;
    private readonly Func<bool> _minimizeToTray;
    private readonly WindowProc _windowProc;
    private readonly nint _previousWindowProc;
    private readonly nint _iconHandle;
    private bool _disposed;

    public TrayIconService(
        nint windowHandle,
        Action showWindow,
        Action hideWindow,
        Action exitApplication,
        Func<bool> minimizeToTray)
    {
        _windowHandle = windowHandle;
        _showWindow = showWindow;
        _hideWindow = hideWindow;
        _exitApplication = exitApplication;
        _minimizeToTray = minimizeToTray;
        _windowProc = HandleWindowMessage;
        _previousWindowProc = SetWindowProcedure(windowHandle, Marshal.GetFunctionPointerForDelegate(_windowProc));

        string iconPath = Path.Combine(AppContext.BaseDirectory, "Assets", "AppIcon.ico");
        _iconHandle = LoadImage(0, iconPath, ImageIcon, 0, 0, LrLoadFromFile | LrDefaultSize);

        NotifyIconData data = CreateNotifyIconData();
        if (!Shell_NotifyIcon(NimAdd, ref data))
        {
            RestoreWindowProcedure();
            if (_iconHandle != 0)
                DestroyIcon(_iconHandle);
            throw new InvalidOperationException("无法创建系统托盘图标。");
        }
    }

    public void Dispose()
    {
        if (_disposed)
            return;
        _disposed = true;

        NotifyIconData data = CreateNotifyIconData();
        Shell_NotifyIcon(NimDelete, ref data);
        RestoreWindowProcedure();
        if (_iconHandle != 0)
            DestroyIcon(_iconHandle);
        GC.SuppressFinalize(this);
    }

    private nint HandleWindowMessage(nint windowHandle, uint message, nuint wParam, nint lParam)
    {
        if (message == CallbackMessage)
        {
            uint mouseMessage = unchecked((uint)lParam.ToInt64());
            if (mouseMessage is WmLButtonUp or WmLButtonDoubleClick)
                _showWindow();
            else if (mouseMessage == WmRButtonUp)
                ShowContextMenu();
            return 0;
        }

        if (message == WmSysCommand && (wParam & 0xFFF0) == ScMinimize && _minimizeToTray())
        {
            _hideWindow();
            return 0;
        }

        return CallWindowProc(_previousWindowProc, windowHandle, message, wParam, lParam);
    }

    private void ShowContextMenu()
    {
        nint menu = CreatePopupMenu();
        if (menu == 0)
            return;

        try
        {
            AppendMenu(menu, MfString, MenuShow, "打开 SAMA Open Display");
            AppendMenu(menu, MfSeparator, 0, null);
            AppendMenu(menu, MfString, MenuExit, "退出");
            GetCursorPos(out Point point);
            SetForegroundWindow(_windowHandle);
            uint command = TrackPopupMenu(menu, TpmReturnCommand | TpmNonotify, point.X, point.Y, 0, _windowHandle, 0);
            if (command == MenuShow)
                _showWindow();
            else if (command == MenuExit)
                _exitApplication();
        }
        finally
        {
            DestroyMenu(menu);
        }
    }

    private NotifyIconData CreateNotifyIconData() => new()
    {
        Size = (uint)Marshal.SizeOf<NotifyIconData>(),
        WindowHandle = _windowHandle,
        Id = IconId,
        Flags = NifMessage | NifIcon | NifTip,
        CallbackMessage = CallbackMessage,
        IconHandle = _iconHandle,
        ToolTip = "SAMA Open Display",
    };

    private void RestoreWindowProcedure()
    {
        if (_previousWindowProc != 0 && IsWindow(_windowHandle))
            SetWindowProcedure(_windowHandle, _previousWindowProc);
    }

    private static nint SetWindowProcedure(nint windowHandle, nint procedure) => IntPtr.Size == 8
        ? SetWindowLongPtr(windowHandle, GwlWndProc, procedure)
        : new nint(SetWindowLong(windowHandle, GwlWndProc, procedure.ToInt32()));

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct NotifyIconData
    {
        public uint Size;
        public nint WindowHandle;
        public uint Id;
        public uint Flags;
        public uint CallbackMessage;
        public nint IconHandle;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)] public string ToolTip;
        public uint State;
        public uint StateMask;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 256)] public string Info;
        public uint TimeoutOrVersion;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 64)] public string InfoTitle;
        public uint InfoFlags;
        public Guid ItemGuid;
        public nint BalloonIconHandle;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct Point
    {
        public int X;
        public int Y;
    }

    private delegate nint WindowProc(nint windowHandle, uint message, nuint wParam, nint lParam);

    [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool Shell_NotifyIcon(uint message, ref NotifyIconData data);

    [DllImport("user32.dll", EntryPoint = "SetWindowLongPtrW", SetLastError = true)]
    private static extern nint SetWindowLongPtr(nint windowHandle, int index, nint newLong);

    [DllImport("user32.dll", EntryPoint = "SetWindowLongW", SetLastError = true)]
    private static extern int SetWindowLong(nint windowHandle, int index, int newLong);

    [DllImport("user32.dll")]
    private static extern nint CallWindowProc(nint previousWindowProcedure, nint windowHandle, uint message, nuint wParam, nint lParam);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern nint LoadImage(nint instance, string name, uint type, int width, int height, uint load);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool DestroyIcon(nint iconHandle);

    [DllImport("user32.dll")]
    private static extern nint CreatePopupMenu();

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool AppendMenu(nint menu, uint flags, nuint itemId, string? text);

    [DllImport("user32.dll")]
    private static extern uint TrackPopupMenu(nint menu, uint flags, int x, int y, int reserved, nint windowHandle, nint rectangle);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool DestroyMenu(nint menu);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetCursorPos(out Point point);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool SetForegroundWindow(nint windowHandle);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool IsWindow(nint windowHandle);
}
