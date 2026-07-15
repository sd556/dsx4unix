#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

HEFESTO_SRC = Path("/home/deck/code/hefesto-dualsense4unix/src")
if str(HEFESTO_SRC) not in sys.path:
    sys.path.insert(0, str(HEFESTO_SRC))

from hefesto_dualsense4unix.app.ipc_bridge import daemon_status_basic, led_set, trigger_set, _run_call


def main() -> int:
    parser = argparse.ArgumentParser(description="Wait for a DualSense on Hefesto and pulse an adaptive trigger test.")
    parser.add_argument("--timeout", type=float, default=60.0, help="Seconds to wait for the controller (default: 60)")
    parser.add_argument("--seconds", type=float, default=8.0, help="How long to hold the trigger effect before reset (default: 8)")
    parser.add_argument("--side", choices=["left", "right"], default="right", help="Trigger side to test")
    parser.add_argument("--mode", default="Resistance", help="Hefesto trigger mode to use (default: Resistance)")
    parser.add_argument("params", nargs="*", type=int, default=[0, 8], help="Mode params, e.g. 0 8 for Resistance")
    args = parser.parse_args()

    deadline = time.monotonic() + args.timeout
    print("Waiting for Hefesto controller status...")
    last_status = None
    while time.monotonic() < deadline:
        status = daemon_status_basic()
        if status:
            last_status = status
            connected = bool(status.get("controller_connected", status.get("connected")))
            transport = status.get("transport")
            print(f"status: connected={connected} transport={transport}")
            if connected:
                print("Applying LED + trigger test now.")
                if not led_set((255, 96, 0)):
                    print("warning: LED IPC call failed")
                if not trigger_set(args.side, args.mode, args.params):
                    print("error: trigger IPC call failed")
                    return 2
                print(f"Hold the {args.side} trigger now for {args.seconds:.1f}s...")
                time.sleep(args.seconds)
                _run_call("trigger.reset", {"side": args.side})
                led_set((0, 64, 255))
                print("Trigger reset sent. Test complete.")
                return 0
        else:
            print("status: daemon unreachable")
        time.sleep(1.0)

    print("Timed out waiting for controller.")
    if last_status is not None:
        print(f"Last daemon status: {last_status}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
