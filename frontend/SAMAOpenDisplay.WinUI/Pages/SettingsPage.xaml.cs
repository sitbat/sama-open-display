using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using SAMAOpenDisplay_WinUI.Services;

namespace SAMAOpenDisplay_WinUI.Pages;

public sealed partial class SettingsPage : Page
{
    private bool _initializing = true;

    public SettingsPage()
    {
        InitializeComponent();
        BackendPath.Text = BackendService.Current.RootDirectory;
        AppSettings settings = App.Settings.Current;
        ThemePicker.SelectedIndex = Math.Clamp(settings.AppearanceTheme, 0, 2);
        StartupToggle.IsOn = settings.StartWithWindows;
        StartMinimizedToggle.IsOn = settings.StartMinimized;
        StartSendingToggle.IsOn = settings.StartSendingOnLaunch;
        MinimizeToTrayToggle.IsOn = settings.MinimizeToTray;
        CloseToTrayToggle.IsOn = settings.CloseToTray;
        StartMinimizedToggle.IsEnabled = settings.StartWithWindows;
        _initializing = false;
    }

    private void ThemePicker_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (_initializing || ThemePicker.SelectedIndex < 0)
            return;

        App.Settings.Current.AppearanceTheme = ThemePicker.SelectedIndex;
        App.MainWindow.ApplyAppearanceTheme(ThemePicker.SelectedIndex);
        SaveSettings();
    }

    private void StartupToggle_Toggled(object sender, RoutedEventArgs e)
    {
        if (_initializing)
            return;

        bool enabled = StartupToggle.IsOn;
        try
        {
            StartupService.SetEnabled(enabled);
            App.Settings.Current.StartWithWindows = enabled;
            StartMinimizedToggle.IsEnabled = enabled;
            SaveSettings();
            ShowStatus(enabled ? "已启用开机自动启动。" : "已关闭开机自动启动。", InfoBarSeverity.Success);
        }
        catch (Exception exception) when (exception is InvalidOperationException or UnauthorizedAccessException or IOException)
        {
            _initializing = true;
            StartupToggle.IsOn = !enabled;
            _initializing = false;
            ShowStatus($"无法修改开机启动项：{exception.Message}", InfoBarSeverity.Error);
        }
    }

    private void BackgroundToggle_Toggled(object sender, RoutedEventArgs e)
    {
        if (_initializing)
            return;

        AppSettings settings = App.Settings.Current;
        settings.StartMinimized = StartMinimizedToggle.IsOn;
        settings.StartSendingOnLaunch = StartSendingToggle.IsOn;
        settings.MinimizeToTray = MinimizeToTrayToggle.IsOn;
        settings.CloseToTray = CloseToTrayToggle.IsOn;
        SaveSettings();
    }

    private void SaveSettings()
    {
        try
        {
            App.Settings.Save();
        }
        catch (IOException exception)
        {
            ShowStatus($"无法保存设置：{exception.Message}", InfoBarSeverity.Error);
        }
        catch (UnauthorizedAccessException exception)
        {
            ShowStatus($"无法保存设置：{exception.Message}", InfoBarSeverity.Error);
        }
    }

    private void ShowStatus(string message, InfoBarSeverity severity)
    {
        SettingsStatus.Message = message;
        SettingsStatus.Severity = severity;
        SettingsStatus.IsOpen = true;
    }
}
