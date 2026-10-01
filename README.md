# rclone-mcp

Dependency-light [Model Context Protocol](https://modelcontextprotocol.io/) server exposing [rclone](https://rclone.org/) to Claude Desktop, Claude Code, Cursor, Cline, Windsurf, VS Code and other LLM clients through the standard JSON-RPC `stdio` transport.

The server delegates storage operations to the installed `rclone` binary. It does not contain cloud-provider SDKs and does not require an HTTP daemon.

## Features

- Standard MCP `initialize`, `ping`, `tools/list` and `tools/call` methods.
- Read-only, read-write and full security modes.
- File listing, metadata, text reading, upload, download, copy, move, sync and deletion.
- Cross-remote duplicate detection using hashes with a size fallback.
- Provider-aware `rclone.conf` management through `config_providers`, `config_create`, `config_update`, `config_continue` and `config_interactive`.
- Redacted configuration inspection; credentials are not intentionally returned by `config_show`.
- No mandatory runtime dependency beyond Python and rclone.
- Local upload/download paths restricted to a configurable directory.

## Requirements

- Python 3.10 or newer.
- rclone installed and available in `PATH`.
- An rclone configuration with at least one remote, unless you are creating a new configuration through the config tools.

Check the prerequisites:

```bash
# Verify the Python and rclone versions.
python3 --version
rclone version
```

## Installation

Clone or extract the repository, then install it in a virtual environment:

```bash
# Create an isolated Python environment.
python3 -m venv .venv

# Activate the environment for the current shell.
. .venv/bin/activate

# Install the MCP server in editable mode.
python -m pip install -e .

# Verify the command is available.
rclone-mcp --version
```

The executable used by an LLM client must be an **absolute path**, for example:

```text
/home/username/rclone-mcp/.venv/bin/rclone-mcp
```

Do not use a shell activation command in an MCP configuration. MCP clients start the command directly and do not load your interactive shell profile reliably.

## Recommended first configuration

Use a dedicated rclone configuration file when granting an LLM access. This prevents accidental use of a personal default configuration and makes access easy to revoke.

```bash
# Create a private directory for the dedicated configuration and local transfer area.
mkdir -p "$HOME/.config/rclone-mcp" "$HOME/.local/share/rclone-mcp"

# Create or edit the dedicated rclone configuration interactively.
RCLONE_CONFIG="$HOME/.config/rclone-mcp/rclone.conf" rclone config

# Protect the configuration file from other local users.
chmod 600 "$HOME/.config/rclone-mcp/rclone.conf"
```

Start with read-only access and an explicit remote allow-list:

```text
RCLONE_MCP_MODE=readonly
RCLONE_MCP_ALLOWED_REMOTES=gdrive,backup
RCLONE_CONFIG=/home/username/.config/rclone-mcp/rclone.conf
RCLONE_MCP_LOCAL_ROOT=/home/username/.local/share/rclone-mcp
```

`RCLONE_MCP_ALLOWED_REMOTES` contains remote names without the trailing colon. If it is set, every remote operation outside the list is rejected.

## Security modes

| Mode | Permitted operations |
|---|---|
| `readonly` (default) | Listing, metadata, reading, searching, checking, duplicate scans and provider discovery |
| `readwrite` | Read-only operations plus upload, download, mkdir, copy, move, links and config create/update |
| `full` | Read-write operations plus sync, delete, purge, dedupe and deletion of remote definitions |

Destructive file tools default to `dry_run=true`. `config_delete` and `config_password` additionally require `confirm=true`.

Recommended escalation:

1. Start with `readonly`.
2. Preview the intended operation.
3. Switch to `readwrite` only for a planned transfer or config update.
4. Switch to `full` only for a planned deletion or synchronization.
5. Return to `readonly` afterwards.

Never put clear-text credentials in an MCP JSON file, a prompt, a README, an issue or a log. Use rclone's config storage and provider authentication flow instead.

## Common environment variables

| Variable | Meaning | Default |
|---|---|---|
| `RCLONE_CONFIG` | Dedicated rclone config path | rclone default |
| `RCLONE_MCP_MODE` | `readonly`, `readwrite` or `full` | `readonly` |
| `RCLONE_MCP_ALLOWED_REMOTES` | Comma-separated remote allow-list | all configured remotes |
| `RCLONE_MCP_LOCAL_ROOT` | Root for relative and local transfer paths | `/tmp/rclone-mcp` |
| `RCLONE_MCP_TIMEOUT` | Maximum rclone command duration in seconds | `300` |
| `RCLONE_MCP_MAX_OUTPUT` | Maximum captured command output | `2000000` |
| `RCLONE_MCP_MAX_SCAN_FILES` | Maximum files scanned by duplicate search | `100000` |
| `RCLONE_MCP_RCLONE` | Alternative rclone executable path | `rclone` |

## MCP client configuration

All examples below use the same generic server definition. Replace every `/home/username/...` path with the real absolute path on the target machine.

### Generic `mcpServers` configuration

This format is used by many clients, including Claude Desktop, Cursor, Cline, Windsurf and several MCP-compatible applications:

```json
{
  "mcpServers": {
    "rclone": {
      "command": "/home/username/rclone-mcp/.venv/bin/rclone-mcp",
      "args": [],
      "env": {
        "RCLONE_CONFIG": "/home/username/.config/rclone-mcp/rclone.conf",
        "RCLONE_MCP_MODE": "readonly",
        "RCLONE_MCP_ALLOWED_REMOTES": "gdrive,backup",
        "RCLONE_MCP_LOCAL_ROOT": "/home/username/.local/share/rclone-mcp",
        "RCLONE_MCP_TIMEOUT": "300"
      }
    }
  }
}
```

Do not add `RCLONE_CONFIG` to the JSON if you intentionally want to use rclone's default config. A dedicated file is safer for LLM access.

### Claude Desktop

1. Install the server as described above.
2. Open Claude Desktop's configuration file:
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\\Claude\\claude_desktop_config.json`
   - Linux: `~/.config/Claude/claude_desktop_config.json`
3. Add the `rclone` entry under `mcpServers`.
4. Save the file and completely restart Claude Desktop.
5. Ask Claude to call `list_remotes` before attempting any write operation.

Minimal read-only example:

```json
{
  "mcpServers": {
    "rclone": {
      "command": "/home/username/rclone-mcp/.venv/bin/rclone-mcp",
      "env": {
        "RCLONE_CONFIG": "/home/username/.config/rclone-mcp/rclone.conf",
        "RCLONE_MCP_MODE": "readonly",
        "RCLONE_MCP_ALLOWED_REMOTES": "gdrive"
      }
    }
  }
}
```

On Windows, use escaped backslashes or forward slashes:

```json
{
  "mcpServers": {
    "rclone": {
      "command": "C:/Users/Jonas/rclone-mcp/.venv/Scripts/rclone-mcp.exe",
      "env": {
        "RCLONE_CONFIG": "C:/Users/Jonas/.config/rclone-mcp/rclone.conf",
        "RCLONE_MCP_MODE": "readonly",
        "RCLONE_MCP_ALLOWED_REMOTES": "gdrive"
      }
    }
  }
}
```

### Claude Code

Claude Code can use the same stdio server. If the installed version supports MCP registration from the command line, register the executable and environment variables through its MCP command. Otherwise add the generic `mcpServers` object to the Claude Code configuration file used by your installation.

A direct smoke test is useful before registering it:

```bash
# Send a minimal MCP initialize request to the server.
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  | /home/username/rclone-mcp/.venv/bin/rclone-mcp
```

### Cursor

Put the generic JSON in `.cursor/mcp.json` for a project or in Cursor's global MCP configuration. Restart Cursor after saving. Cursor must be able to execute the absolute `command` path without shell activation.

### Cline

Open Cline's MCP settings and add the same `mcpServers.rclone` object. Keep `RCLONE_MCP_MODE` at `readonly` until the server and remote allow-list have been verified.

### Windsurf

Add the same `mcpServers` entry to Windsurf's MCP configuration file and restart the application. The configuration is still a local stdio process, so the machine running Windsurf must have both Python environment and rclone available.

### VS Code and other clients

Recent VS Code MCP configurations commonly use a `servers` object instead of `mcpServers`:

```json
{
  "servers": {
    "rclone": {
      "type": "stdio",
      "command": "/home/username/rclone-mcp/.venv/bin/rclone-mcp",
      "args": [],
      "env": {
        "RCLONE_CONFIG": "/home/username/.config/rclone-mcp/rclone.conf",
        "RCLONE_MCP_MODE": "readonly",
        "RCLONE_MCP_ALLOWED_REMOTES": "gdrive,backup"
      }
    }
  }
}
```

Other MCP-compatible LLMs usually expose the same three fields: executable command, arguments and environment. If the client supports only remote HTTP MCP servers and not local stdio servers, this project cannot be attached directly without an additional stdio-to-HTTP bridge.

## Useful prompts for an LLM

Start with harmless discovery:

```text
Use rclone-mcp in read-only mode. List the configured remotes and show the top-level files in gdrive:Documents. Do not modify anything.
```

Find duplicates without deleting them:

```text
Scan gdrive:Photos and backup:Photos for duplicate files. Use find_duplicates with a bounded scan, show every duplicate group, and do not delete or move anything.
```

Preview a synchronization:

```text
Compare gdrive:Documents with backup:Documents. First run check, then run sync with dry_run=true. Explain which destination-only files would be deleted. Do not perform the real sync.
```

Create a provider configuration:

```text
Use config_providers to inspect the provider schema for S3. Ask me for any required values, never invent credentials, then create the remote non-interactively. Do not reveal secret values in your summary.
```

Read a text file:

```text
Read gdrive:Reports/status.md with read_file, limited to 200000 bytes, and summarize it. Do not download or modify the file.
```

## Tool reference

### Discovery and validation

`rclone_version`, `list_remotes`, `list_files`, `stat`, `read_file`, `search`, `check`, and `find_duplicates` are available in `readonly` mode.

### Transfers

`download`, `upload`, `mkdir`, `copy`, `move` require `readwrite`. Prefer `copy` when the source should remain unchanged. Use `move` only when source deletion is intended.

### Destructive operations

`sync`, `delete`, `purge` and `dedupe` require `full`. Always run the corresponding dry-run first. `purge` removes a complete path and is more destructive than `delete`.

### rclone.conf management

- `config_file` reports the active config path.
- `config_show` returns redacted config data.
- `config_providers` returns provider schemas.
- `config_create` and `config_update` use rclone's non-interactive provider handling.
- `config_continue` continues a provider question/state flow.
- `config_interactive` accepts explicit `input_lines`; it never consumes MCP protocol stdin.
- `config_delete` requires `full` and `confirm=true`.

## Troubleshooting

### The client says the server cannot start

- Confirm the `command` is an absolute path.
- Run `rclone-mcp --version` as the same OS user as the LLM client.
- Check that the virtual environment still exists.
- Check that `RCLONE_CONFIG` points to an existing readable file.
- Use the MCP initialize smoke test shown above.

### No remotes are visible

- Call `config_file` to see which config rclone is using.
- Verify `RCLONE_CONFIG` is set in the client configuration, not only in your interactive shell.
- Check that the file is readable by the client user.
- Call `config_show` to inspect the redacted sections.

### An operation is rejected

- Check the configured `RCLONE_MCP_MODE`.
- Check `RCLONE_MCP_ALLOWED_REMOTES` spelling and omit trailing colons.
- For local transfers, keep paths below `RCLONE_MCP_LOCAL_ROOT`.
- For destructive config operations, supply the required explicit confirmation.

### OAuth or provider setup needs another question

Use `config_providers` to understand the provider, then call `config_create` or `config_update` with `non_interactive=true`. If the response contains rclone's `State` and `Option`, ask the user for the answer and continue with `config_continue`. Never guess OAuth, tenant, scope or credential values.

## Development and tests

Run the dependency-free test suite:

```bash
# Run syntax checks and all unit tests.
python3 -m py_compile src/rclone_mcp/*.py tests/*.py
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The tests use a fake rclone executable and do not access cloud accounts.

## Sources

- [Official rclone documentation](https://rclone.org/docs/)
- [Official rclone config command](https://rclone.org/commands/rclone_config/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [rclone-mcp repository](https://github.com/PhateValleyman/rclone-mcp)

## License

MIT
