#!/usr/bin/env python3
import signal
import sys
import time


def stop(_signum, _frame):
    raise SystemExit(0)


signal.signal(signal.SIGTERM, stop)
args = [arg for arg in sys.argv[1:] if arg != "--foreground"]
if "mount" not in args:
    print("unsupported", file=sys.stderr)
    raise SystemExit(1)
while True:
    time.sleep(1)
