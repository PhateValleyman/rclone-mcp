---
name: rclone
description: Use when a task mentions rclone, cloud remotes, remote file operations, duplicate detection, synchronization, or editing rclone.conf through rclone-mcp.
---

# rclone

Use this skill for cloud-storage operations through the `rclone-mcp` MCP server. Prefer MCP tools over shell commands: they enforce remote allow-lists, local path boundaries, timeouts, dry-run defaults, and mode gates.

## Safety

- Treat `rclone.conf` as sensitive. Never expose clear-text tokens, passwords, OAuth data, or service-account keys. Use `config_show`, which returns rclone-redacted output.
- Start in `RCLONE_MCP_MODE=readonly`. Use `readwrite` only for intentional transfers/config updates; use `full` only for deletion, `sync`, `purge`, and `dedupe`.
- Preview destructive work first. Keep `dry_run=true` for `sync`, `delete`, `purge`, and `dedupe`; inspect the result before repeating with `dry_run=false`.
- `sync` makes the destination match the source and can delete destination-only files. `move` deletes the source after transfer. `purge` removes a path and all contents.
- Use `config_delete` and `config_password` only with explicit `confirm=true`. Prefer a dedicated `RCLONE_CONFIG` file and protect it with restrictive filesystem permissions.
- Do not pass unrestricted local paths. Upload/download paths must remain below `RCLONE_MCP_LOCAL_ROOT`.

## MCP workflow

1. Call `rclone_version` and `list_remotes`.
2. For discovery use `list_files`, `stat`, `search`, or `read_file`.
3. Before transfers use `check`; use `copy` when the destination must not be pruned.
4. For duplicate analysis call `find_duplicates` with bounded `max_files_per_remote` and `max_groups`; do not delete from its result without reviewing each group.
5. For configuration call `config_providers` first. Then use `config_create` or `config_update` with `non_interactive=true`. If rclone returns a provider question/state, call `config_continue` with the selected answer. Use `config_interactive` only with explicit `input_lines`.
6. After a write, re-run `stat`, `list_files`, or `check` to verify the result.

## Tool selection

| Intent | MCP tools |
|---|---|
| Inspect | `list_remotes`, `list_files`, `stat`, `search`, `read_file` |
| Transfer | `download`, `upload`, `copy`, `move` |
| Validate | `check`, `find_duplicates` |
| Configure | `config_file`, `config_show`, `config_providers`, `config_create`, `config_update`, `config_unset`, `config_continue`, `config_interactive` |
| Destructive | `sync`, `delete`, `purge`, `dedupe`, `config_delete` |

## Shell fallback

Use the installed `rclone` CLI only when the MCP server is unavailable. Always preview destructive commands and keep credentials out of command arguments and logs.

```bash
# Preview a synchronization before allowing destination deletions.
rclone sync --dry-run source:path destination:path

# Compare two paths after a transfer.
rclone check source:path destination:path
```

## Sources

- [Official rclone documentation](https://rclone.org/docs/)
- [Official rclone config command](https://rclone.org/commands/rclone_config/)
- [Community rclone-cli skill](https://github.com/sickn33/agentic-awesome-skills/blob/main/skills/rclone-cli/SKILL.md)
- [rclone-mcp project](https://github.com/rclone-ui/rclone-mcp)
