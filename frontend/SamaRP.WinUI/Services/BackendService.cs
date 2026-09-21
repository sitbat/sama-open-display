using System.Diagnostics;
using System.Text.Json;
using SamaRP_WinUI.Models;

namespace SamaRP_WinUI.Services;

public sealed class BackendService
{
    public static BackendService Current { get; } = new();

    public string RootDirectory { get; }
    public string PluginDirectory { get; }
    private string PythonExecutable { get; }
    private bool UsesPythonModule { get; }

    private BackendService()
    {
        string bundledBackend = Path.Combine(AppContext.BaseDirectory, "backend", "SamaRP.Backend.exe");
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
        string? configured = Environment.GetEnvironmentVariable("SAMARP_BACKEND_ROOT");
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
            throw new InvalidOperationException($"找不到 SamaRP 后端：{PythonExecutable}");
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
        using Process process = Process.Start(start) ?? throw new InvalidOperationException("无法启动 SamaRP 后端");
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

    public async Task<bool> DetectDisplayAsync()
    {
        try
        {
            string json = await RunAsync("detect");
            using JsonDocument document = JsonDocument.Parse(json);
            return document.RootElement.EnumerateArray().Any(item =>
                item.TryGetProperty("role", out JsonElement role) && role.GetString() == "display");
        }
        catch
        {
            return false;
        }
    }

    public async Task<string> RenderPreviewAsync(string? themeId = null)
    {
        string? configuredDataDirectory = Environment.GetEnvironmentVariable("SAMARP_DATA_DIR");
        string dataDirectory = string.IsNullOrWhiteSpace(configuredDataDirectory)
            ? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SamaRP")
            : Path.GetFullPath(configuredDataDirectory);
        string directory = Path.Combine(dataDirectory, "preview");
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
