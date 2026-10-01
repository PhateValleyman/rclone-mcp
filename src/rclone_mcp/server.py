#!/usr/bin/env python3
"""rclone MCP server using the MCP JSON-RPC stdio transport."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

SERVER_NAME = "rclone-mcp"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2024-11-05"


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name, default)))
    except ValueError:
        return default


class PolicyError(ValueError):
    pass


class RcloneMCP:
    def __init__(self) -> None:
        self.rclone = os.environ.get("RCLONE_MCP_RCLONE", "rclone")
        self.mode = os.environ.get("RCLONE_MCP_MODE", "readonly").lower()
        if self.mode not in {"readonly", "readwrite", "full"}:
            raise ValueError("RCLONE_MCP_MODE must be readonly, readwrite, or full")
        allowed = os.environ.get("RCLONE_MCP_ALLOWED_REMOTES", "")
        self.allowed_remotes = {x.strip().rstrip(":") for x in allowed.split(",") if x.strip()}
        self.local_root = Path(os.environ.get("RCLONE_MCP_LOCAL_ROOT", "/tmp/rclone-mcp")).expanduser().resolve()
        self.local_root.mkdir(parents=True, exist_ok=True)
        self.timeout = _env_int("RCLONE_MCP_TIMEOUT", 300)
        self.max_output = _env_int("RCLONE_MCP_MAX_OUTPUT", 2_000_000)
        self.max_scan_files = _env_int("RCLONE_MCP_MAX_SCAN_FILES", 100_000)
        self.config = os.environ.get("RCLONE_CONFIG")

    def _check_remote(self, remote: str) -> str:
        if not isinstance(remote, str) or not remote.strip():
            raise PolicyError("remote is required")
        name = remote.strip().split(":", 1)[0]
        if not name or any(c in name for c in "/\\\n\r\t"):
            raise PolicyError("invalid remote name")
        if self.allowed_remotes and name not in self.allowed_remotes:
            raise PolicyError(f"remote '{name}' is not allowed")
        return name + ":"

    def _remote_path(self, remote: str, path: str = "") -> str:
        prefix = self._check_remote(remote)
        path = str(path or "").replace("\\", "/").lstrip("/")
        if "\x00" in path or any(part == ".." for part in path.split("/")):
            raise PolicyError("remote path cannot contain '..' or NUL")
        return prefix + path

    def _local_path(self, path: str, *, must_exist: bool = False) -> Path:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = self.local_root / candidate
        candidate = candidate.resolve(strict=False)
        try:
            candidate.relative_to(self.local_root)
        except ValueError as exc:
            raise PolicyError(f"local path must stay under {self.local_root}") from exc
        if must_exist and not candidate.exists():
            raise FileNotFoundError(str(candidate))
        return candidate

    def _require(self, level: str) -> None:
        ranks = {"readonly": 0, "readwrite": 1, "full": 2}
        if ranks[self.mode] < ranks[level]:
            raise PolicyError(f"operation requires RCLONE_MCP_MODE={level} (current: {self.mode})")

    def _run(self, args: list[str], *, json_output: bool = False) -> Any:
        command = [self.rclone]
        if self.config:
            command += ["--config", self.config]
        command += args
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=self.timeout, check=False)
        except FileNotFoundError as exc:
            raise RuntimeError(f"rclone executable not found: {self.rclone}") from exc
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"rclone timed out after {self.timeout}s") from exc
        if result.returncode:
            detail = (result.stderr or result.stdout).strip()
            raise RuntimeError(f"rclone exited with {result.returncode}: {detail[-4000:]}")
        output = result.stdout
        if len(output) > self.max_output:
            raise RuntimeError(f"rclone output exceeds {self.max_output} bytes")
        if json_output:
            return json.loads(output or "null")
        return output

    def tools(self) -> list[dict[str, Any]]:
        return [
            self._tool("rclone_version", "Return rclone and server versions.", {}),
            self._tool("list_remotes", "List configured rclone remotes.", {}),
            self._tool("list_files", "List files and directories on a remote.", {"remote": self._str(), "path": self._str(""), "recursive": self._bool(False), "files_only": self._bool(False), "max_depth": self._int(0)}),
            self._tool("stat", "Return metadata for a remote path.", {"remote": self._str(), "path": self._str()}),
            self._tool("read_file", "Read a UTF-8 text file from a remote.", {"remote": self._str(), "path": self._str(), "max_bytes": self._int(1_000_000)}),
            self._tool("download", "Download a remote path into the sandbox local root.", {"remote": self._str(), "path": self._str(), "local_path": self._str()}),
            self._tool("upload", "Upload a local file or directory from the sandbox local root.", {"local_path": self._str(), "remote": self._str(), "path": self._str()}),
            self._tool("mkdir", "Create a remote directory.", {"remote": self._str(), "path": self._str()}),
            self._tool("copy", "Copy files or directories between rclone paths.", {"source_remote": self._str(), "source_path": self._str(""), "destination_remote": self._str(), "destination_path": self._str(""), "immutable": self._bool(False)}),
            self._tool("move", "Move files or directories between rclone paths.", {"source_remote": self._str(), "source_path": self._str(""), "destination_remote": self._str(), "destination_path": self._str(""), "delete_empty_source_dirs": self._bool(False)}),
            self._tool("sync", "Synchronize destination to match source; destructive on destination.", {"source_remote": self._str(), "source_path": self._str(""), "destination_remote": self._str(), "destination_path": self._str(""), "dry_run": self._bool(True), "delete_excluded": self._bool(False)}),
            self._tool("delete", "Delete files matching a remote path.", {"remote": self._str(), "path": self._str(), "dry_run": self._bool(True)}),
            self._tool("purge", "Delete a remote directory and all contents.", {"remote": self._str(), "path": self._str(), "dry_run": self._bool(True)}),
            self._tool("create_link", "Create a public or temporary link when supported by the backend.", {"remote": self._str(), "path": self._str(), "expire": self._str("1d")}),
            self._tool("search", "Search remote paths by name or glob pattern.", {"remote": self._str(), "path": self._str(""), "pattern": self._str(), "max_results": self._int(1000)}),
            self._tool("check", "Compare source and destination for equality.", {"source_remote": self._str(), "source_path": self._str(""), "destination_remote": self._str(), "destination_path": self._str(""), "size_only": self._bool(False)}),
            self._tool("find_duplicates", "Find duplicate files within or across remotes using hashes and size fallback.", {"remotes": self._arr(), "path": self._str(""), "by": self._enum(["hash", "size", "hash_or_size"], "hash_or_size"), "max_files_per_remote": self._int(100000), "max_groups": self._int(1000)}),
            self._tool("dedupe", "Run rclone dedupe interactively in a chosen mode.", {"remote": self._str(), "path": self._str(), "dedupe_mode": self._enum(["interactive", "skip", "first", "newest", "oldest", "largest", "smallest", "rename"], "skip"), "dry_run": self._bool(True)}),
        ]

    @staticmethod
    def _str(default: Any = None) -> dict[str, Any]:
        schema: dict[str, Any] = {"type": "string"}
        if default is not None: schema["default"] = default
        return schema

    @staticmethod
    def _bool(default: bool) -> dict[str, Any]: return {"type": "boolean", "default": default}
    @staticmethod
    def _int(default: int) -> dict[str, Any]: return {"type": "integer", "default": default, "minimum": 1}
    @staticmethod
    def _arr() -> dict[str, Any]: return {"type": "array", "items": {"type": "string", "minLength": 1}}
    @staticmethod
    def _enum(values: list[str], default: str) -> dict[str, Any]: return {"type": "string", "enum": values, "default": default}
    @staticmethod
    def _tool(name: str, description: str, properties: dict[str, Any]) -> dict[str, Any]:
        required = [x for x in properties if "default" not in properties[x]]
        return {"name": name, "description": description, "inputSchema": {"type": "object", "properties": properties, "required": required, "additionalProperties": False}}

    def call(self, name: str, a: dict[str, Any]) -> Any:
        if name == "rclone_version": return {"server": SERVER_VERSION, "rclone": self._run(["version", "--checkers", "1"])}
        if name == "list_remotes": return {"remotes": [x.rstrip(":") for x in self._run(["listremotes"]).splitlines() if x.strip()]}
        if name == "list_files":
            args = ["lsjson", self._remote_path(a["remote"], a.get("path", "")), "--no-modtime"]
            if a.get("recursive"): args.append("--recursive")
            if a.get("files_only"): args.append("--files-only")
            if a.get("max_depth", 0): args += ["--max-depth", str(a["max_depth"])]
            return self._run(args, json_output=True)
        if name == "stat": return self._run(["size", self._remote_path(a["remote"], a["path"]), "--json"], json_output=True)
        if name == "read_file":
            raw = self._run(["cat", self._remote_path(a["remote"], a["path"])])
            data = raw.encode()
            limit = max(1, min(int(a.get("max_bytes", 1_000_000)), self.max_output))
            return {"truncated": len(data) > limit, "text": data[:limit].decode("utf-8", errors="replace"), "bytes": min(len(data), limit)}
        if name == "download":
            self._require("readwrite"); dest = self._local_path(a["local_path"]); dest.parent.mkdir(parents=True, exist_ok=True)
            self._run(["copyto", self._remote_path(a["remote"], a["path"]), str(dest)])
            return {"local_path": str(dest)}
        if name == "upload":
            self._require("readwrite"); src = self._local_path(a["local_path"], must_exist=True)
            self._run(["copyto", str(src), self._remote_path(a["remote"], a["path"])])
            return {"uploaded": str(src)}
        if name == "mkdir": self._require("readwrite"); return self._run(["mkdir", self._remote_path(a["remote"], a["path"])])
        if name in {"copy", "move"}:
            self._require("readwrite")
            source = self._remote_path(a["source_remote"], a.get("source_path", "")); dest = self._remote_path(a["destination_remote"], a.get("destination_path", ""))
            args = [name, source, dest]
            if name == "copy" and a.get("immutable"): args.append("--immutable")
            if name == "move" and a.get("delete_empty_source_dirs"): args.append("--delete-empty-src-dirs")
            return self._run(args)
        if name == "sync":
            self._require("full"); args = ["sync", self._remote_path(a["source_remote"], a.get("source_path", "")), self._remote_path(a["destination_remote"], a.get("destination_path", ""))]
            if a.get("dry_run", True): args.append("--dry-run")
            if a.get("delete_excluded"): args.append("--delete-excluded")
            return self._run(args)
        if name in {"delete", "purge"}:
            self._require("full"); args = [name, self._remote_path(a["remote"], a["path"])]
            if a.get("dry_run", True): args.append("--dry-run")
            return self._run(args)
        if name == "create_link":
            self._require("readwrite"); return {"link": self._run(["link", self._remote_path(a["remote"], a["path"]), "--expire", a.get("expire", "1d")]).strip()}
        if name == "search":
            remote = self._remote_path(a["remote"], a.get("path", "")); pattern = a["pattern"]; limit = max(1, min(int(a.get("max_results", 1000)), self.max_scan_files))
            rows = self._run(["lsf", remote, "--recursive", "--files-only", "--format", "p"]).splitlines()
            return {"matches": [x for x in rows if pattern.lower() in x.lower()][:limit]}
        if name == "check":
            args = ["check", self._remote_path(a["source_remote"], a.get("source_path", "")), self._remote_path(a["destination_remote"], a.get("destination_path", "")), "--combined"]
            if a.get("size_only"): args.append("--size-only")
            return self._run(args)
        if name == "find_duplicates": return self._find_duplicates(a)
        if name == "dedupe":
            self._require("full"); args = ["dedupe", "--dedupe-mode", a.get("dedupe_mode", "skip"), self._remote_path(a["remote"], a["path"])]
            if a.get("dry_run", True): args.append("--dry-run")
            return self._run(args)
        raise ValueError(f"unknown tool: {name}")

    def _find_duplicates(self, a: dict[str, Any]) -> dict[str, Any]:
        remotes = a.get("remotes") or []
        if not remotes: raise PolicyError("remotes must contain at least one remote")
        mode = a.get("by", "hash_or_size"); groups: dict[str, list[dict[str, Any]]] = defaultdict(list); scanned = 0
        for remote in remotes:
            rows = self._run(["lsjson", self._remote_path(remote, a.get("path", "")), "--recursive", "--files-only", "--hash"], json_output=True)
            for row in rows[:min(int(a.get("max_files_per_remote", self.max_scan_files)), self.max_scan_files)]:
                scanned += 1; hashes = row.get("Hashes") or {}; digest = next((v for v in hashes.values() if v), "")
                if mode == "hash": key = f"hash:{digest}" if digest else "skip:{scanned}"
                elif mode == "size": key = f"size:{row.get('Size', -1)}"
                else: key = f"hash:{digest}" if digest else f"size:{row.get('Size', -1)}"
                groups[key].append({"remote": remote.rstrip(":"), "path": row.get("Path", ""), "size": row.get("Size", 0), "hash": digest})
        duplicates = [{"key": key, "files": files} for key, files in groups.items() if len(files) > 1 and not key.startswith("skip:")]
        duplicates.sort(key=lambda x: (-len(x["files"]), x["key"]))
        return {"scanned": scanned, "duplicate_groups": duplicates[:max(1, int(a.get("max_groups", 1000)))]}


def _response(req_id: Any, result: Any = None, error: dict[str, Any] | None = None) -> dict[str, Any]:
    out = {"jsonrpc": "2.0", "id": req_id}
    if error is None: out["result"] = result
    else: out["error"] = error
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="MCP stdio server for rclone")
    parser.add_argument("--version", action="version", version=SERVER_VERSION)
    parser.parse_args()
    try: server = RcloneMCP()
    except Exception as exc:
        print(str(exc), file=sys.stderr); return 2
    for line in sys.stdin:
        if not line.strip(): continue
        req_id = None
        try:
            req = json.loads(line); req_id = req.get("id"); method = req.get("method"); params = req.get("params") or {}
            if method == "initialize":
                result = {"protocolVersion": PROTOCOL_VERSION, "capabilities": {"tools": {"listChanged": False}}, "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION}, "instructions": "Use tools/list for the complete rclone tool catalog. Destructive operations are policy-gated by environment mode."}
            elif method == "notifications/initialized" or method == "notifications/cancelled": continue
            elif method == "ping": result = {}
            elif method == "tools/list": result = {"tools": server.tools()}
            elif method == "tools/call":
                name = params.get("name"); args = params.get("arguments") or {}
                result = {"content": [{"type": "text", "text": json.dumps(server.call(name, args), ensure_ascii=False, indent=2, default=str)}], "isError": False}
            else: raise ValueError(f"method not found: {method}")
            if req_id is not None: print(json.dumps(_response(req_id, result), ensure_ascii=False), flush=True)
        except Exception as exc:
            if req_id is not None:
                if req.get("method") == "tools/call":
                    result = {"content": [{"type": "text", "text": str(exc)}], "isError": True}
                    print(json.dumps(_response(req_id, result), ensure_ascii=False), flush=True)
                else:
                    print(json.dumps(_response(req_id, error={"code": -32000, "message": str(exc)}), ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__": raise SystemExit(main())
