# Connected Apps

Use the selected cluster and profile. If the CLI lacks `integration`, use the bundled Python helper with the same profile. A 403 means access was denied. An empty filtered list means no matching visible entries.

| Intent | CLI | Python helper subcommand |
|---|---|---|
| Which apps are installed? | `integration types --category MCP` | `integration-defs --category MCP` (use enabled definitions) |
| Does this provider support an operation? | `integration operations --type aws-s3` | `integration-operations --type aws-s3` |
| Which saved connections match? | `integration list --type aws-s3` | `integration-list --type aws-s3` |
| Which inputs are required? | `integration operations test-s3 --name "List Buckets"` | `integration-operations --connection test-s3 --name "List Buckets"` |
| What credentials does setup require? | `integration type-config aws-s3` | `integration-defs --category MCP` then select the matching type's configuration |

For a capability question, inspect the type before asking for credentials. For execution, select an enabled saved connection, asking the user which one if several match. Use the exact operation name and its live `inputSchema.data`. Discovery shows advertised operations. Execution also depends on integration EXECUTE access, the connection's auth mode and upstream permissions.

For example, after confirming the connection, operation and region, build a task like this and use the existing workflow registration and execution instructions:

```json
{"name":"List Buckets","taskReferenceName":"list_buckets","type":"INTEGRATION","inputParameters":{"integrationName":"test-s3","integrationType":"aws-s3","method":"List Buckets","region":"us-east-2"}}
```

## Setting up a connection

1. Discover the provider, advertised operations, and existing enabled connections. If matches exist, give their names and ask **which one to reuse, or whether to create a new connection**. End this turn with that choice and wait for the answer. Reuse requires no configuration change.
2. If the user chooses new, inspect the live type configuration. Ask for a unique connection name and **which advertised auth mode to use** unless already specified. Collect only connection fields from type-config. Operation inputs such as the Lambda region belong to a later workflow task. For secrets, arrange a protected local file or environment input. Keep credential values out of chat, command arguments, and workflow inputs.
3. Summarize the proposed name, provider type, auth mode, and non-secret settings. Ask explicitly whether to create this connection and wait for confirmation. Choosing “new” or selecting an auth mode is not confirmation of the final configuration.
4. After confirmation, run `conductor integration create` with the JSON payload on stdin or via a protected file. Include name, type, category, enabled, description, and configuration. Verify the saved name and type with `conductor integration get`. If the CLI lacks integration support, use the bundled `integration-save --category MCP` fallback with secret environment variables.
