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
    private int _previewGeneration;
    private string? _currentPreviewPath;
    private DisplayDeviceInfo? _displayDevice;

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
            ThemePicker.SelectedItem = Themes.FirstOrDefault();
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
        int generation = ++_previewGeneration;
        PreviewProgress.IsActive = true;
        try
        {
            string? themeId = (ThemePicker.SelectedItem as ThemeInfo)?.Id;
            string path = await BackendService.Current.RenderPreviewAsync(themeId);
            StorageFile file = await StorageFile.GetFileFromPathAsync(path);
            using var stream = await file.OpenReadAsync();
            BitmapImage bitmap = new();
            await bitmap.SetSourceAsync(stream);
            if (generation == _previewGeneration)
            {
                PreviewImage.Source = bitmap;
                _currentPreviewPath = path;
                UpdateHardwareAvailability();
            }
        }
        catch (Exception exception)
        {
            DeviceInfo.Severity = InfoBarSeverity.Error;
            DeviceInfo.Title = "预览后端不可用";
            DeviceInfo.Message = exception.Message;
        }
        finally
        {
            if (generation == _previewGeneration)
                PreviewProgress.IsActive = false;
        }
    }

    private async Task DetectAsync()
    {
        IReadOnlyList<DisplayDeviceInfo> displays = await BackendService.Current.DetectDisplaysAsync();
        _displayDevice = displays.FirstOrDefault();
        bool found = _displayDevice is not null;
        DeviceInfo.Severity = found ? InfoBarSeverity.Success : InfoBarSeverity.Warning;
        DeviceInfo.Title = found ? "已发现 SAMA USB 小屏" : "未检测到目标小屏";
        DeviceInfo.Message = found
            ? $"{_displayDevice!.Port} · {_displayDevice.UsbId}。协议身份将在写入前再次核验。"
            : "请检查 USB 连接或退出原厂软件后重试。";
        UpdateHardwareAvailability();
    }

    private void UpdateHardwareAvailability()
    {
        SendButton.IsEnabled = _displayDevice is not null &&
            !string.IsNullOrWhiteSpace(_currentPreviewPath) && File.Exists(_currentPreviewPath);
    }

    private async void RefreshPreview_Click(object sender, RoutedEventArgs e) => await RefreshPreviewAsync();
    private async void Detect_Click(object sender, RoutedEventArgs e) => await DetectAsync();

    private async void ThemePicker_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        UpdateThemeDescription();
        if (!_loadingThemes && IsLoaded)
            await RefreshPreviewAsync();
    }

    private async void SendButton_Click(object sender, RoutedEventArgs e)
    {
        if (_displayDevice is null || string.IsNullOrWhiteSpace(_currentPreviewPath))
            return;

        StackPanel details = new() { Spacing = 8 };
        details.Children.Add(new TextBlock
        {
            Text = "即将向 USB 小屏写入一张完整画面。请先退出 SAMA 原厂软件，避免串口被同时占用。",
            TextWrapping = TextWrapping.Wrap,
        });
        details.Children.Add(new TextBlock { Text = $"端口：{_displayDevice.Port}" });
        details.Children.Add(new TextBlock { Text = $"USB：{_displayDevice.UsbId}" });
        details.Children.Add(new TextBlock { Text = $"必须匹配的协议身份：{BackendService.VerifiedDisplayIdentity}" });
        details.Children.Add(new TextBlock { Text = $"亮度：{(int)Math.Round(BrightnessSlider.Value)}%" });

        ContentDialog dialog = new()
        {
            XamlRoot = XamlRoot,
            Title = "确认发送当前画面",
            Content = details,
            PrimaryButtonText = "确认发送",
            CloseButtonText = "取消",
            DefaultButton = ContentDialogButton.Close,
        };
        if (await dialog.ShowAsync() != ContentDialogResult.Primary)
            return;

        SendButton.IsEnabled = false;
        HardwareInfo.IsOpen = true;
        HardwareInfo.IsClosable = false;
        HardwareInfo.Severity = InfoBarSeverity.Informational;
        HardwareInfo.Title = "正在核验设备并发送…";
        HardwareInfo.Message = "身份不匹配时后端会在画面写入前中止。";
        try
        {
            string result = await BackendService.Current.SendFrameAsync(
                _currentPreviewPath,
                BackendService.VerifiedDisplayIdentity,
                (int)Math.Round(BrightnessSlider.Value));
            HardwareInfo.Severity = InfoBarSeverity.Success;
            HardwareInfo.Title = "画面发送完成";
            HardwareInfo.Message = result;
        }
        catch (Exception exception)
        {
            HardwareInfo.Severity = InfoBarSeverity.Error;
            HardwareInfo.Title = "发送失败，未继续写入";
            HardwareInfo.Message = exception.Message;
        }
        finally
        {
            HardwareInfo.IsClosable = true;
            UpdateHardwareAvailability();
        }
    }
}
