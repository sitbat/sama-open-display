using System.Collections.ObjectModel;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media.Imaging;
using SAMAOpenDisplay_WinUI.Services;
using SAMAOpenDisplay_WinUI.Models;
using Windows.Storage;
using Windows.Storage.Pickers;

namespace SAMAOpenDisplay_WinUI.Pages;

public sealed partial class HomePage : Page
{
    private enum ContentMode
    {
        Theme,
        Image,
        Text,
    }

    public ObservableCollection<ThemeInfo> Themes { get; } = [];
    private bool _loadingThemes;
    private int _previewGeneration;
    private string? _currentPreviewPath;
    private DisplayDeviceInfo? _displayDevice;
    private bool _hardwareBusy;
    private bool _dashboardRunning;
    private CancellationTokenSource? _dashboardCancellation;
    private ContentMode _contentMode = ContentMode.Theme;
    private string? _selectedImagePath;
    private string _textContent = "你好，SAMA Open Display";
    private bool _changingContentMode;
    private bool _initialized;

    public HomePage()
    {
        InitializeComponent();
        NavigationCacheMode = Microsoft.UI.Xaml.Navigation.NavigationCacheMode.Required;
        ThemePicker.ItemsSource = Themes;
        RestoreDisplayState();
        Loaded += HomePage_Loaded;
    }

    private async void HomePage_Loaded(object sender, RoutedEventArgs e)
    {
        if (_initialized)
        {
            UpdateHardwareAvailability();
            return;
        }

        _initialized = true;
        await LoadThemesAsync();
        await Task.WhenAll(RefreshPreviewAsync(), DetectAsync());
        if (App.Settings.Current.StartSendingOnLaunch)
            await StartDashboardAsync(showUnavailableStatus: true);
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
            string? selectedThemeId = App.Settings.Current.SelectedThemeId;
            ThemePicker.SelectedItem = Themes.FirstOrDefault(theme =>
                string.Equals(theme.Id, selectedThemeId, StringComparison.OrdinalIgnoreCase)) ?? Themes.FirstOrDefault();
            UpdateThemeDescription();
        }
        finally
        {
            _loadingThemes = false;
        }
        PersistDisplayState();
    }

    private void RestoreDisplayState()
    {
        AppSettings settings = App.Settings.Current;
        _selectedImagePath = settings.SelectedImagePath;
        _textContent = string.IsNullOrWhiteSpace(settings.DisplayTextContent)
            ? "你好，SAMA Open Display"
            : settings.DisplayTextContent;
        string restoredMode = settings.DisplayContentMode?.ToLowerInvariant() ?? "theme";
        bool restoredImageExists = !string.IsNullOrWhiteSpace(_selectedImagePath) && File.Exists(_selectedImagePath);
        _contentMode = restoredMode switch
        {
            "image" when restoredImageExists => ContentMode.Image,
            "text" => ContentMode.Text,
            _ => ContentMode.Theme,
        };
        if (restoredMode == "image" && !restoredImageExists)
            _selectedImagePath = null;
        FitPicker.SelectedIndex = string.Equals(settings.DisplayFitMode, "contain", StringComparison.OrdinalIgnoreCase) ? 1 : 0;

        _changingContentMode = true;
        ThemeOption.IsChecked = _contentMode == ContentMode.Theme;
        ImageOption.IsChecked = _contentMode == ContentMode.Image;
        TextOption.IsChecked = _contentMode == ContentMode.Text;
        _changingContentMode = false;

        ImageDescription.Visibility = _contentMode == ContentMode.Image ? Visibility.Visible : Visibility.Collapsed;
        ChooseImageButton.Visibility = ImageDescription.Visibility;
        if (_contentMode == ContentMode.Image)
            ImageDescription.Text = Path.GetFileName(_selectedImagePath);
        TextDescription.Visibility = _contentMode == ContentMode.Text ? Visibility.Visible : Visibility.Collapsed;
        EditTextButton.Visibility = TextDescription.Visibility;
        if (_contentMode == ContentMode.Text)
            TextDescription.Text = _textContent.ReplaceLineEndings(" ");
    }

    private void PersistDisplayState()
    {
        AppSettings settings = App.Settings.Current;
        settings.DisplayContentMode = _contentMode switch
        {
            ContentMode.Image => "image",
            ContentMode.Text => "text",
            _ => "theme",
        };
        settings.SelectedThemeId = (ThemePicker.SelectedItem as ThemeInfo)?.Id;
        settings.SelectedImagePath = _selectedImagePath;
        settings.DisplayTextContent = _textContent;
        settings.DisplayFitMode = CurrentFitMode();
        try
        {
            App.Settings.Save();
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            HardwareInfo.IsOpen = true;
            HardwareInfo.IsClosable = true;
            HardwareInfo.Severity = InfoBarSeverity.Warning;
            HardwareInfo.Title = "无法保存显示设置";
            HardwareInfo.Message = exception.Message;
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
            string path = _contentMode switch
            {
                ContentMode.Image when !string.IsNullOrWhiteSpace(_selectedImagePath) =>
                    await BackendService.Current.RenderImagePreviewAsync(_selectedImagePath, CurrentFitMode()),
                ContentMode.Text => await BackendService.Current.RenderTextPreviewAsync(_textContent),
                _ => await BackendService.Current.RenderThemePreviewAsync((ThemePicker.SelectedItem as ThemeInfo)?.Id),
            };
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
        bool ready = _displayDevice is not null &&
            !string.IsNullOrWhiteSpace(_currentPreviewPath) && File.Exists(_currentPreviewPath);
        SendButton.IsEnabled = ready && !_hardwareBusy;
        ContinuousButton.IsEnabled = _dashboardRunning ||
            (ready && !_hardwareBusy && _contentMode == ContentMode.Theme);
        ThemePicker.IsEnabled = !_hardwareBusy && _contentMode == ContentMode.Theme;
        FitPicker.IsEnabled = !_hardwareBusy && _contentMode == ContentMode.Image;
        ThemeOption.IsEnabled = !_hardwareBusy;
        ImageOption.IsEnabled = !_hardwareBusy;
        TextOption.IsEnabled = !_hardwareBusy;
        ChooseImageButton.IsEnabled = !_hardwareBusy;
        EditTextButton.IsEnabled = !_hardwareBusy;
    }

    private async void RefreshPreview_Click(object sender, RoutedEventArgs e) => await RefreshPreviewAsync();
    private async void Detect_Click(object sender, RoutedEventArgs e) => await DetectAsync();

    private async void ThemePicker_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        UpdateThemeDescription();
        if (!_loadingThemes && IsLoaded)
        {
            PersistDisplayState();
            await RefreshPreviewAsync();
        }
    }

    private string CurrentFitMode() => FitPicker.SelectedIndex == 1 ? "contain" : "cover";

    private async void ThemeOption_Checked(object sender, RoutedEventArgs e)
    {
        if (_changingContentMode || !IsLoaded)
            return;
        _contentMode = ContentMode.Theme;
        ImageDescription.Visibility = Visibility.Collapsed;
        ChooseImageButton.Visibility = Visibility.Collapsed;
        TextDescription.Visibility = Visibility.Collapsed;
        EditTextButton.Visibility = Visibility.Collapsed;
        PersistDisplayState();
        InvalidatePreview();
        await RefreshPreviewAsync();
    }

    private async void ImageOption_Checked(object sender, RoutedEventArgs e)
    {
        if (_changingContentMode || !IsLoaded)
            return;
        if (!await ChooseImageAsync())
            RestoreSelectedMode();
    }

    private async Task<bool> ChooseImageAsync()
    {
        FileOpenPicker picker = new();
        foreach (string extension in new[] { ".png", ".jpg", ".jpeg", ".bmp", ".webp" })
            picker.FileTypeFilter.Add(extension);
        picker.SuggestedStartLocation = PickerLocationId.PicturesLibrary;
        nint hwnd = WinRT.Interop.WindowNative.GetWindowHandle(App.MainWindow);
        WinRT.Interop.InitializeWithWindow.Initialize(picker, hwnd);
        StorageFile? file = await picker.PickSingleFileAsync();
        if (file is null)
            return false;

        _contentMode = ContentMode.Image;
        _selectedImagePath = file.Path;
        ImageDescription.Text = file.Name;
        ImageDescription.Visibility = Visibility.Visible;
        ChooseImageButton.Visibility = Visibility.Visible;
        TextDescription.Visibility = Visibility.Collapsed;
        EditTextButton.Visibility = Visibility.Collapsed;
        PersistDisplayState();
        InvalidatePreview();
        await RefreshPreviewAsync();
        return true;
    }

    private async void ChooseImageButton_Click(object sender, RoutedEventArgs e) => await ChooseImageAsync();

    private async void TextOption_Checked(object sender, RoutedEventArgs e)
    {
        if (_changingContentMode || !IsLoaded)
            return;
        if (!await EditTextAsync())
            RestoreSelectedMode();
    }

    private async Task<bool> EditTextAsync()
    {
        TextBox editor = new()
        {
            Text = _textContent,
            AcceptsReturn = true,
            TextWrapping = TextWrapping.Wrap,
            MinWidth = 480,
            MinHeight = 180,
            SelectionStart = _textContent.Length,
        };
        ContentDialog dialog = new()
        {
            XamlRoot = XamlRoot,
            Title = "编辑显示文本",
            Content = editor,
            PrimaryButtonText = "生成预览",
            CloseButtonText = "取消",
            DefaultButton = ContentDialogButton.Primary,
        };
        if (await dialog.ShowAsync() != ContentDialogResult.Primary || string.IsNullOrWhiteSpace(editor.Text))
            return false;

        _contentMode = ContentMode.Text;
        _textContent = editor.Text.Trim();
        TextDescription.Text = _textContent.ReplaceLineEndings(" ");
        TextDescription.Visibility = Visibility.Visible;
        EditTextButton.Visibility = Visibility.Visible;
        ImageDescription.Visibility = Visibility.Collapsed;
        ChooseImageButton.Visibility = Visibility.Collapsed;
        PersistDisplayState();
        InvalidatePreview();
        await RefreshPreviewAsync();
        return true;
    }

    private async void EditTextButton_Click(object sender, RoutedEventArgs e) => await EditTextAsync();

    private async void FitPicker_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (IsLoaded && _contentMode == ContentMode.Image && !string.IsNullOrWhiteSpace(_selectedImagePath))
        {
            PersistDisplayState();
            InvalidatePreview();
            await RefreshPreviewAsync();
        }
    }

    private void InvalidatePreview()
    {
        _currentPreviewPath = null;
        UpdateHardwareAvailability();
    }

    private void RestoreSelectedMode()
    {
        _changingContentMode = true;
        ThemeOption.IsChecked = _contentMode == ContentMode.Theme;
        ImageOption.IsChecked = _contentMode == ContentMode.Image;
        TextOption.IsChecked = _contentMode == ContentMode.Text;
        _changingContentMode = false;
    }

    private async void SendButton_Click(object sender, RoutedEventArgs e)
    {
        if (_displayDevice is null || string.IsNullOrWhiteSpace(_currentPreviewPath))
            return;

        _hardwareBusy = true;
        UpdateHardwareAvailability();
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
            _hardwareBusy = false;
            UpdateHardwareAvailability();
        }
    }

    private async void ContinuousButton_Click(object sender, RoutedEventArgs e)
    {
        if (_dashboardRunning)
        {
            ContinuousButton.IsEnabled = false;
            HardwareInfo.Title = "正在安全停止…";
            HardwareInfo.Message = "当前传输块结束后会关闭串口。";
            _dashboardCancellation?.Cancel();
            return;
        }
        await StartDashboardAsync(showUnavailableStatus: false);
    }

    private async Task StartDashboardAsync(bool showUnavailableStatus)
    {
        if (_contentMode != ContentMode.Theme || _displayDevice is null || ThemePicker.SelectedItem is not ThemeInfo theme)
        {
            if (showUnavailableStatus)
            {
                HardwareInfo.IsOpen = true;
                HardwareInfo.IsClosable = true;
                HardwareInfo.Severity = InfoBarSeverity.Warning;
                HardwareInfo.Title = "未能自动开始持续发送";
                HardwareInfo.Message = _contentMode != ContentMode.Theme
                    ? "持续发送仅适用于主题；已恢复上次的静态内容，可手动发送当前画面。"
                    : _displayDevice is null
                        ? "启动时未检测到目标小屏，请连接设备后手动开始。"
                        : "当前没有可用主题，请检查主题或插件设置。";
            }
            return;
        }

        _hardwareBusy = true;
        _dashboardRunning = true;
        _dashboardCancellation = new CancellationTokenSource();
        ContinuousButton.Content = "停止持续发送画面";
        UpdateHardwareAvailability();
        HardwareInfo.IsOpen = true;
        HardwareInfo.IsClosable = false;
        HardwareInfo.Severity = InfoBarSeverity.Informational;
        HardwareInfo.Title = "正在持续发送画面";
        HardwareInfo.Message = $"正在使用“{theme.Name}”，点击停止后会安全关闭串口。";
        try
        {
            string result = await BackendService.Current.RunDashboardAsync(
                theme.Id,
                BackendService.VerifiedDisplayIdentity,
                (int)Math.Round(BrightnessSlider.Value),
                _dashboardCancellation.Token);
            HardwareInfo.Severity = InfoBarSeverity.Success;
            HardwareInfo.Title = _dashboardCancellation.IsCancellationRequested ? "持续发送已停止" : "持续发送已结束";
            HardwareInfo.Message = result;
        }
        catch (Exception exception)
        {
            HardwareInfo.Severity = InfoBarSeverity.Error;
            HardwareInfo.Title = "持续发送异常停止";
            HardwareInfo.Message = exception.Message;
        }
        finally
        {
            _dashboardCancellation.Dispose();
            _dashboardCancellation = null;
            _dashboardRunning = false;
            _hardwareBusy = false;
            ContinuousButton.Content = "开始持续发送画面";
            HardwareInfo.IsClosable = true;
            UpdateHardwareAvailability();
        }
    }
}
