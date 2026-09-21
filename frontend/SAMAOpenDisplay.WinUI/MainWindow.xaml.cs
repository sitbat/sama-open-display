using Microsoft.UI.Windowing;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using SAMAOpenDisplay_WinUI.Pages;
using SAMAOpenDisplay_WinUI.Services;
using WinRT.Interop;

// To learn more about WinUI, the WinUI project structure,
// and more about our project templates, see: http://aka.ms/winui-project-info.

namespace SAMAOpenDisplay_WinUI;

public sealed partial class MainWindow : Window
{
    private const int SwHide = 0;
    private const int SwRestore = 9;
    private readonly nint _windowHandle;
    private readonly TrayIconService _trayIcon;
    private bool _isExiting;

    public MainWindow()
    {
        InitializeComponent();

        ExtendsContentIntoTitleBar = true;
        SetTitleBar(AppTitleBar);
        AppWindow.TitleBar.PreferredHeightOption = TitleBarHeightOption.Tall;
        AppWindow.SetIcon("Assets/AppIcon.ico");
        AppWindow.Resize(new Windows.Graphics.SizeInt32(1240, 800));
        AppWindow.Closing += AppWindow_Closing;
        _windowHandle = WindowNative.GetWindowHandle(this);
        _trayIcon = new TrayIconService(
            _windowHandle,
            ShowFromTray,
            HideToTray,
            ExitApplication,
            () => App.Settings.Current.MinimizeToTray);
        NavFrame.Navigate(typeof(HomePage));
    }

    public void ApplyAppearanceTheme(int selectedIndex)
    {
        if (Content is not FrameworkElement root)
            return;
        root.RequestedTheme = selectedIndex switch
        {
            1 => ElementTheme.Light,
            2 => ElementTheme.Dark,
            _ => ElementTheme.Default,
        };
    }

    public void HideToTray()
    {
        ShowWindow(_windowHandle, SwHide);
    }

    public void ShowFromTray()
    {
        ShowWindow(_windowHandle, SwRestore);
        Activate();
        SetForegroundWindow(_windowHandle);
    }

    public void ExitApplication()
    {
        _isExiting = true;
        _trayIcon.Dispose();
        Close();
    }

    private void AppWindow_Closing(AppWindow sender, AppWindowClosingEventArgs args)
    {
        if (!_isExiting && App.Settings.Current.CloseToTray)
        {
            args.Cancel = true;
            HideToTray();
            return;
        }

        _trayIcon.Dispose();
    }

    private void TitleBar_PaneToggleRequested(TitleBar sender, object args)
    {
        NavView.IsPaneOpen = !NavView.IsPaneOpen;
    }

    private void TitleBar_BackRequested(TitleBar sender, object args)
    {
        NavFrame.GoBack();
    }

    private void NavView_SelectionChanged(NavigationView sender, NavigationViewSelectionChangedEventArgs args)
    {
        if (args.IsSettingsSelected)
        {
            NavFrame.Navigate(typeof(SettingsPage));
        }
        else if (args.SelectedItem is NavigationViewItem item)
        {
            switch (item.Tag)
            {
                case "home":
                    NavFrame.Navigate(typeof(HomePage));
                    break;
                case "about":
                    NavFrame.Navigate(typeof(AboutPage));
                    break;
                case "plugins":
                    NavFrame.Navigate(typeof(PluginsPage));
                    break;
                default:
                    throw new InvalidOperationException($"Unknown navigation item tag: {item.Tag}");
            }
        }
    }

    [System.Runtime.InteropServices.DllImport("user32.dll")]
    [return: System.Runtime.InteropServices.MarshalAs(System.Runtime.InteropServices.UnmanagedType.Bool)]
    private static extern bool ShowWindow(nint windowHandle, int command);

    [System.Runtime.InteropServices.DllImport("user32.dll")]
    [return: System.Runtime.InteropServices.MarshalAs(System.Runtime.InteropServices.UnmanagedType.Bool)]
    private static extern bool SetForegroundWindow(nint windowHandle);
}
