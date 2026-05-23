# Writing Conductor Workers

Workers execute SIMPLE tasks in a workflow. They poll the Conductor server for tasks, execute business logic, and report results back. Workers are stateless and idempotent.

## Before you scaffold — check the built-ins first

Most "I need a worker for X" requests are actually built-in tasks. Walk SKILL.md Rule 6's table before writing any worker code — if a built-in matches (LLM call, Kafka publish, PDF render, vector index/search, sub-workflow trigger, wait, human approval, JQ transform, fork/join, etc.), use it. A custom worker is the right answer only when no built-in covers the operation (e.g. an internal API, a proprietary system, business logic that doesn't fit a generic task).

## Scaffolding flow (SKILL.md Rule 7)

1. **Confirm no built-in fits.** Name the closest candidate and why it doesn't work.
2. **Ask the language.** Supported officially: Java, Go, Python, TypeScript/JavaScript, .NET (C#), Rust, Ruby. Don't assume — defaults shift across teams.
3. **WebFetch the SDK repo README** (table below) before writing code. The SDKs evolve fast — annotations, runner classes, package paths, and entry points have changed across major versions. Pin the version and install command from what the README currently says, not from memory.
4. **Scaffold from the pattern below**, match the worker's task type to the SIMPLE task's `name` exactly, and include the idempotency note.

## How workers work

1. Workflow reaches a SIMPLE task
2. Task is placed in a queue
3. Worker polls the queue, picks up the task
4. Worker executes logic using task's `inputData`
5. Worker returns result (COMPLETED or FAILED) with `outputData`
6. Workflow continues to the next task

## SDKs — canonical repos (WebFetch these before scaffolding)

All official SDKs live under the `conductor-oss` GitHub org with the `*-sdk` naming convention:

| Language | Repo (WebFetch the README) | Package / Install |
|----------|----------------------------|-------------------|
| Python | [github.com/conductor-oss/python-sdk](https://github.com/conductor-oss/python-sdk) | PyPI: `conductor-python` — `pip install conductor-python` |
| JavaScript / TypeScript | [github.com/conductor-oss/javascript-sdk](https://github.com/conductor-oss/javascript-sdk) | npm: `@io-orkes/conductor-javascript` — `npm install @io-orkes/conductor-javascript` |
| Java | [github.com/conductor-oss/java-sdk](https://github.com/conductor-oss/java-sdk) | Maven: `org.conductoross:conductor-client` (and `conductor-client-spring` for Spring Boot) |
| Go | [github.com/conductor-oss/go-sdk](https://github.com/conductor-oss/go-sdk) | Go module path: `go get github.com/conductor-sdk/conductor-go` (the source repo is at `conductor-oss/go-sdk` but the Go import path retains the historical `conductor-sdk/conductor-go` name) |
| .NET (C#) | [github.com/conductor-oss/csharp-sdk](https://github.com/conductor-oss/csharp-sdk) | NuGet: `conductor-csharp` — `dotnet add package conductor-csharp` |
| Ruby | [github.com/conductor-oss/ruby-sdk](https://github.com/conductor-oss/ruby-sdk) | Gem: `conductor_ruby` (early version — confirm patterns from the repo) |
| Rust | [github.com/conductor-oss/rust-sdk](https://github.com/conductor-oss/rust-sdk) | crates.io: `conductor-rust` (early version — confirm patterns from the repo) |

All SDKs connect via the same env vars: `CONDUCTOR_SERVER_URL`, `CONDUCTOR_AUTH_KEY`, `CONDUCTOR_AUTH_SECRET`.

> **Why the WebFetch step matters.** The Python/JS/Java/Go patterns below are stable across recent versions but the API surface still drifts (e.g. Python switched runner classes; Java's `@WorkerTask` annotation gained options; Go module path moved org without changing the import). The .NET / Ruby / Rust SDKs are younger and their APIs shift more — fetch the README before scaffolding rather than trust an example below.

---

## Python

```bash
pip install conductor-python
```

### Define a worker

```python
from conductor.client.worker.worker_task import worker_task

@worker_task(task_definition_name='process_order')
def process_order(order_id: str, amount: float) -> dict:
    # Your business logic here
    return {'status': 'processed', 'order_id': order_id, 'total': amount * 1.1}
```

Function parameters are automatically mapped from the task's `inputParameters`. The return value becomes the task's `outputData`.

### Start workers

```python
from conductor.client.automator.task_handler import TaskHandler
from conductor.client.configuration.configuration import Configuration

config = Configuration()  # reads CONDUCTOR_SERVER_URL, CONDUCTOR_AUTH_KEY, CONDUCTOR_AUTH_SECRET
with TaskHandler(configuration=config, scan_for_annotated_workers=True) as handler:
    handler.start_processes()
    # Workers poll until stopped
```

---

## JavaScript / TypeScript

```bash
npm install @io-orkes/conductor-javascript
```

### Define and run a worker

```typescript
import {
  orkesConductorClient,
  TaskManager,
} from "@io-orkes/conductor-javascript";

const client = await orkesConductorClient({
  serverUrl: "http://localhost:8080/api",
});

const taskManager = new TaskManager(client, [
  {
    taskType: "process_order",
    execute: async ({ inputData }) => {
      return {
        status: "COMPLETED",
        outputData: {
          status: "processed",
          order_id: inputData.order_id,
        },
      };
    },
  },
]);

taskManager.startPolling();
```

---

## Java

**Gradle:**
```gradle
implementation 'org.conductoross:conductor-client:5.0.0'
```

**Maven:**
```xml
<dependency>
    <groupId>org.conductoross</groupId>
    <artifactId>conductor-client</artifactId>
    <version>5.0.0</version>
</dependency>
```

### Option A: Implement Worker interface

```java
public class ProcessOrderWorker implements Worker {
    @Override
    public String getTaskDefName() {
        return "process_order";
    }

    @Override
    public TaskResult execute(Task task) {
        String orderId = (String) task.getInputData().get("order_id");
        TaskResult result = new TaskResult(task);
        result.setStatus(TaskResult.Status.COMPLETED);
        result.addOutputData("status", "processed");
        result.addOutputData("order_id", orderId);
        return result;
    }
}
```

### Option B: @WorkerTask annotation

```java
public class Workers {
    @WorkerTask("process_order")
    public Map<String, Object> processOrder(@InputParam("order_id") String orderId) {
        return Map.of("status", "processed", "order_id", orderId);
    }
}
```

### Start workers

```java
ConductorClient client = ConductorClient.builder()
    .basePath("http://localhost:8080/api")
    .build();

TaskClient taskClient = new TaskClient(client);
new TaskRunnerConfigurer.Builder(taskClient, List.of(new ProcessOrderWorker()))
    .withThreadCount(10)
    .build()
    .init();
```

---

## Go

```bash
go get github.com/conductor-sdk/conductor-go
```

### Define and run a worker

```go
package main

import (
    "fmt"
    "time"
    "github.com/conductor-sdk/conductor-go/sdk/client"
    "github.com/conductor-sdk/conductor-go/sdk/model"
    "github.com/conductor-sdk/conductor-go/sdk/worker"
)

func ProcessOrder(task *model.Task) (interface{}, error) {
    orderId := fmt.Sprintf("%v", task.InputData["order_id"])
    return map[string]interface{}{
        "status":   "processed",
        "order_id": orderId,
    }, nil
}

func main() {
    apiClient := client.NewAPIClientFromEnv()
    taskRunner := worker.NewTaskRunnerWithApiClient(apiClient)
    taskRunner.StartWorker("process_order", ProcessOrder, 1, time.Millisecond*100)
    // Blocks and polls until stopped
    select {}
}
```

---

## Linking workers to workflows

In your workflow definition, use `"type": "SIMPLE"` and set `"name"` to the task type your worker polls for:

```json
{
  "name": "process_order",
  "taskReferenceName": "process_order_ref",
  "type": "SIMPLE",
  "inputParameters": {
    "order_id": "${workflow.input.order_id}",
    "amount": "${workflow.input.amount}"
  }
}
```

The worker registered for task type `process_order` will automatically pick up this task when the workflow reaches it.

## Best practices

- **Idempotent**: Workers may receive the same task on retry. Design for safe re-execution.
- **Timeouts**: Set `responseTimeoutSeconds` on task definitions so stuck tasks get rescheduled.
- **Error handling**: Return `FAILED` status with a `reasonForIncompletion` message for graceful failures. Return `FAILED_WITH_TERMINAL_ERROR` to fail the task without retrying.
- **Scaling**: Run multiple worker instances for throughput. Each polls independently.
- **Domain isolation**: Use task domains to route tasks to specific worker groups (e.g. region-specific workers).
