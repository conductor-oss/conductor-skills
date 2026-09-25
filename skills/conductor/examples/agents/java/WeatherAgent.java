// Native Conductor Agent scaffold (Java): Agent.builder() + one @Tool method.
//
// Gradle: implementation 'org.conductoross:conductor-client-ai:<VERSION>'
//   The artifact is conductor-client-ai -- NOT conductor-ai as one UI quickstart says. Fetch the
//   current <VERSION> from Maven Central or the java-sdk README before pinning. Spring Boot apps
//   can use conductor-client-ai-spring instead.
// Env:    CONDUCTOR_SERVER_URL (+ CONDUCTOR_AUTH_KEY/SECRET if required). Provider key on the server.
// Usage:  WeatherAgent run|deploy|serve   (serve blocks; run it as a long-lived process)

import java.util.List;

import org.conductoross.conductor.ai.Agent;
import org.conductoross.conductor.ai.AgentRuntime;
import org.conductoross.conductor.ai.annotations.Tool;
import org.conductoross.conductor.ai.internal.ToolRegistry; // confirm package from java-sdk docs/agents
import org.conductoross.conductor.ai.model.AgentResult;
import org.conductoross.conductor.ai.model.ToolDef;

public class WeatherAgent {

    /** Tool methods live on a plain class; ToolRegistry turns each @Tool method into a ToolDef. */
    public static class Tools {
        @Tool(name = "get_weather", description = "Return the current weather for a city.")
        public String getWeather(String city) {
            // Tool workers must be idempotent: Conductor retries a tool task on failure or timeout.
            return city + ": Sunny, 21C";
        }
    }

    public static void main(String[] args) {
        String command = args.length > 0 ? args[0] : "run";
        List<ToolDef> tools = ToolRegistry.fromInstance(new Tools());

        Agent agent = Agent.builder()
            .name("weather_agent")
            .model("openai/gpt-4o-mini") // always provider/model
            .instructions("Answer weather questions with get_weather. Keep answers brief.")
            .tools(tools)
            .maxTurns(10)
            .build();

        try (AgentRuntime runtime = new AgentRuntime()) {
            switch (command) {
                case "run" -> {
                    AgentResult result = runtime.run(agent, "What is the weather in San Francisco?");
                    result.printResult();
                }
                case "deploy" -> runtime.deploy(agent); // registers only; nothing runs until served
                case "serve" -> runtime.serve(agent);   // blocks; polls the @Tool workers
                default -> throw new IllegalArgumentException("use run|deploy|serve");
            }
        }
    }
}
