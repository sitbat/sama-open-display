using System.Collections.ObjectModel;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using SAMAOpenDisplay_WinUI.Models;
using SAMAOpenDisplay_WinUI.Services;
using Windows.Storage.Pickers;

namespace SAMAOpenDisplay_WinUI.Pages;

public sealed partial class PluginsPage : Page
{
    public ObservableCollection<PluginInfo> Plugins { get; } = [];

    public PluginsPage()
    {
        InitializeComponent();
        PluginList.ItemsSource = Plugins;
        Loaded += async (_, _) => await RefreshAsync();
    }

    private IReadOnlyList<string> SelectedIds() =>
        PluginList.SelectedItems.Cast<PluginInfo>().Select(item => item.Id).ToList();

    private async Task RefreshAsync()
    {
        try
        {
            IReadOnlyList<PluginInfo> items = await BackendService.Current.ListPluginsAsync();
            Plugins.Clear();
            foreach (PluginInfo item in items)
                Plugins.Add(item);
            PluginCount.Text = $"{Plugins.Count} 个插件 · {Plugins.Count(item => item.Enabled && string.IsNullOrEmpty(item.Problem))} 个可用";
        }
        catch (Exception exception)
        {
            ShowStatus("无法读取插件", exception.Message, InfoBarSeverity.Error);
        }
    }

    private void ShowStatus(string title, string message, InfoBarSeverity severity)
    {
        StatusInfo.Title = title;
        StatusInfo.Message = message;
        StatusInfo.Severity = severity;
        StatusInfo.IsOpen = true;
    }

    private async void Install_Click(object sender, RoutedEventArgs e)
    {
        FileOpenPicker picker = new();
        picker.FileTypeFilter.Add(".sodpkg");
        picker.SuggestedStartLocation = PickerLocationId.Downloads;
        nint hwnd = WinRT.Interop.WindowNative.GetWindowHandle(App.MainWindow);
        WinRT.Interop.InitializeWithWindow.Initialize(picker, hwnd);
        IReadOnlyList<Windows.Storage.StorageFile> files = await picker.PickMultipleFilesAsync();
        if (files.Count == 0)
            return;
        try
        {
            IReadOnlyList<PluginInfo> pending = await BackendService.Current.InspectPluginsAsync(files.Select(file => file.Path));
            bool executesCode = pending.Any(item => item.ExecutesCode);
            StackPanel summary = new() { Spacing = 8 };
            summary.Children.Add(new TextBlock
            {
                Text = string.Join(Environment.NewLine, pending.Select(item => $"• {item.Name} {item.Version} · {item.TypeLabel}")),
                TextWrapping = TextWrapping.Wrap,
            });
            summary.Children.Add(new TextBlock
            {
                Text = executesCode
                    ? "其中包含可执行数据接口插件。它会作为独立进程运行，但仍拥有当前 Windows 用户的权限；请只安装你信任来源的插件。"
                    : "布局主题只包含声明式布局与资源，不会执行第三方代码。",
                TextWrapping = TextWrapping.Wrap,
                Foreground = executesCode
                    ? new Microsoft.UI.Xaml.Media.SolidColorBrush(Microsoft.UI.Colors.OrangeRed)
                    : (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["TextFillColorSecondaryBrush"],
            });
            ContentDialog confirmation = new()
            {
                XamlRoot = XamlRoot,
                Title = executesCode ? "确认安装可执行插件" : "安装插件",
                Content = summary,
                PrimaryButtonText = "安装",
                CloseButtonText = "取消",
                DefaultButton = ContentDialogButton.Close,
            };
            if (await confirmation.ShowAsync() != ContentDialogResult.Primary)
                return;
            await BackendService.Current.InstallPluginsAsync(files.Select(file => file.Path));
            await RefreshAsync();
            ShowStatus("安装完成", $"已安装 {files.Count} 个插件。", InfoBarSeverity.Success);
        }
        catch (Exception exception)
        {
            ShowStatus("安装失败", exception.Message, InfoBarSeverity.Error);
        }
    }

    private async Task ChangeStateAsync(bool enabled)
    {
        IReadOnlyList<string> ids = SelectedIds();
        if (ids.Count == 0)
            return;
        try
        {
            await BackendService.Current.EnablePluginsAsync(ids, enabled);
            await RefreshAsync();
        }
        catch (Exception exception)
        {
            ShowStatus("插件状态未更改", exception.Message, InfoBarSeverity.Error);
        }
    }

    private async void Enable_Click(object sender, RoutedEventArgs e) => await ChangeStateAsync(true);
    private async void Disable_Click(object sender, RoutedEventArgs e) => await ChangeStateAsync(false);
    private async void Refresh_Click(object sender, RoutedEventArgs e) => await RefreshAsync();

    private async void Uninstall_Click(object sender, RoutedEventArgs e)
    {
        IReadOnlyList<string> ids = SelectedIds();
        if (ids.Count == 0)
            return;
        ContentDialog dialog = new()
        {
            XamlRoot = XamlRoot,
            Title = "卸载插件",
            Content = $"确定卸载所选 {ids.Count} 个插件？依赖保护仍会阻止不安全的删除。",
            PrimaryButtonText = "卸载",
            CloseButtonText = "取消",
            DefaultButton = ContentDialogButton.Close,
        };
        if (await dialog.ShowAsync() != ContentDialogResult.Primary)
            return;
        try
        {
            await BackendService.Current.UninstallPluginsAsync(ids);
            await RefreshAsync();
        }
        catch (Exception exception)
        {
            ShowStatus("卸载失败", exception.Message, InfoBarSeverity.Error);
        }
    }
}
