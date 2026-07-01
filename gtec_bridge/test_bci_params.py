#!/usr/bin/env python3
"""Test 4: Inspect BCICore8 constructor parameters and runtime properties.

Discovers what configuration options BCICore8 exposes — sampling rate,
channel count, buffer settings, etc.

Usage
-----
    python test_bci_params.py
"""

import gpype as gp

if __name__ == "__main__":
    print("=" * 60)
    print("BCICore8 Constructor Signature")
    print("=" * 60)
    import inspect
    try:
        sig = inspect.signature(gp.BCICore8.__init__)
        print(f"BCICore8.__init__{sig}")
    except Exception as e:
        print(f"Could not get signature: {e}")

    print()
    print("=" * 60)
    print("BCICore8 Source Code (if available)")
    print("=" * 60)
    try:
        src = inspect.getsource(gp.BCICore8)
        print(src[:3000])
    except Exception as e:
        print(f"Could not get source: {e}")

    print()
    print("=" * 60)
    print("BCICore8 Instance Attributes")
    print("=" * 60)
    try:
        source = gp.BCICore8()
        print(f"type      : {type(source).__name__}")
        print(f"module    : {type(source).__module__}")

        # List all public attributes
        attrs = [a for a in dir(source) if not a.startswith("_")]
        print(f"\nPublic attributes ({len(attrs)}):")
        for a in attrs:
            try:
                val = getattr(source, a)
                if callable(val):
                    print(f"  .{a}()        — method")
                else:
                    val_str = str(val)
                    if len(val_str) > 80:
                        val_str = val_str[:77] + "..."
                    print(f"  .{a}          = {val_str}")
            except Exception as exc:
                print(f"  .{a}          — <error: {exc}>")

        # Try to get channel count and sampling rate
        print()
        print("=" * 60)
        print("Key properties check")
        print("=" * 60)
        for prop in [
            "n_channels", "channel_count", "num_channels",
            "sample_rate", "sampling_rate", "fs",
            "channel_names", "channel_labels",
        ]:
            if hasattr(source, prop):
                print(f"  .{prop} = {getattr(source, prop)}")
            else:
                print(f"  .{prop} — not found")

    except Exception as e:
        print(f"Error creating BCICore8: {e}")

    print()
    print("=" * 60)
    print("Available gpype source classes (dir scan)")
    print("=" * 60)
    for name in sorted(dir(gp)):
        if any(kw in name.lower() for kw in ["core", "bci", "unicorn", "hybrid", "nautilus", "source"]):
            obj = getattr(gp, name)
            if callable(obj):
                try:
                    sig = inspect.signature(obj.__init__)
                    print(f"  gp.{name}{sig}")
                except Exception:
                    print(f"  gp.{name}(...)")
