# rclone-mcp

Dependency-light MCP server exposing `rclone` to LLM clients through the standard JSON-RPC `stdio` transport.

## Why this design

- No mandatory third-party runtime dependency: works with clients that launch an MCP command directly.
- Implements `initialize`, `ping`, `tools/list`, and `tools/call`.
- JSON Schema tool definitions, deterministic JSON results, and useful error messages.
- Every filesystem operation is delegated to rclone; no cloud SDK lock-in.
- Destructive operations are policy-gated by an environment mode.

## Install

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

The `rclone` executable must be available in `PATH`.

## Security modes

| Mode | Allowed operations |
|---|---|
| `readonly` (default) | listing, metadata, reading, search, check, duplicate scan |
| `readwrite` | readonly + upload, download, mkdir, copy, move, links |
| `full` | readwrite + sync, delete, purge, dedupe |

Destructive tools default to `dry_run=true` even in `full` mode. Set `dry_run=false` only when the caller explicitly intends the operation.

Useful environment variables:

```bash
export RCLONE_MCP_MODE=readonly
export RCLONE_MCP_ALLOWED_REMOTES=gdrive,backup
export RCLONE_MCP_LOCAL_ROOT=/tmp/rclone-mcp
export RCLONE_MCP_TIMEOUT=300
export RCLONE_MCP_MAX_SCAN_FILES=100000
# Optional: use a dedicated configuration file
export RCLONE_CONFIG=/path/to/rclone.conf
```

Remote names are allow-listed when `RCLONE_MCP_ALLOWED_REMOTES` is set. Local upload/download paths are restricted to `RCLONE_MCP_LOCAL_ROOT`.

## MCP client configuration

Generic configuration:

```json
{
  "mcpServers": {
    "rclone": {
      "command": "/absolute/path/to/.venv/bin/rclone-mcp",
      "env": {
        "RCLONE_MCP_MODE": "readonly",
        "RCLONE_MCP_ALLOWED_REMOTES": "gdrive,backup",
        "RCLONE_CONFIG": "/absolute/path/to/rclone.conf"
      }
    }
  }
}
```

For write access, change only the mode intentionally. Never put credentials in this JSON; use a file protected by the operating system or rclone's normal credential mechanisms.

## Tools

`rclone_version`, `list_remotes`, `list_files`, `stat`, `read_file`, `download`, `upload`, `mkdir`, `copy`, `move`, `sync`, `delete`, `purge`, `create_link`, `search`, `check`, `find_duplicates`, and `dedupe`.

`find_duplicates` scans one or more remotes using rclone's reported hashes, with a size fallback when no hash exists. It returns duplicate groups with remote, path, size, and hash. For large stores use `max_files_per_remote` and `max_groups`.

## Manual smoke test

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | rclone-mcp
printf '%s\n' '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | rclone-mcp
```

## License

MIT
