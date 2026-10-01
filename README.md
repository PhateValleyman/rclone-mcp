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
| `full` | readwrite + sync, delete, purge, dedupe, remote-definition deletion |

Destructive tools default to `dry_run=true` even in `full` mode. Set `dry_run=false` only when the caller explicitly intends the operation. `config_delete` and `config_password` additionally require `confirm=true`.

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

`rclone_version`, `list_remotes`, `config_file`, `config_show`, `config_providers`, `config_create`, `config_update`, `config_unset`, `config_delete`, `config_password`, `config_reconnect`, `config_interactive`, `config_continue`, `list_files`, `stat`, `read_file`, `download`, `upload`, `mkdir`, `copy`, `move`, `sync`, `delete`, `purge`, `create_link`, `search`, `check`, `find_duplicates`, and `dedupe`.

### Managing `rclone.conf`

Configuration tools call the installed rclone binary rather than parsing or rewriting the INI file themselves. This preserves rclone's provider-specific validation, password obscuring, OAuth flow and config-file locking.

- `config_show` uses `rclone config redacted`; secrets are not returned in clear text.
- `config_providers` exposes the provider schemas from `rclone config providers`, which lets an LLM build a provider-specific form.
- `config_create` and `config_update` accept provider option values and use `--non-interactive` by default. Password fields can be obscured with `obscure=true`.
- `config_continue` supports rclone's JSON state machine for provider questions: call it with the returned `state`, selected `result`, and any defaults.
- `config_interactive` runs the native wizard from a supplied `input_lines` array. It never reads the MCP transport's stdin, so it cannot steal protocol messages or hang waiting for a hidden prompt.
- `config_delete` is available only in `full` mode and requires `confirm=true`.

Configuration changes should use a dedicated `RCLONE_CONFIG` file when possible. Do not put clear-text credentials in client configuration files or logs.

`find_duplicates` scans one or more remotes using rclone's reported hashes, with a size fallback when no hash exists. It returns duplicate groups with remote, path, size, and hash. For large stores use `max_files_per_remote` and `max_groups`.

## Manual smoke test

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | rclone-mcp
printf '%s\n' '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | rclone-mcp
```

## License

MIT
