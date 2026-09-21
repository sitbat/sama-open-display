using System.Text.Json.Serialization;

namespace SamaRP_WinUI.Models;

public sealed class PluginInfo
{
    [JsonPropertyName("id")] public string Id { get; set; } = "";
    [JsonPropertyName("name")] public string Name { get; set; } = "";
    [JsonPropertyName("version")] public string Version { get; set; } = "";
    [JsonPropertyName("author")] public string Author { get; set; } = "";
    [JsonPropertyName("kind")] public string Kind { get; set; } = "";
    [JsonPropertyName("description")] public string Description { get; set; } = "";
    [JsonPropertyName("dependencies")] public string[] Dependencies { get; set; } = [];
    [JsonPropertyName("permissions")] public string[] Permissions { get; set; } = [];
    [JsonPropertyName("enabled")] public bool Enabled { get; set; }
    [JsonPropertyName("problem")] public string Problem { get; set; } = "";

    public string TypeLabel => Kind == "data-provider" ? "数据前置" : "显示主题";
    public string StateLabel => string.IsNullOrEmpty(Problem) ? (Enabled ? "已启用" : "已停用") : Problem;
    public string DependencyLabel => Dependencies.Length == 0 ? "无前置插件" : $"前置：{string.Join(", ", Dependencies)}";
    public string PermissionLabel => Permissions.Length == 0 ? "不读取电脑数据" : $"权限：{string.Join(", ", Permissions)}";
}
