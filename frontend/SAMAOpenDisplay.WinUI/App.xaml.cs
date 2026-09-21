using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Data;
using Microsoft.UI.Xaml.Input;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Navigation;
using SAMAOpenDisplay_WinUI.Services;

// To learn more about WinUI, the WinUI project structure,
// and more about our project templates, see: http://aka.ms/winui-project-info.

namespace SAMAOpenDisplay_WinUI;

/// <summary>
/// Provides application-specific behavior to supplement the default Application class.
/// </summary>
public partial class App : Application
{
    public static MainWindow MainWindow { get; private set; } = null!;
    public static AppSettingsService Settings { get; } = new();
    
    /// <summary>
    /// Initializes the singleton application object.  This is the first line of authored code
    /// executed, and as such is the logical equivalent of main() or WinMain().
    /// </summary>
    public App()
    {
        InitializeComponent();
    }

    /// <summary>
    /// Invoked when the application is launched.
    /// </summary>
    /// <param name="args">Details about the launch request and process.</param>
    protected override void OnLaunched(Microsoft.UI.Xaml.LaunchActivatedEventArgs args)
    {
        MainWindow = new MainWindow();
        MainWindow.Activate();
        MainWindow.ApplyAppearanceTheme(Settings.Current.AppearanceTheme);

        bool launchedAtStartup = Environment.GetCommandLineArgs()
            .Any(argument => string.Equals(argument, "--startup", StringComparison.OrdinalIgnoreCase));
        if (launchedAtStartup && Settings.Current.StartMinimized)
            MainWindow.HideToTray();
    }
}
