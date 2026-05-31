"""Persistent CleanSun launcher for Windows auto-start (Task Scheduler).

Run with pythonw.exe so there is no console window. Output is redirected to
server.log (capped at ~2 MB) since pythonw has no stdout. Binds 0.0.0.0:9191
so the dashboard is reachable from other devices on the LAN.
"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

# Cap the log so it never grows without bound across reboots.
_LOG = os.path.join(BASE, "server.log")
try:
    if os.path.exists(_LOG) and os.path.getsize(_LOG) > 2 * 1024 * 1024:
        os.remove(_LOG)
except OSError:
    pass

_fh = open(_LOG, "a", buffering=1, encoding="utf-8")
sys.stdout = _fh
sys.stderr = _fh

import asyncio
import time

import app_runner

# Auto-restart loop: if the server crashes, wait and bring it back up.
while True:
    print("=== CleanSun start {} ===".format(time.strftime("%Y-%m-%d %H:%M:%S")))
    try:
        # host defaults to 0.0.0.0 (all interfaces); port 9191.
        asyncio.run(app_runner.bootstrap(port=9191))
    except KeyboardInterrupt:
        break
    except Exception as exc:
        print("crash: {} — restart in 10s".format(exc))
        time.sleep(10)
    else:
        break
