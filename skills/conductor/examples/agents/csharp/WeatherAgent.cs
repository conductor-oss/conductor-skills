// Native Conductor Agent scaffold (C#): Agent + one [Tool] method.
//
// PREVIEW: the conductor-ai NuGet package is not yet published. Add a project reference to
// Conductor.AI from https://github.com/conductor-oss/csharp-sdk instead of `dotnet add package`.
// Env:    CONDUCTOR_SERVER_URL (+ CONDUCTOR_AUTH_KEY/SECRET if required). The .NET SDK still reads
//         AGENTSPAN_* names for runtime tunables -- confirm from the SDK README. Provider key on the server.
// Usage:  dotnet run -- run|deploy|serve   (serve blocks; run it as a long-lived process)
using Conductor.AI;

public class WeatherTools
{
    [Tool("Return the current weather for a city.", Name = "get_weather")]
    public string GetWeather(string city)
    {
        // Tool workers must be idempotent: Conductor retries a tool task on failure or timeout.
        return $"{city}: Sunny, 21C";
    }
}

public static class WeatherAgent
{
    public static async Task Main(string[] args)
    {
        var command = args.Length > 0 ? args[0] : "run";

        var agent = new Agent("weather_agent")
        {
            Model = "openai/gpt-4o-mini", // always provider/model
            Instructions = "Answer weather questions with get_weather. Keep answers brief.",
            Tools = ToolRegistry.FromInstance(new WeatherTools()),
            MaxTurns = 10,
        };

        await using var runtime = new AgentRuntime();
        switch (command)
        {
            case "run":
                var result = await runtime.RunAsync(agent, "What is the weather in San Francisco?");
                result.PrintResult();
                break;
            case "deploy":
                await runtime.DeployAsync(agent); // registers only; nothing runs until served
                break;
            case "serve":
                await runtime.ServeAsync(agent); // blocks; polls the [Tool] workers
                break;
            default:
                throw new ArgumentException("use run|deploy|serve");
        }
    }
}
