/**
 * Vercel AI SDK tool() objects on a Conductor Agent (verbatim from the server UI quickstart).
 *
 * Install: npm install @io-orkes/conductor-javascript ai@4 zod@3
 * Env:     CONDUCTOR_SERVER_URL (+ CONDUCTOR_AUTH_KEY/SECRET if required). The TS SDK still reads
 *          CONDUCTOR_SERVER_URL / CONDUCTOR_AUTH_KEY / CONDUCTOR_AUTH_SECRET env (SDK 4.x); tunables via the AgentRuntime options object.
 *
 * Vercel AI is TypeScript-only. Pass AI-SDK tool() objects directly in Agent.tools; the runtime reads
 * `parameters` as the input schema. Execution model: COMPILED -- LLM turns on the server; `execute`
 * functions become worker tasks that need runtime.serve(agent).
 */
// Version note: this `tool({ parameters })` shape is AI SDK 4, which the Conductor SDK auto-detects
// (Zod `parameters` + `execute`) and names from the first 30 chars of `description`. AI SDK 5+ renamed
// `parameters` -> `inputSchema` and is NOT auto-detected: declare the tool with the native
// `tool(execute, { name, description, inputSchema })` from "@io-orkes/conductor-javascript/agents" instead.
import { tool } from "ai";
import { z } from "zod";
import { Agent, AgentRuntime } from "@io-orkes/conductor-javascript/agents";

const weather = tool({
  description: "Get weather for a city",
  parameters: z.object({ city: z.string() }),
  execute: async ({ city }) => ({ city, condition: "Sunny" }),
});

const agent = new Agent({
  name: "vercel_weather",
  model: "openai/gpt-4o-mini",
  instructions: "Use the weather tool.",
  tools: [weather],
});

const runtime = new AgentRuntime();
try {
  const result = await runtime.run(agent, "Weather in San Francisco?");
  result.printResult();
} finally {
  await runtime.shutdown();
}
