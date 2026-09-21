using System.Text.Json.Serialization;

namespace SamaRP_WinUI.Models;

public sealed class DisplayDeviceInfo
{
    [JsonPropertyName("role")] public string Role { get; set; } = "";
    [JsonPropertyName("vid")] public int Vid { get; set; }
    [JsonPropertyName("pid")] public int Pid { get; set; }
    [JsonPropertyName("port")] public string? Port { get; set; }
    [JsonPropertyName("instance_id")] public string InstanceId { get; set; } = "";
    [JsonPropertyName("friendly_name")] public string? FriendlyName { get; set; }

    public string UsbId => $"VID_{Vid:X4}&PID_{Pid:X4}";
}
