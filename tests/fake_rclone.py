#!/usr/bin/env python3
import json
import sys

args = sys.argv[1:]
while args and args[0].startswith("--"):
    args.pop(0)
    if args and not args[0].startswith("--") and args[0] in {"--config", "--checkers"}:
        args.pop(0)

cmd = args[0] if args else ""
if cmd == "listremotes":
    print("a:\nb:\n")
elif cmd == "version":
    print("fake-rclone 0.0")
elif cmd == "config":
    sub = args[1] if len(args) > 1 else ""
    if sub == "file": print("/tmp/fake-rclone.conf")
    elif sub == "redacted": print("[fake]\ntype = local\nsecret = ***REDACTED***")
    elif sub == "providers": print(json.dumps({"local": {"Name": "local", "Options": []}}))
    else: print("ok")
elif cmd == "lsjson":
    if "--stat" in args:
        print(json.dumps({"Path": "one.txt", "Name": "one.txt", "Size": 10, "IsDir": False}))
    else:
        print(json.dumps([
            {"Path": "one.txt", "Name": "one.txt", "Size": 10, "Hashes": {"MD5": "same"}},
            {"Path": "unique.txt", "Name": "unique.txt", "Size": 20, "Hashes": {"MD5": "unique"}},
        ]))
elif cmd in {"delete", "purge", "sync", "copy", "move", "mkdir", "copyto", "link", "dedupe", "check", "cat", "size", "lsf"}:
    if cmd == "cat": print("hello")
    elif cmd == "size": print(json.dumps({"count": 1, "bytes": 10}))
    elif cmd == "lsf": print("one.txt\nunique.txt")
    elif cmd == "link": print("https://example.invalid/link")
    else: print("ok")
else:
    print("unknown", file=sys.stderr)
    raise SystemExit(1)
