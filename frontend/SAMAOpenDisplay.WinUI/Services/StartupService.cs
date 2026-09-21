using Microsoft.Win32;

namespace SAMAOpenDisplay_WinUI.Services;

public static class StartupService
{
    private const string RunKeyPath = @"Software\Microsoft\Windows\CurrentVersion\Run";
    private const string ValueName = "SAMAOpenDisplay";

    public static bool IsEnabled
    {
        get
        {
            using RegistryKey? key = Registry.CurrentUser.OpenSubKey(RunKeyPath, false);
            return key?.GetValue(ValueName) is string value && !string.IsNullOrWhiteSpace(value);
        }
    }

    public static void SetEnabled(bool enabled)
    {
        using RegistryKey key = Registry.CurrentUser.CreateSubKey(RunKeyPath, true)
            ?? throw new InvalidOperationException("无法打开 Windows 当前用户启动项注册表。");

        if (!enabled)
        {
            key.DeleteValue(ValueName, false);
            return;
        }

        string executablePath = Environment.ProcessPath
            ?? throw new InvalidOperationException("无法确定应用程序路径。");
        key.SetValue(ValueName, $"\"{executablePath}\" --startup", RegistryValueKind.String);
    }
}
