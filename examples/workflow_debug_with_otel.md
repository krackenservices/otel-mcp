Description:
How to use otel-mcp for debugging and performance analysis of myapp

```
# Debugging and Performance Analysis with OTEL

This workflow describes how to use the `otel-mcp` toolset to debug errors and analyze performance in the `myapp` application.

## Prerequisites

1.  **Instrumentation**: The application code must be instrumented with OpenTelemetry.
    - Example: `tracing.StartSpan(ctx, "operation.name", ...)`
2.  **Environment**: When running `myapp` manually (e.g., via `run_command`), ensure the OTLP exporter is configured:
    ```bash
    export OTEL_EXPORTER_OTLP_ENDPOINT=localhost:4317
    ./bin/myapp <command> ...
    ```

## Debugging Errors

To find and diagnose application errors:

1.  **Find Errors**:
    Use `mcp_otel-mcp_find_errors` to identify operations with failures.
    ```json
    {
      "service_name": "myapp",
      "limit": 10
    }
    ```

2.  **Search Specific Traces**:
    If you know the operation or time range, use `mcp_otel-mcp_search_traces` with `has_error: true`.
    ```json
    {
      "service_name": "myapp",
      "operation_name": "library.Export",
      "has_error": true
    }
    ```

3.  **Inspect Trace**:
    Get full details of a suspicious trace using its ID.
    ```json
    {
      "trace_id": "<trace_id>"
    }
    ```
    Look at `events` or `status` code and `error_message` in the spans.

## Performance Analysis

To analyze latency and bottlenecks:

1.  **Overview Statistics**:
    Get aggregated metrics (p50, p95, p99 latency) for an operation.
    ```json
    {
      "service_name": "myapp",
      "operation_name": "library.Export"
    }
    ```

2.  **Find Slow Traces**:
    Identify the slowest executions to target optimization.
    ```json
    {
      "service_name": "myapp",
      "operation_name": "library.Export",
      "min_duration_ms": 1000
    }
    ```

3.  **Analyze Waterfall**:
    Retrieve a slow trace and examine the `spans` to see which child operation took the most time.
    ```json
    {
      "trace_id": "<trace_id>"
    }
    ```
    Compare `duration_ms` of parent vs. children to find gaps or expensive processing.

## Verification Example

To verify instrumentation is working:

1.  Run a command: `OTEL_EXPORTER_OTLP_ENDPOINT=localhost:4317 ./bin/myapp export nes stats json`
2.  Search traces: `mcp_otel-mcp_search_traces(service_name="myapp", operation_name="library.Export", limit=1)`
3.  Verify attributes: Check for `library.name`, `report.type`, etc.
4.  **Verify Hierarchy**: Ensure SQL spans (`sql.conn.query`, `sql.rows`) are children of the operation span (e.g., `export.getMatched`), NOT the root `library.Export` span.

## Instrumented Operations

| Operation | Span Name | Key Attributes |
|-----------|-----------|----------------|
| Import | `f.Import` | `f.path`, `system.name`, `result.*` |
| System Resolution | `f.getOrCreateSystem` | `system.name` |
| Library Scan | `scan: <name>` | `library.name`, `system.name` |
| Export | `library.Export` | `library.name`, `report.type`, `result.count` |
| Export Matched | `export.getMatched` | (child span) |
| Export Missing | `export.getMissing` | (child span) |
| File Rename | `library.Rename` | `library.name`, `dry_run`, `result.*` |
| Find Duplicates | `library.FindDuplicates` | `library.id`, `result.*_count` |
| Cleanup Plan | `library.CleanupPlan` | `library.name`, `result.*` |
| Preference Selection | `library.SelectPreferred` | `system.id`, `result.*` |
```
