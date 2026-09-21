using System.Diagnostics;
using System.Text.Json;
using SAMAOpenDisplay_WinUI.Models;

namespace SAMAOpenDisplay_WinUI.Services;

public sealed class BackendService
{
    public static BackendService Current { get; } = new();
    public const string VerifiedDisplayIdentity = "chs_65inch.dev1_rom1.91";

    public string RootDirectory { get; }
    public string PluginDirectory { get; }
    private string PythonExecutable { get; }
    private bool UsesPythonModule { get; }

    private BackendService()
    {
        string bundledBackend = Path.Combine(AppContext.BaseDirectory, "backend", "SAMAOpenDisplay.Backend.exe");
        if (File.Exists(bundledBackend))
        {
            RootDirectory = AppContext.BaseDirectory;
            PluginDirectory = Path.Combine(AppContext.BaseDirectory, "plugins");
            UsesPythonModule = false;
            PythonExecutable = bundledBackend;
            return;
        }

        RootDirectory = LocateBackendRoot();
        PluginDirectory = Path.Combine(RootDirectory, "plugins");
        string developmentPython = Path.Combine(RootDirectory, ".venv", "Scripts", "python.exe");
        UsesPythonModule = File.Exists(developmentPython);
        PythonExecutable = UsesPythonModule
            ? developmentPython
            : bundledBackend;
    }

    private static string LocateBackendRoot()
    {
        string? configured = Environment.GetEnvironmentVariable("SAMA_OPEN_DISPLAY_BACKEND_ROOT");
        if (!string.IsNullOrWhiteSpace(configured) && Directory.Exists(configured))
            return Path.GetFullPath(configured);
        DirectoryInfo? directory = new(AppContext.BaseDirectory);
        while (directory is not null)
        {
            if (Directory.Exists(Path.Combine(directory.FullName, "sama_display")) &&
                File.Exists(Path.Combine(directory.FullName, "pyproject.toml")))
                return directory.FullName;
            directory = directory.Parent;
        }
        return Path.Combine(AppContext.BaseDirectory, "backend");
    }

    private async Task<string> RunAsync(params string[] arguments)
    {
        if (!File.Exists(PythonExecutable))
            throw new InvalidOperationException($"找不到 SAMA Open Display 后端：{PythonExecutable}");
        ProcessStartInfo start = new(PythonExecutable)
        {
            WorkingDirectory = RootDirectory,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        if (UsesPythonModule)
        {
            start.ArgumentList.Add("-m");
            start.ArgumentList.Add("sama_display");
        }
        foreach (string argument in arguments)
            start.ArgumentList.Add(argument);
        using Process process = Process.Start(start) ?? throw new InvalidOperationException("无法启动 SAMA Open Display 后端");
        string output = await process.StandardOutput.ReadToEndAsync();
        string error = await process.StandardError.ReadToEndAsync();
        await process.WaitForExitAsync();
        if (process.ExitCode != 0)
            throw new InvalidOperationException(string.IsNullOrWhiteSpace(error) ? output.Trim() : error.Trim());
        return output.Trim();
    }

    public async Task<IReadOnlyList<PluginInfo>> ListPluginsAsync()
    {
        string json = await RunAsync("plugin-list", "--directory", PluginDirectory);
        return JsonSerializer.Deserialize<List<PluginInfo>>(json) ?? [];
    }

    public async Task<IReadOnlyList<ThemeInfo>> ListThemesAsync()
    {
        string json = await RunAsync("theme-list", "--directory", PluginDirectory);
        return JsonSerializer.Deserialize<List<ThemeInfo>>(json) ?? [];
    }

    public Task InstallPluginsAsync(IEnumerable<string> paths) =>
        RunAsync(["plugin-install", .. paths, "--directory", PluginDirectory]);

    public Task EnablePluginsAsync(IEnumerable<string> ids, bool enabled) =>
        RunAsync([enabled ? "plugin-enable" : "plugin-disable", .. ids, "--directory", PluginDirectory]);

    public Task UninstallPluginsAsync(IEnumerable<string> ids) =>
        RunAsync(["plugin-uninstall", .. ids, "--directory", PluginDirectory]);

    public async Task<IReadOnlyList<DisplayDeviceInfo>> DetectDisplaysAsync()
    {
        try
        {
            string json = await RunAsync("detect");
            return (JsonSerializer.Deserialize<List<DisplayDeviceInfo>>(json) ?? [])
                .Where(item => item.Role == "display" && !string.IsNullOrWhiteSpace(item.Port))
                .ToList();
        }
        catch
        {
            return [];
        }
    }

    public Task<string> SendFrameAsync(string imagePath, string deviceIdentity, int brightness) =>
        RunAsync(
            "send",
            "--image", imagePath,
            "--brightness", brightness.ToString(System.Globalization.CultureInfo.InvariantCulture),
            "--device-id", deviceIdentity,
            "--write-hardware");

    public async Task<string> RunDashboardAsync(
        string? themeId,
        string deviceIdentity,
        int brightness,
        CancellationToken cancellationToken)
    {
        string stopDirectory = Path.Combine(GetDataDirectory(), "control");
        Directory.CreateDirectory(stopDirectory);
        string stopFile = Path.Combine(stopDirectory, $"dashboard-stop-{Guid.NewGuid():N}.signal");
        List<string> arguments = [
            "dashboard-live",
            "--seconds", "43200",
            "--interval", "1.0",
            "--brightness", brightness.ToString(System.Globalization.CultureInfo.InvariantCulture),
            "--device-id", deviceIdentity,
            "--plugins-directory", PluginDirectory,
            "--stop-file", stopFile,
            "--write-hardware",
        ];
        if (!string.IsNullOrWhiteSpace(themeId))
        {
            arguments.Add("--theme-id");
            arguments.Add(themeId);
        }

        using CancellationTokenRegistration registration = cancellationToken.Register(() =>
        {
            try
            {
                File.WriteAllText(stopFile, "stop");
            }
            catch (IOException)
            {
                // The backend may already have completed and removed the need for a stop signal.
            }
        });
        try
        {
            return await RunAsync([.. arguments]);
        }
        finally
        {
            try { File.Delete(stopFile); } catch (IOException) { }
        }
    }

    private static string GetDataDirectory()
    {
        string? configuredDataDirectory = Environment.GetEnvironmentVariable("SAMA_OPEN_DISPLAY_DATA_DIR");
        return string.IsNullOrWhiteSpace(configuredDataDirectory)
            ? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SAMA Open Display")
            : Path.GetFullPath(configuredDataDirectory);
    }

    public async Task<string> RenderPreviewAsync(string? themeId = null)
    {
        string directory = Path.Combine(GetDataDirectory(), "preview");
        Directory.CreateDirectory(directory);
        string path = Path.Combine(directory, $"dashboard-{Guid.NewGuid():N}.png");
        List<string> arguments = ["preview", "--output", path, "--plugins-directory", PluginDirectory];
        if (!string.IsNullOrWhiteSpace(themeId))
        {
            arguments.Add("--theme-id");
            arguments.Add(themeId);
        }
        await RunAsync([.. arguments]);
        return path;
    }
}
