using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media.Imaging;
using SamaRP_WinUI.Services;
using Windows.Storage;

namespace SamaRP_WinUI.Pages;

public sealed partial class HomePage : Page
{
    public HomePage()
    {
        InitializeComponent();
        Loaded += HomePage_Loaded;
    }

    private async void HomePage_Loaded(object sender, RoutedEventArgs e)
    {
        await Task.WhenAll(RefreshPreviewAsync(), DetectAsync());
    }

    private async Task RefreshPreviewAsync()
    {
        PreviewProgress.IsActive = true;
        try
        {
            string path = await BackendService.Current.RenderPreviewAsync();
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
}
