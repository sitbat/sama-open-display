using System.Text.Json;

int samples = 0;
while (Console.ReadLine() is { } line)
{
    try
    {
        using JsonDocument request = JsonDocument.Parse(line);
        JsonElement root = request.RootElement;
        if (root.GetProperty("protocol").GetInt32() != 2)
            return 2;
        switch (root.GetProperty("action").GetString())
        {
            case "sample":
                Console.WriteLine($"{{\"count\":{++samples}}}");
                break;
            case "shutdown":
                return 0;
            default:
                return 2;
        }
    }
    catch (JsonException)
    {
        return 2;
    }
}

return 0;
