"""Make the windows_launcher modules importable for pytest.

The launcher is a plain script directory (no package); the bat runs
``python launcher_server.py`` from its own dir, which puts that dir on
sys.path.  Tests replicate that by prepending the parent dir here.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
