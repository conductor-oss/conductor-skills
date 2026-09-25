/**
 * Native Conductor Agent scaffold (TypeScript): one tool, run or serve by argv.
 *
 * Install: npm install @io-orkes/conductor-javascript   (pin the version from the SDK README you fetched)
 * Env:     CONDUCTOR_SERVER_URL per the guide (+ CONDUCTOR_AUTH_KEY/SECRET if required).
 *          The TS SDK 4.x reads CONDUCTOR_SERVER_URL / CONDUCTOR_AUTH_KEY / CONDUCTOR_AUTH_SECRET; worker tunables (threads, polling,
 *          streaming) -- confirm the current names from the SDK README before relying on them.
 * Server:  conductor.integrations.ai.enabled=true and OPENAI_API_KEY exported where the server runs.
 *
 * Usage:   npx tsx weather-agent.ts run "Weather in SF?"
 *          npx tsx weather-agent.ts serve     // long-lived worker process for the tool() functions
 */
import { Agent, AgentRuntime, tool } from "@io-orkes/conductor-javascript/agents";

const getWeather = tool(
  async ({ city }: { city: string }) => {
    // Tool workers must be idempotent: Conductor retries a tool task on failure or timeout.
    return { city, condition: "Sunny", temperatureC: 21 };
  },
  {
    name: "get_weather",
    description: "Return the current weather for a city.",
    inputSchema: {
      type: "object",
      properties: { city: { type: "string", description: "City name" } },
      required: ["city"],
    },
  },
);

const agent = new Agent({
  name: "weather_agent",
  model: "openai/gpt-4o-mini", // always provider/model
  instructions: "Answer weather questions with get_weather. Keep answers brief.",
  tools: [getWeather],
  maxTurns: 10,
});

const command = process.argv[2] ?? "run";
const prompt = process.argv[3] ?? "What is the weather in San Francisco?";

const runtime = new AgentRuntime();
try {
  if (command === "run") {
    const result = await runtime.run(agent, prompt);
    result.printResult();
    console.log(result.executionId); // a workflow id: conductor workflow get-execution <id>
  } else if (command === "serve") {
    await runtime.serve(agent); // blocks until the process is stopped
  } else {
    throw new Error(`unknown command ${command}; use run|serve`);
  }
} finally {
  await runtime.shutdown();
}
