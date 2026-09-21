using System.Collections.ObjectModel;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media.Imaging;
using SamaRP_WinUI.Services;
using SamaRP_WinUI.Models;
using Windows.Storage;

namespace SamaRP_WinUI.Pages;

public sealed partial class HomePage : Page
{
    public ObservableCollection<ThemeInfo> Themes { get; } = [];
    private bool _loadingThemes;

    public HomePage()
    {
        InitializeComponent();
        ThemePicker.ItemsSource = Themes;
        Loaded += HomePage_Loaded;
    }

    private async void HomePage_Loaded(object sender, RoutedEventArgs e)
    {
        await LoadThemesAsync();
        await Task.WhenAll(RefreshPreviewAsync(), DetectAsync());
    }

    private async Task LoadThemesAsync()
    {
        _loadingThemes = true;
        try
        {
            IReadOnlyList<ThemeInfo> themes = await BackendService.Current.ListThemesAsync();
            Themes.Clear();
            foreach (ThemeInfo theme in themes)
                Themes.Add(theme);
            ThemePicker.SelectedItem = Themes.FirstOrDefault(theme =>
                theme.PluginId == "org.samarpproject.system-dashboard") ?? Themes.FirstOrDefault();
            UpdateThemeDescription();
        }
        finally
        {
            _loadingThemes = false;
        }
    }

    private void UpdateThemeDescription()
    {
        ThemeDescription.Text = ThemePicker.SelectedItem is ThemeInfo theme
            ? theme.Description
            : "没有可用主题，请前往插件中心安装或启用主题。";
    }

    private async Task RefreshPreviewAsync()
    {
        PreviewProgress.IsActive = true;
        try
        {
            string? themeId = (ThemePicker.SelectedItem as ThemeInfo)?.Id;
            string path = await BackendService.Current.RenderPreviewAsync(themeId);
            StorageFile file = await StorageFile.GetFileFromPathAsync(path);
            using var stream = await file.OpenReadAsync();
            BitmapImage bitmap = new();
            await bitmap.SetSourceAsync(stream);
            PreviewImage.Source = bitmap;
        }
        catch (Exception exception)
        {
            DeviceInfo.Severity = InfoBarSeverity.Error;
            DeviceInfo.Title = "预览后端不可用";
            DeviceInfo.Message = exception.Message;
        }
        finally
        {
            PreviewProgress.IsActive = false;
        }
    }

    private async Task DetectAsync()
    {
        bool found = await BackendService.Current.DetectDisplayAsync();
        DeviceInfo.Severity = found ? InfoBarSeverity.Success : InfoBarSeverity.Warning;
        DeviceInfo.Title = found ? "已发现 SAMA USB 小屏" : "未检测到目标小屏";
        DeviceInfo.Message = found ? "设备身份将在写入前再次核验。" : "请检查 USB 连接或退出原厂软件后重试。";
    }

    private async void RefreshPreview_Click(object sender, RoutedEventArgs e) => await RefreshPreviewAsync();
    private async void Detect_Click(object sender, RoutedEventArgs e) => await DetectAsync();

    private async void ThemePicker_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        UpdateThemeDescription();
        if (!_loadingThemes && IsLoaded)
            await RefreshPreviewAsync();
    }
}
