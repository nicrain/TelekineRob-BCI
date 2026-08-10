"""LSL stream probe for the O2 launcher (P8b).

Runs under the DEVICE's ``python_cmd`` — a venv that has ``pylsl`` — NOT in
the launcher itself, which stays zero-dependency. Prints ``found`` when a
stream with the given source_id resolves within the timeout, else
``not-found`` (or ``no-pylsl`` if pylsl isn't installed in that python).
"""
import sys


def main() -> int:
    try:
        from pylsl import resolve_byprop
    except ImportError:
        print("no-pylsl")
        return 0

    source_id = sys.argv[1] if len(sys.argv) > 1 else ""
    timeout = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
    streams = resolve_byprop("source_id", source_id, timeout=timeout)
    print("found" if streams else "not-found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
