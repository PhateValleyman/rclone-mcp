---
name: rclone-mcp
description: Use for storage operations, provider setup, or mounted filesystems through the rclone-mcp MCP server, across every backend supported by the installed rclone version.
---

# rclone-mcp

Operate configured rclone remotes through the `rclone-mcp` MCP tools. Use MCP rather than shell commands when available: the server applies access modes, remote allow-lists, local path boundaries, command timeouts, and dry-run defaults.

## Backend coverage

The available backends are the providers supported by the **installed rclone version**, not a fixed list in this skill. Start provider setup with `config_providers`; it returns the authoritative provider names and option schemas for this installation. Provider availability, authentication requirements, and feature support vary by rclone version and backend.

Examples of backend families include local filesystems; object stores and cloud drives; SFTP, FTP, SMB, WebDAV, and HTTP; and rclone's virtual or cryptographic backends such as alias, crypt, and union. Treat these as examples, not a complete or guaranteed list. Never invent provider names, option names, credentials, OAuth answers, or backend capabilities.

For a new backend:

1. Call `config_providers` and select the exact provider type and options from its result.
2. Ask the user for missing configuration and authentication values; never guess secrets or OAuth choices.
3. Use `config_create` or `config_update` with `non_interactive=true`. If rclone returns a state/question, present it to the user and continue with `config_continue`.
4. Verify the result with `config_show` (redacted) and `list_remotes`, then test access with a read-only operation.
5. Confirm backend-specific support before using links, checksums, mounts, or destructive operations. For example, `create_link` only works on backends that implement it, and mounts require a usable FUSE setup on the host.

## Safety

- Treat `rclone.conf` and all provider credentials as sensitive. Never reveal or repeat clear-text tokens, passwords, OAuth data, or service-account keys. `config_show` uses rclone's redacted output.
- Keep `RCLONE_MCP_MODE=readonly` by default. Use `readwrite` only for intentional transfers, configuration changes, or managed mounts. Use `full` only when an explicitly planned destructive action is necessary.
- `sync` makes the destination match the source and can delete destination-only files. `move` removes source data after transfer. `purge` removes a path and its contents. Preview destructive actions with `dry_run=true`, inspect the output, and only execute for real after explicit user approval.
- `delete`, `purge`, `sync`, and `dedupe` require `full`; `config_delete` also requires `full` and `confirm=true`. `config_password` requires `readwrite` and `confirm=true`.
- Do not pass unrestricted local paths. Upload, download, and mount paths must remain below `RCLONE_MCP_LOCAL_ROOT`.
- `RCLONE_MCP_ALLOWED_REMOTES`, when configured, restricts remote file operations to the listed remote names (without trailing colons).
- Use a dedicated `RCLONE_CONFIG` file with restrictive permissions when granting an LLM access. Do not put credentials in prompts, client configuration, shell command arguments, or logs.

## Recommended workflow

1. Call `rclone_version`, `config_file`, and `list_remotes` to check the server, active configuration, and available remotes.
2. Discover content with `list_files`, `stat`, `search`, or `read_file`. Keep recursive queries scoped and bounded.
3. Before copying or moving data, use `check` where appropriate. Prefer `copy` when the source must remain unchanged.
4. For duplicate analysis, use `find_duplicates` with bounded `max_files_per_remote` and `max_groups`. Review every group before any cleanup.
5. After a write, verify with `stat`, `list_files`, or `check`.

## Tool reference

| Purpose | Tools | Access |
|---|---|---|
| Version, remotes, configuration discovery | `rclone_version`, `list_remotes`, `config_file`, `config_show`, `config_providers` | `readonly` |
| Browse and inspect | `list_files`, `stat`, `search`, `read_file` | `readonly` |
| Compare and analyze | `check`, `find_duplicates` | `readonly` |
| Transfer and create directories | `download`, `upload`, `mkdir`, `copy`, `move`, `create_link` | `readwrite` |
| Configure providers | `config_create`, `config_update`, `config_unset`, `config_reconnect`, `config_continue`, `config_interactive`, `config_password` | `readwrite` |
| Synchronize or remove data/config | `sync`, `delete`, `purge`, `dedupe`, `config_delete` | `full` |
| Manage mounts | `mount_start`, `mount_stop`, `mount_list` | `readwrite` |

Notes:

- `read_file` is for UTF-8 text, not arbitrary binary data.
- `config_interactive` requires explicit `input_lines`; MCP protocol input is not an interactive terminal.
- `dedupe` supports only non-interactive strategies. Review its dry-run output before applying any changes.
- `config_delete` and `config_password` require explicit `confirm=true`.
- `mount_start` creates a foreground managed mount below the local root. Prefer `read_only=true`; `allow_other` is opt-in and requires host-level FUSE configuration.
- Mount cache and link behavior are backend- and host-dependent. Do not treat a successful request as proof that the mounted filesystem or generated link is usable; verify it.

## Shell fallback

Use the installed `rclone` CLI only when the MCP server is unavailable. Keep credentials out of command arguments and logs, and preview any destructive operation:

```bash
# Preview a synchronization before allowing destination deletions.
rclone sync --dry-run source:path destination:path

# Compare two paths after a transfer.
rclone check source:path destination:path
```

## Sources

- [Official rclone documentation](https://rclone.org/docs/)
- [Official rclone backend overview](https://rclone.org/overview/)
- [Official rclone config command](https://rclone.org/commands/rclone_config/)
- [rclone-mcp project](https://github.com/PhateValleyman/rclone-mcp)
