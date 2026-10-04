import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SRC = ROOT / "src"
FAKE = ROOT / "tests" / "fake_rclone.py"
FAKE_MOUNT = ROOT / "tests" / "fake_rclone_mount.py"


def run_server(*requests, mode="readonly", rclone=FAKE):
    env = os.environ.copy()
    env.update({"PYTHONPATH": str(SRC), "RCLONE_MCP_RCLONE": str(rclone), "RCLONE_MCP_MODE": mode})
    proc = subprocess.run([sys.executable, "-m", "rclone_mcp.server"], input="\n".join(json.dumps(x) for x in requests) + "\n", text=True, capture_output=True, env=env, check=True)
    return [json.loads(x) for x in proc.stdout.splitlines() if x.strip()]


class ServerTests(unittest.TestCase):
    def test_initialize_and_tools(self):
        out = run_server({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        self.assertEqual(out[0]["result"]["serverInfo"]["name"], "rclone-mcp")
        names = {x["name"] for x in out[1]["result"]["tools"]}
        self.assertTrue({"find_duplicates", "delete", "sync", "list_files"} <= names)

    def test_readonly_blocks_delete(self):
        out = run_server({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "delete", "arguments": {"remote": "a", "path": "x", "dry_run": False}}})
        self.assertTrue(out[0]["result"]["isError"])
        self.assertIn("requires RCLONE_MCP_MODE=full", out[0]["result"]["content"][0]["text"])

    def test_duplicate_scan(self):
        out = run_server({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "find_duplicates", "arguments": {"remotes": ["a", "b"]}}})
        payload = json.loads(out[0]["result"]["content"][0]["text"])
        self.assertEqual(payload["scanned"], 4)
        self.assertEqual(len(payload["duplicate_groups"]), 2)

    def test_full_mode_allows_dry_run_delete(self):
        out = run_server({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "delete", "arguments": {"remote": "a", "path": "x"}}}, mode="full")
        self.assertNotIn("error", out[0])

    def test_config_discovery_and_create(self):
        out = run_server(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "config_providers", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "config_create", "arguments": {"name": "demo", "provider_type": "local", "values": {"nounc": True}}}},
            mode="readwrite",
        )
        self.assertEqual(out[0]["result"]["isError"], False)
        self.assertEqual(json.loads(out[0]["result"]["content"][0]["text"]), {"local": {"Name": "local", "Options": []}})
        self.assertEqual(out[1]["result"]["isError"], False)

    def test_config_delete_requires_confirmation(self):
        out = run_server({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "config_delete", "arguments": {"name": "demo"}}}, mode="full")
        self.assertTrue(out[0]["result"]["isError"])
        self.assertIn("confirm=true", out[0]["result"]["content"][0]["text"])

    def test_config_interactive_requires_explicit_answers(self):
        out = run_server({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "config_interactive", "arguments": {}}}, mode="readwrite")
        self.assertTrue(out[0]["result"]["isError"])
        self.assertIn("input_lines is required", out[0]["result"]["content"][0]["text"])

    def test_mount_lifecycle(self):
        out = run_server(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "mount_start", "arguments": {"remote": "a", "mountpoint": "mount-test", "read_only": True, "vfs_cache_mode": "writes"}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "mount_list", "arguments": {}}},
            mode="readwrite",
            rclone=FAKE_MOUNT,
        )
        self.assertFalse(out[0]["result"]["isError"])
        mount = json.loads(out[0]["result"]["content"][0]["text"])
        self.assertEqual(mount["remote"], "a:")
        self.assertTrue(out[1]["result"]["isError"] is False)
        self.assertEqual(len(json.loads(out[1]["result"]["content"][0]["text"])["mounts"]), 1)

    def test_invalid_json_rpc_gets_error_response(self):
        out = run_server({"id": 1, "method": "ping", "params": {}})
        self.assertEqual(out[0]["error"]["code"], -32600)

    def test_max_depth_schema_allows_zero(self):
        out = run_server({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
        list_files = next(tool for tool in out[0]["result"]["tools"] if tool["name"] == "list_files")
        self.assertEqual(list_files["inputSchema"]["properties"]["max_depth"]["minimum"], 0)


if __name__ == "__main__":
    unittest.main()
