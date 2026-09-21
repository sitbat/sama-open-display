using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using SamaRP_WinUI.Services;

namespace SamaRP_WinUI.Pages;

public sealed partial class SettingsPage : Page
{
    public SettingsPage()
    {
        InitializeComponent();
        BackendPath.Text = BackendService.Current.RootDirectory;
    }

    private void ThemePicker_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (App.MainWindow.Content is not FrameworkElement root)
            return;
        root.RequestedTheme = ThemePicker.SelectedIndex switch
        {
            1 => ElementTheme.Light,
            2 => ElementTheme.Dark,
            _ => ElementTheme.Default,
        };
    }
}
