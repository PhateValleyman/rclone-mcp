.PHONY: test smoke

# Run the test suite.
test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

# Exercise MCP initialization without touching a remote.
smoke:
	printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | PYTHONPATH=src python3 -m rclone_mcp.server
