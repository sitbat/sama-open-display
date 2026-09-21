using System.Text.Json;

namespace SAMAOpenDisplay_WinUI.Services;

public sealed class AppSettings
{
    public int AppearanceTheme { get; set; }
    public bool StartWithWindows { get; set; }
    public bool StartMinimized { get; set; } = true;
    public bool MinimizeToTray { get; set; } = true;
    public bool CloseToTray { get; set; } = true;
}

public sealed class AppSettingsService
{
    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = true };
    private readonly string _settingsPath;

    public AppSettingsService()
    {
        string dataDirectory = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "SAMA Open Display");
        _settingsPath = Path.Combine(dataDirectory, "settings.json");
        Current = Load();
        Current.StartWithWindows = StartupService.IsEnabled;
    }

    public AppSettings Current { get; }

    public void Save()
    {
        string? directory = Path.GetDirectoryName(_settingsPath);
        if (directory is not null)
            Directory.CreateDirectory(directory);

        string temporaryPath = _settingsPath + ".tmp";
        File.WriteAllText(temporaryPath, JsonSerializer.Serialize(Current, JsonOptions));
        File.Move(temporaryPath, _settingsPath, true);
    }

    private AppSettings Load()
    {
        try
        {
            if (File.Exists(_settingsPath))
                return JsonSerializer.Deserialize<AppSettings>(File.ReadAllText(_settingsPath)) ?? new AppSettings();
        }
        catch (JsonException)
        {
            // Keep the application usable if a hand-edited settings file is invalid.
        }
        catch (IOException)
        {
            // Fall back to defaults; a later successful save repairs the file.
        }

        return new AppSettings();
    }
}
