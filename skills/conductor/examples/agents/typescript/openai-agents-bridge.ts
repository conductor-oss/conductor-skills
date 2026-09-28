/**
 * OpenAI Agents SDK on Conductor (verbatim from the server UI quickstart).
 *
 * Install: npm install @io-orkes/conductor-javascript @openai/agents   (pin from the SDK README you fetched)
 * Env:     CONDUCTOR_SERVER_URL (+ CONDUCTOR_AUTH_KEY/SECRET if required). The TS SDK still reads
 *          CONDUCTOR_SERVER_URL / CONDUCTOR_AUTH_KEY / CONDUCTOR_AUTH_SECRET env (SDK 4.x); tunables via the AgentRuntime options object.
 *
 * Execution model: COMPILED -- LLM turns run on the server (OPENAI_API_KEY on the server). Any
 * function tools become worker tasks that need runtime.serve(agent).
 */
import { Agent, setTracingDisabled } from "@openai/agents";
import { AgentRuntime } from "@io-orkes/conductor-javascript/agents";

setTracingDisabled(true);
const agent = new Agent({
  name: "openai_greeter",
  model: "gpt-4o-mini",
  instructions: "You are friendly and concise.",
});

const runtime = new AgentRuntime();
try {
  const result = await runtime.run(agent, "Share a durable execution fact.");
  result.printResult();
} finally {
  await runtime.shutdown();
}
