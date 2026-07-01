#!/usr/bin/env python3
"""Explore BCICore8 connection/disconnection API.

Usage
-----
    python gtec_bridge/test_connection.py
"""

import gpype as gp
import inspect

if __name__ == "__main__":
    print("=" * 60)
    print("BCICore8 full source code (connection-related)")
    print("=" * 60)
    try:
        src = inspect.getsource(gp.BCICore8)
        print(src)
    except Exception as e:
        print(f"Could not get source: {e}")

    print()
    print("=" * 60)
    print("AmplifierSource base class")
    print("=" * 60)
    try:
        src = inspect.getsource(gp.AmplifierSource)
        print(src[:5000])
    except Exception as e:
        print(f"Could not get source: {e}")

    print()
    print("=" * 60)
    print("Connection-relevant methods on BCICore8 instance")
    print("=" * 60)
    try:
        source = gp.BCICore8(channel_count=4)
    except Exception as e:
        print(f"Could not create source: {e}")
        exit(1)

    connection_methods = [
        "connect", "disconnect", "start", "stop",
        "setup", "reset", "cycle", "step",
        "get_state", "get_context", "get_counter",
    ]
    for name in connection_methods:
        if hasattr(source, name):
            method = getattr(source, name)
            try:
                sig = inspect.signature(method)
                doc = inspect.getdoc(method)
                doc_str = f" — {doc.split(chr(10))[0][:80]}" if doc else ""
                print(f"  .{name}{sig}{doc_str}")
            except Exception:
                print(f"  .{name}() — cannot inspect")

    print()
    print("=" * 60)
    print("_device attribute")
    print("=" * 60)
    if hasattr(source, "_device"):
        dev = source._device
        print(f"  _device = {dev}")
        if dev is not None:
            print(f"  type    = {type(dev).__name__}")
            print(f"  module  = {type(dev).__module__}")
            # List methods
            for attr in dir(dev):
                if not attr.startswith("_"):
                    obj = getattr(dev, attr)
                    if callable(obj):
                        try:
                            sig = inspect.signature(obj)
                            print(f"  _device.{attr}{sig}")
                        except Exception:
                            print(f"  _device.{attr}()")

    print()
    print("=" * 60)
    print("Check for ble module / scan utilities")
    print("=" * 60)
    ble_names = [n for n in dir(gp) if "ble" in n.lower() or "scan" in n.lower() or "bluetooth" in n.lower()]
    if ble_names:
        for n in ble_names:
            print(f"  gp.{n}")
    else:
        print("  No BLE/scan related symbols found directly on gp")
        # Try submodules
        try:
            from gpype.backend.sources import bci_core8
            print("  Found: gpype.backend.sources.bci_core8")
        except ImportError:
            pass
        try:
            import gpype.backend.sources as srcs
            print(f"  gpype.backend.sources members: {[n for n in dir(srcs) if not n.startswith('_')]}")
        except ImportError:
            pass

    print()
    print("=" * 60)
    print("Serial number detection")
    print("=" * 60)
    for attr in ["_target_sn", "serial", "config"]:
        if hasattr(source, attr):
            val = getattr(source, attr)
            print(f"  .{attr} = {val}")
