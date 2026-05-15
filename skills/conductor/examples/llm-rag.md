# Example: RAG — Retrieval-Augmented Generation

Classic RAG pattern: search a vector database for context, then ask an LLM to answer using only that context. Two tasks, one workflow.

## Pipeline

```
LLM_SEARCH_INDEX (vector search) → LLM_CHAT_COMPLETE (answer with context)
```

The search task auto-embeds the user's question, queries the vector DB, and returns the top-k matching chunks. The chat task receives those chunks as system-prompt context and grounds its answer in them.

## Prerequisites

1. **A vector database** registered with Conductor — Pinecone, Postgres pgvector, or MongoDB Atlas. The example uses `postgres-prod` (configured server-side; see your Conductor admin).
2. **Documents already indexed.** Use [`LLM_INDEX_TEXT`](../references/workflow-definition.md#llm_index_text) in a separate ingestion workflow to populate the index.
3. **An LLM provider** with its API key set (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.) — Conductor auto-enables providers when their API key is present.

## Workflow

See [workflows/llm-rag.json](workflows/llm-rag.json):

```json
{
  "name": "rag_qa",
  "tasks": [
    {
      "name": "search_knowledge_base",
      "taskReferenceName": "search",
      "type": "LLM_SEARCH_INDEX",
      "inputParameters": {
        "vectorDB": "postgres-prod",
        "namespace": "kb",
        "index": "articles",
        "embeddingModelProvider": "openai",
        "embeddingModel": "text-embedding-3-small",
        "query": "${workflow.input.question}",
        "llmMaxResults": 3
      }
    },
    {
      "name": "generate_answer",
      "taskReferenceName": "answer",
      "type": "LLM_CHAT_COMPLETE",
      "inputParameters": {
        "llmProvider": "anthropic",
        "model": "claude-sonnet-4-6",
        "messages": [
          {"role": "system", "message": "Answer using only the context below. If the answer isn't in the context, say \"I don't know.\"\n\nContext:\n${search.output.result}"},
          {"role": "user", "message": "${workflow.input.question}"}
        ],
        "temperature": 0.2,
        "maxTokens": 500
      }
    }
  ],
  "outputParameters": {
    "answer": "${answer.output.result}",
    "sources": "${search.output.result}",
    "tokensUsed": "${answer.output.tokenUsed}"
  }
}
```

## Run

```bash
conductor workflow create examples/workflows/llm-rag.json
conductor workflow start -w rag_qa -i '{"question": "How does Conductor handle worker failures?"}' --sync
```

The `--sync` flag waits for both tasks (search + chat) to complete and returns the final answer plus the source chunks for citation.

## Output

- `answer` — the grounded response (string)
- `sources` — the retrieved chunks, with their metadata (use to render citations)
- `tokensUsed` — for cost tracking

## Variant: pre-computed embeddings

If you already have the query embedding (e.g., computed by an upstream worker), use `LLM_SEARCH_EMBEDDINGS` instead — same shape, but takes `embeddings` (a float array) instead of `query` (text). Saves one embedding call per request.

## Patterns

- **System prompt does the grounding.** "Answer only from the context below" is the difference between a real RAG system and a thin wrapper that pretends. State it explicitly. Tell the model what to do when the context doesn't cover the question — "say I don't know" beats hallucination.
- **Low temperature for QA.** `0.2` keeps answers grounded; higher temperatures invent facts.
- **`llmMaxResults` is the recall knob.** 3 chunks → tight answer, low cost. 10 chunks → broader recall, higher token spend, risk of off-topic context diluting the signal.
- **Different providers per task is fine.** Cheap small model for embedding (`text-embedding-3-small`), a strong reasoning model for the answer (`claude-sonnet-4-6`). Each task picks its own provider/model.
- **Return sources.** Always return `${search.output.result}` so the caller can cite or display sources. RAG without sources is just expensive Q&A.

## Ingesting documents (separate workflow)

For the search to find anything, an ingestion workflow needs to populate the index. Sketch:

```json
{
  "name": "ingest_doc",
  "type": "LLM_INDEX_TEXT",
  "inputParameters": {
    "vectorDB": "postgres-prod",
    "namespace": "kb",
    "index": "articles",
    "embeddingModelProvider": "openai",
    "embeddingModel": "text-embedding-3-small",
    "text": "${workflow.input.document}",
    "docId": "${workflow.input.docId}",
    "metadata": {"source": "${workflow.input.source}"}
  }
}
```

Run this once per document. The embedding model **must** match the one used at query time in `rag_qa` — different models produce incompatible vector spaces.
