/**
 * LangGraph graph on Conductor (verbatim from the server UI quickstart).
 *
 * Install: npm install @io-orkes/conductor-javascript @langchain/langgraph @langchain/openai @langchain/core
 *          (pin from the SDK README you fetched)
 * Env:     CONDUCTOR_SERVER_URL (+ CONDUCTOR_AUTH_KEY/SECRET if required). The TS SDK still reads
 *          CONDUCTOR_SERVER_URL / CONDUCTOR_AUTH_KEY / CONDUCTOR_AUTH_SECRET env (SDK 4.x); tunables via the AgentRuntime options object.
 *
 * The runtime introspects the graph for its model and tools and COMPILES it into a Conductor graph.
 * If introspection is ambiguous, build the graph with `createReactAgent` from
 * "@io-orkes/conductor-javascript/agents/langgraph" instead; that wrapper records the metadata the
 * server needs. When the model cannot be derived from the LLM object, pass a `{ model: "openai/gpt-4o-mini" }`
 * hint to the wrapper. Graphs the server cannot extract fall back to PASSTHROUGH, where the whole
 * loop runs inside runtime.serve(graph) -- serve() must then be running for the agent to progress.
 */
import { createReactAgent } from "@langchain/langgraph/prebuilt";
import { ChatOpenAI } from "@langchain/openai";
import { AgentRuntime } from "@io-orkes/conductor-javascript/agents";

const graph = createReactAgent({
  llm: new ChatOpenAI({ model: "gpt-4o-mini", temperature: 0 }),
  tools: [],
  name: "langgraph_assistant",
});

const runtime = new AgentRuntime();
try {
  const result = await runtime.run(graph, "What makes execution durable?");
  result.printResult();
} finally {
  await runtime.shutdown();
}
