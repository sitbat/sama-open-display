using System.Text.Json.Serialization;

namespace SAMAOpenDisplay_WinUI.Models;

public sealed class ThemeInfo
{
    [JsonPropertyName("id")] public string Id { get; set; } = "";
    [JsonPropertyName("name")] public string Name { get; set; } = "";
    [JsonPropertyName("author")] public string Author { get; set; } = "";
    [JsonPropertyName("description")] public string Description { get; set; } = "";
    [JsonPropertyName("plugin_id")] public string PluginId { get; set; } = "";

    public string SourceLabel => string.IsNullOrEmpty(PluginId) ? "内置主题" : "主题插件";
}
